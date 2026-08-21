"""Conversation Orchestrator Service.

Coordinates the end-to-step conversational BI pipeline using LangGraph.
"""

from typing import Any, Optional, List, AsyncGenerator
from fastapi import HTTPException, Depends, BackgroundTasks, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uuid
from datetime import datetime, timezone
import asyncio
import json
import traceback
import hmac
import os

from app.redis_client import get_redis_client, close_redis_client

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics

from contracts.events import RunEvent, RunEventType

try:
    from app.models import ConversationState
    from app.graph import orchestrator_graph
    from app.database import create_tables, get_db
    from app.orm_models import Conversation, Message, Run
except ImportError:
    from backend.services.orchestrator.app.models import ConversationState
    from backend.services.orchestrator.app.graph import orchestrator_graph
    from backend.services.orchestrator.app.database import create_tables, get_db
    from backend.services.orchestrator.app.orm_models import Conversation, Message, Run

from sqlalchemy.orm import Session

app = create_service_app(service_name="orchestrator")

# Observability setup
setup_logging(service_name="orchestrator")
setup_tracing(service_name="orchestrator", app=app)
setup_metrics(app)

try:
    from app.dashboards import router as dashboards_router
except ImportError:
    from backend.services.orchestrator.app.dashboards import router as dashboards_router

app.include_router(dashboards_router)


def require_internal_admin_token(
    x_internal_admin_token: str | None = Header(default=None),
) -> None:
    """Keep operational endpoints inaccessible unless explicitly configured."""
    expected_token = os.getenv("INTERNAL_ADMIN_TOKEN")
    if not expected_token or not x_internal_admin_token or not hmac.compare_digest(
        x_internal_admin_token, expected_token
    ):
        # A 404 avoids advertising an operational endpoint to unauthenticated callers.
        raise HTTPException(status_code=404, detail="Not found")

@app.on_event("startup")
def on_startup():
    create_tables()

@app.on_event("shutdown")
async def on_shutdown():
    await close_redis_client()

# ── Request/Response Models ──────────────────────────────────────

class CreateConversationRequest(BaseModel):
    tenant_id: str
    user_id: str
    source_id: Optional[str] = None
    title: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    source_id: Optional[str] = None
    title: str
    created_at: datetime
    updated_at: datetime

class SendMessageRequest(BaseModel):
    tenant_id: str
    user_id: str
    source_id: Optional[str] = None
    message: str

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    payload: Optional[dict] = None
    created_at: datetime

class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse
    messages: List[MessageResponse]

class ResultsResponse(BaseModel):
    results: List[dict[str, Any]]
    total: int
    offset: int
    limit: int

class RunResponse(BaseModel):
    run_id: str
    conversation_id: str | None = None
    status: str
    events_url: str | None = None
    results: Optional[list[dict[str, Any]]] = None
    chart_spec: Optional[dict[str, Any]] = None
    semantic_plan: Optional[dict[str, Any]] = None
    clarification_options: Optional[list[dict[str, str]]] = None
    error_message: Optional[str] = None
    response: Optional[str] = None
    sql_draft: Optional[dict] = None


