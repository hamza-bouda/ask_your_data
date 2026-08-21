import os

def patch_worker():
    filepath = "backend/services/orchestrator/app/worker.py"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    if "observability" in content:
        print("Worker already patched.")
        return

    # 1. Imports at top
    import_statement = """import structlog
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

"""
    # Replace standard logging
    content = content.replace("logging.basicConfig(level=logging.INFO)", "")
    content = content.replace('logger = logging.getLogger("worker")', import_statement)

    # 2. Patch process_message
    
    # We want to wrap the body of process_message in a span
    # The signature is: async def process_message(r: redis.Redis, message_id: str, data: dict):
    # We'll inject context extraction right after extracting data.
    
    extract_code = """    run_id = data.get("run_id")
    tenant_id = data.get("tenant_id")
    user_id = data.get("user_id")
    conversation_id = data.get("conversation_id")
    correlation_id = data.get("correlation_id", "")
    question = data.get("question", "")

    # OpenTelemetry context extraction
    ctx = extract_context(data)
    
    with tracer.start_as_current_span("process_message", context=ctx) as span:
        span.set_attribute("tenant_id", tenant_id or "")
        span.set_attribute("correlation_id", correlation_id)
        span.set_attribute("run_id", run_id or "")
        # Do not log question directly to avoid leaking PII/secrets

        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            run_id=run_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id
        )

        with WORKER_TASK_DURATION.time():
"""
    
    # Find the data extraction block
    data_extraction = """    run_id = data.get("run_id")
    tenant_id = data.get("tenant_id")
    user_id = data.get("user_id")
    conversation_id = data.get("conversation_id")
    correlation_id = data.get("correlation_id", "")
    question = data.get("question", "")"""
    
    content = content.replace(data_extraction, extract_code)
    
    # Indent the rest of the function by 8 spaces (since we added 2 'with' blocks)
    # The rest of the function starts at `if not run_id:` and ends before `async def main():`
    
    lines = content.splitlines()
    new_lines = []
    in_process = False
    in_with_blocks = False
    for line in lines:
        if line.startswith("    if not run_id:"):
            in_with_blocks = True
        
        if line.startswith("async def main():"):
            in_with_blocks = False
            
        if in_with_blocks and line.startswith("    ") and not line.startswith("        span.set_attribute"):
            if len(line.strip()) > 0:
                new_lines.append("        " + line)
            else:
                new_lines.append("")
        else:
            new_lines.append(line)
            
    content = "\\n".join(new_lines)
    
    # Also add metric increments
    content = content.replace('run.status = "error"', 'run.status = "error"\\n                WORKER_TASKS_PROCESSED.labels(status="error").inc()')
    content = content.replace('await r.xadd(DLQ_STREAM, data)', 'await r.xadd(DLQ_STREAM, data)\\n                WORKER_DLQ_MESSAGES.inc()')
    content = content.replace('run.attempts += 1', 'run.attempts += 1\\n                if run.attempts > 1:\\n                    WORKER_RETRIES.inc()')
    content = content.replace('logger.info(f"Run {run_id} completed successfully")', 'logger.info(f"Run {run_id} completed successfully")\\n                WORKER_TASKS_PROCESSED.labels(status="success").inc()')
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print("Patched worker.py")

if __name__ == "__main__":
    patch_worker()
