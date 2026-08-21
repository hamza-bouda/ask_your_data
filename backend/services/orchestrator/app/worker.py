import asyncio
import json
import logging
import os
import socket
import traceback
import uuid
from datetime import datetime, timezone
import redis.asyncio as redis
from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError

from app.database import get_db, create_tables
from app.orm_models import Conversation, Message, Run
from app.models import ConversationState
from app.graph import orchestrator_graph
from contracts.events import RunEvent, RunEventType


import structlog
from observability import setup_logging, setup_tracing, get_tracer, extract_context
from prometheus_client import start_http_server, Counter, Gauge, Histogram

# Initialize observability
setup_logging(service_name="worker")
setup_tracing(service_name="worker")
logger = structlog.get_logger("worker")

tracer = get_tracer("worker")

# Prometheus Metrics
WORKER_TASKS_PROCESSED = Counter("worker_tasks_processed_total", "Total tasks processed by worker", ["status"])
WORKER_TASK_DURATION = Histogram("worker_task_duration_seconds", "Task processing duration")
WORKER_DLQ_MESSAGES = Counter("worker_dlq_messages_total", "Total messages sent to DLQ")
WORKER_RETRIES = Counter("worker_retries_total", "Total task retries")

# Start Prometheus metrics server on port 8000
start_http_server(8000)



REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
WORKER_ID = f"worker-{socket.gethostname()}-{os.getpid()}"
GROUP_NAME = "cg_orchestrator_workers"
STREAM_NAME = "stream:tasks:runs"
DLQ_STREAM = "stream:dlq:runs"
MAX_RETRIES = 3
VISIBILITY_TIMEOUT_MS = 60000  # 60 seconds

async def setup_consumer_group(r: redis.Redis):
    try:
        await r.xgroup_create(STREAM_NAME, GROUP_NAME, id="0-0", mkstream=True)
        logger.info(f"Created consumer group {GROUP_NAME} on {STREAM_NAME}")
    except ResponseError as e:
        if "BUSYGROUP" in str(e):
            pass
        else:
            raise

async def claim_abandoned_messages(r: redis.Redis):
    while True:
        try:
            # Check pending messages for the group
            pending = await r.xpending_range(STREAM_NAME, GROUP_NAME, min="-", max="+", count=100)
            for p in pending:
                message_id = p["message_id"]
                consumer = p["consumer"]
                time_since_delivered = p["time_since_delivered"]
                
                if time_since_delivered > VISIBILITY_TIMEOUT_MS:
                    logger.info(f"Claiming abandoned message {message_id} from {consumer}")
                    await r.xclaim(STREAM_NAME, GROUP_NAME, WORKER_ID, VISIBILITY_TIMEOUT_MS, [message_id])
                    
        except asyncio.CancelledError:
            break
        except RedisTimeoutError:
            # A blocking XREADGROUP timeout simply means there is no work yet.
            # It is an expected idle state, not an operational failure.
            continue
        except Exception as e:
            logger.error(f"Error claiming abandoned messages: {e}")
            
        await asyncio.sleep(30)