# Global SSE Queues removed - using Redis Streams instead


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/conversations", response_model=ConversationResponse)
async def create_conversation(body: CreateConversationRequest, db: Session = Depends(get_db)):
    """Create a new conversation."""
    conv = Conversation(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        source_id=body.source_id,
        title=body.title or "Nouvelle conversation"
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@app.get("/internal/conversations", response_model=List[ConversationResponse])
async def list_conversations(tenant_id: str, user_id: str, db: Session = Depends(get_db)):
    """List conversations for a user."""
    convs = db.query(Conversation).filter(
        Conversation.tenant_id == tenant_id,
        Conversation.user_id == user_id
    ).order_by(Conversation.updated_at.desc()).all()
    return convs

@app.get("/internal/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str, tenant_id: str, user_id: str, db: Session = Depends(get_db)):
    """Get a conversation with its messages."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.tenant_id == tenant_id,
        Conversation.user_id == user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {
        "conversation": conv,
        "messages": conv.messages
    }


@app.get("/internal/results", response_model=ResultsResponse)
async def list_results(
    tenant_id: str,
    user_id: str,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Return persisted data results without the client performing N+1 reads."""
    offset = max(offset, 0)
    limit = min(max(limit, 1), 100)
    rows = (
        db.query(Message, Conversation.title)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .filter(Conversation.tenant_id == tenant_id, Conversation.user_id == user_id)
        .filter(Message.role.in_(["assistant", "ai"]))
        .order_by(Message.created_at.desc())
        .all()
    )
    results = []
    for message, conversation_title in rows:
        payload = message.payload or {}
        intent = (payload.get("semantic_plan") or {}).get("intent")
        data = payload.get("results")
        if intent not in {"DATA_QUERY", "CHART_GENERATION"} or not isinstance(data, list) or not data:
            continue
        results.append({
            "id": message.id,
            "date": message.created_at,
            "title": (payload.get("chart_spec") or {}).get("title") or f"Résultat de {conversation_title}",
            "conversation_title": conversation_title,
            "data": data,
            "chart_spec": payload.get("chart_spec"),
            "sql": payload.get("sql_query"),
        })
    total = len(results)
    return {"results": results[offset:offset + limit], "total": total, "offset": offset, "limit": limit}

@app.post("/internal/conversations/{conversation_id}/messages", response_model=RunResponse)
async def send_message(
    conversation_id: str, 
    body: SendMessageRequest, 
    request: Request,
    db: Session = Depends(get_db)
):
    """Send a message and push a run task to Redis."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.tenant_id == body.tenant_id,
        Conversation.user_id == body.user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if body.source_id and conv.source_id and body.source_id != conv.source_id:
        raise HTTPException(status_code=409, detail="Conversation belongs to a different datasource")
    if body.source_id and not conv.source_id:
        conv.source_id = body.source_id
        
    # Auto-title on first message
    if len(conv.messages) == 0 and conv.title == "Nouvelle conversation":
        conv.title = (body.message[:30] + '...') if len(body.message) > 30 else body.message
        db.add(conv)

    # Save user message
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=body.message
    )
    db.add(user_msg)
    
    # Create Run with pending status
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        conversation_id=conversation_id,
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        source_id=conv.source_id,
        status="pending",
        stage="init"
    )
    db.add(run)
    db.commit()

    correlation_id = request.headers.get("X-Correlation-ID", "")
    
    # Push to Redis Stream
    redis_client = get_redis_client()
    task_payload = {
        "run_id": run_id,
        "tenant_id": body.tenant_id,
        "user_id": body.user_id,
        "source_id": conv.source_id or "",
        "conversation_id": conversation_id,
        "correlation_id": correlation_id,
        "question": body.message
    }
    
    # Inject tracing context
    from observability import inject_context
    task_payload.update(inject_context())
    
    await redis_client.xadd("stream:tasks:runs", task_payload)
    
    return RunResponse(
        run_id=run_id,
        conversation_id=conversation_id,
        status="pending",
        events_url=f"/v1/runs/{run_id}/events"
    )

# ── SSE Endpoints ───────────────────────────────────────────────

@app.get("/internal/runs/{run_id}/events")
async def get_run_events(run_id: str, tenant_id: str, user_id: str, request: Request, last_event_id: str | None = None, db: Session = Depends(get_db)):
    """Stream events for a specific run from Redis."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    if run.tenant_id != tenant_id or run.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # The client can pass Last-Event-ID as a header, but also via query params (useful for EventSource if we had to polyfill)
    client_last_event_id = request.headers.get("Last-Event-ID") or last_event_id or "0-0"
    redis_client = get_redis_client()
    stream_key = f"stream:events:{run_id}"

    async def event_generator():
        current_id = client_last_event_id
        
        # Check if the run is already completed before we even start pulling,
        # but we should still replay events if the client hasn't seen them.
        try:
            while True:
                if await request.is_disconnected():
                    break
                    
                # Read from Redis stream (block for 5 seconds to wait for new events)
                streams = {stream_key: current_id}
                result = await redis_client.xread(streams, count=10, block=5000)
                
                if result:
                    for _, messages in result:
                        for message_id, message_data in messages:
                            current_id = message_id
                            event_json = message_data.get("event")
                            if event_json:
                                yield f"id: {message_id}\ndata: {event_json}\n\n"
                                
                                # If this was a terminal event, we can stop the stream
                                event_dict = json.loads(event_json)
                                if event_dict.get("event_type") in [RunEventType.RESULT_READY, RunEventType.RUN_FAILED]:
                                    return
                                    
                # Send keep-alive comments to prevent connection drop
                yield ": keep-alive\n\n"
                
                # If run is marked as finished in DB and no more events, we close
                # This protects against cases where the terminal event was lost or missed
                db.expire_all()
                current_run = db.query(Run).filter(Run.id == run_id).first()
                if current_run and current_run.status in ["completed", "error"]:
                    # Wait a bit just in case events are still being flushed
                    await asyncio.sleep(2)
                    final_result = await redis_client.xread({stream_key: current_id}, count=10, block=10)
                    if not final_result:
                        yield f"id: {current_id}\ndata: {json.dumps({'event_type': RunEventType.RESULT_READY if current_run.status == 'completed' else RunEventType.RUN_FAILED, 'status': current_run.status, 'run_id': run_id})}\n\n"
                        return

        except asyncio.CancelledError:
            pass
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'event_type': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/internal/runs/{run_id}", response_model=RunResponse)
async def get_run_status(run_id: str, tenant_id: str, user_id: str, db: Session = Depends(get_db)):
    """Retrieve the status and results of a run."""
    run = db.query(Run).filter(Run.id == run_id, Run.tenant_id == tenant_id, Run.user_id == user_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    response_data = RunResponse(
        run_id=run_id,
        conversation_id=run.conversation_id,
        status=run.status,
        error_message=run.error_message
    )
    
    # If final message exists, populate payload
    if run.final_message_id:
        msg = db.query(Message).filter(Message.id == run.final_message_id).first()
        if msg and msg.payload:
            response_data.results = msg.payload.get("results")
            response_data.chart_spec = msg.payload.get("chart_spec")
            response_data.semantic_plan = msg.payload.get("semantic_plan")
            response_data.clarification_options = msg.payload.get("clarification_options")
            response_data.sql_draft = {"sql_query": msg.payload.get("sql_query")} if msg.payload.get("sql_query") else None
            response_data.response = msg.content
            
    return response_data

@app.get("/internal/runs/dlq")
async def get_dlq_runs(
    request: Request,
    _: None = Depends(require_internal_admin_token),
):
    """Admin endpoint to view DLQ."""
    redis_client = get_redis_client()
    dlq_items = await redis_client.xrange("stream:dlq:runs", "-", "+", count=100)
    
    results = []
    for message_id, message_data in dlq_items:
        results.append({
            "message_id": message_id,
            "data": message_data
        })
    return {"dlq": results}

@app.get("/internal/runs/stuck")
async def get_stuck_runs(
    _: None = Depends(require_internal_admin_token),
    db: Session = Depends(get_db),
):
    """Admin endpoint to see runs stuck in pending or running state."""
    # Check for runs stuck for more than 5 minutes
    now = datetime.now(timezone.utc)
    from sqlalchemy import func
    # Note: For SQLite/Postgres differences, standard filtering:
    # MVP approach: return runs still pending or running
    stuck = db.query(Run).filter(Run.status.in_(["pending", "running"])).all()
    
    return {"stuck_runs": [{"id": r.id, "status": r.status, "attempts": r.attempts, "created_at": r.created_at} for r in stuck]}