async def process_message(r: redis.Redis, message_id: str, data: dict):
    run_id = data.get("run_id")
    tenant_id = data.get("tenant_id")
    user_id = data.get("user_id")
    source_id = data.get("source_id") or None
    conversation_id = data.get("conversation_id")
    correlation_id = data.get("correlation_id", "")
    question = data.get("question", "")

    # OpenTelemetry context extraction
    ctx = extract_context(data)
    
    with tracer.start_as_current_span("process_message", context=ctx) as span:
        span.set_attribute("tenant_id", tenant_id or "")
        span.set_attribute("source_id", source_id or "")
        span.set_attribute("correlation_id", correlation_id)
        span.set_attribute("run_id", run_id or "")
        # Do not log question directly to avoid leaking PII/secrets

        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            run_id=run_id,
            tenant_id=tenant_id,
            source_id=source_id,
            conversation_id=conversation_id
        )

        with WORKER_TASK_DURATION.time():


            if not run_id:
                await r.xack(STREAM_NAME, GROUP_NAME, message_id)
                return

            logger.info(f"Processing run {run_id}")
            db_gen = get_db()
            db = next(db_gen)

            try:
                run = db.query(Run).filter(Run.id == run_id).first()
                if not run:
                    logger.warning(f"Run {run_id} not found in DB")
                    await r.xack(STREAM_NAME, GROUP_NAME, message_id)
                    return

                if run.status in ["completed", "error"]:
                    logger.info(f"Run {run_id} already finalized (status: {run.status}). Acking.")
                    await r.xack(STREAM_NAME, GROUP_NAME, message_id)
                    return

                # Prepare execution
                run.attempts += 1
                if run.attempts > 1:
                    WORKER_RETRIES.inc()
                run.worker_id = WORKER_ID
                run.started_at = datetime.now(timezone.utc)
                run.last_heartbeat_at = datetime.now(timezone.utc)

                if run.attempts > MAX_RETRIES:
                    logger.error(f"Run {run_id} exceeded max retries. Moving to DLQ.")
                    run.status = "error"
                    WORKER_TASKS_PROCESSED.labels(status="error").inc()
                    run.stage = "failed_retry"
                    run.error_message = "Exceeded max retries"
                    run.completed_at = datetime.now(timezone.utc)
                    db.commit()

                    await r.xadd(DLQ_STREAM, data)
                    WORKER_DLQ_MESSAGES.inc()
                    await r.xack(STREAM_NAME, GROUP_NAME, message_id)

                    # Emit fail event
                    fail_event = RunEvent(
                        run_id=run_id, conversation_id=conversation_id, event_type=RunEventType.RUN_FAILED,
                        stage="failed_retry", status="error", payload={"detail": "Exceeded max retries"}, correlation_id=correlation_id
                    )
                    await r.xadd(f"stream:events:{run_id}", {"event": fail_event.model_dump_json()})
                    return

                run.status = "running"
                db.commit()

                # Helper to emit events
                async def emit(event_type: RunEventType, stage: str, status: str, payload: dict):
                    event = RunEvent(
                        run_id=run_id,
                        conversation_id=conversation_id,
                        event_type=event_type,
                        stage=stage,
                        status=status,
                        payload=payload,
                        correlation_id=correlation_id
                    )
                    await r.xadd(f"stream:events:{run_id}", {"event": event.model_dump_json()})
                    run.last_heartbeat_at = datetime.now(timezone.utc)
                    db.commit()

                await emit(RunEventType.RUN_STARTED, "started", "running", {})

                history_msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(10).all()
                chat_history = [{"role": m.role, "content": m.content} for m in reversed(history_msgs)]

                initial_state = ConversationState(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    source_id=source_id,
                    conversation_id=conversation_id,
                    question=question,
                    run_id=run_id,
                    chat_history=chat_history
                )

                final_state_dict = initial_state.model_dump()
                error_msg = None
                status = "error"

                try:
                    async for chunk in orchestrator_graph.astream(initial_state.model_dump(), stream_mode="updates"):
                        for node_name, node_state in chunk.items():
                            final_state_dict.update(node_state)
                            stage = node_name
                            node_status = node_state.get("status", "running")

                            evt_type = None
                            payload = {}

                            if node_name == "retrieve":
                                evt_type = RunEventType.RETRIEVAL_COMPLETED
                            elif node_name == "plan":
                                if node_status == "needs_clarification":
                                    evt_type = RunEventType.CLARIFICATION_REQUESTED
                                    payload = {"options": node_state.get("clarification_options", [])}
                                elif node_status == "unrelated":
                                    evt_type = RunEventType.RUN_COMPLETED
                                else:
                                    evt_type = RunEventType.PLANNING
                                    payload = {"intent": node_state.get("semantic_plan", {}).get("intent")}
                            elif node_name == "generate_sql":
                                evt_type = RunEventType.SQL_GENERATING
                            elif node_name == "execute_sql":
                                evt_type = RunEventType.QUERY_EXECUTING
                            elif node_name == "visualization":
                                evt_type = RunEventType.VISUALIZATION_GENERATING
                            elif node_name == "repair":
                                evt_type = RunEventType.SQL_VALIDATING

                            if evt_type:
                                await emit(evt_type, stage, node_status, payload)

                    status = final_state_dict.get("status", "completed")
                    error_msg = final_state_dict.get("error_message")

                except Exception as e:
                    traceback.print_exc()
                    logger.error(f"Error in LangGraph for run {run_id}: {e}")
                    error_msg = str(e)
                    status = "error"
                    await emit(RunEventType.RUN_FAILED, "error", status, {"detail": "Unexpected error occurred."})
                    raise # Raise to avoid ACK so it can be retried by XCLAIM

                final_state = ConversationState(**final_state_dict)
                # Graph node states (for example "visualized") are useful for the
                # timeline, but persisted runs must expose a stable terminal state.
                if status == "error":
                    terminal_status = "failed"
                elif status == "needs_clarification":
                    terminal_status = "awaiting_clarification"
                elif status == "unrelated":
                    terminal_status = "completed"
                else:
                    terminal_status = "completed"

                run.status = terminal_status
                run.stage = "completed" if terminal_status == "completed" else status
                run.error_message = error_msg
                run.completed_at = datetime.now(timezone.utc)

                has_error = error_msg is not None
                response_text = error_msg if has_error else "Voici les résultats"

                if final_state.response_text:
                    response_text = final_state.response_text
                elif status == "unrelated" and final_state.results and len(final_state.results) > 0 and "response" in final_state.results[0]:
                    response_text = final_state.results[0]["response"]
                elif status == "needs_clarification":
                    response_text = "Je n'ai pas bien compris. Pouvez-vous préciser ?"

                payload = {
                    "semantic_plan": final_state.semantic_plan,
                    "results": final_state.results,
                    "chart_spec": final_state.chart_spec,
                    "sql_query": final_state.sql_query,
                    "clarification_options": final_state.clarification_options,
                    "error_message": final_state.error_message
                }

                ai_msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response_text,
                    payload=payload
                )
                db.add(ai_msg)
                db.commit()

                run.final_message_id = ai_msg.id
                db.commit()

                if terminal_status == "failed":
                    await emit(RunEventType.RUN_FAILED, "completed", terminal_status, {"detail": error_msg})
                else:
                    await emit(RunEventType.RESULT_READY, run.stage, terminal_status, {})

                # Successful completion, acknowledge message
                await r.xack(STREAM_NAME, GROUP_NAME, message_id)
                logger.info(f"Run {run_id} completed successfully")
                WORKER_TASKS_PROCESSED.labels(status="success").inc()

            finally:
                db.close()


async def main():
    logger.info(f"Starting worker {WORKER_ID}")
    create_tables()
    
    r = redis.from_url(REDIS_URL, decode_responses=True)
    await setup_consumer_group(r)
    
    # Start background task to claim abandoned messages
    asyncio.create_task(claim_abandoned_messages(r))

    while True:
        try:
            # Read from stream
            result = await r.xreadgroup(GROUP_NAME, WORKER_ID, {STREAM_NAME: ">"}, count=1, block=5000)
            if result:
                for _, messages in result:
                    for message_id, message_data in messages:
                        try:
                            await process_message(r, message_id, message_data)
                        except Exception as e:
                            logger.error(f"Failed to process message {message_id}: {e}")
                            # Do not xack, let the claim process pick it up later
        except asyncio.CancelledError:
            break
        except RedisTimeoutError:
            continue
        except Exception as e:
            if "Timeout reading" in str(e):
                # A blocking Redis read with no pending work is an expected idle
                # state. Some redis-py backends expose it as a generic timeout.
                continue
            logger.error(f"Error in main loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped")
