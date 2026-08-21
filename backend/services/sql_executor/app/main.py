"""SQL Executor Service.

Executes generated SQL queries against the target analytics database.
Enforces read-only safety constraints to prevent data modification.
"""

from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics


try:
    from app.executor import execute_query, SqlExecutionError
except ImportError:
    from backend.services.sql_executor.app.executor import execute_query, SqlExecutionError


app = create_service_app(service_name="sql_executor")

# Observability setup
setup_logging(service_name="sql_executor")
setup_tracing(service_name="sql_executor", app=app)
setup_metrics(app)


# ── Request/Response Models ──────────────────────────────────────

class ExecuteSqlRequest(BaseModel):
    sql_query: str
    tenant_id: str
    source_id: str | None = None


class ExecuteSqlResponse(BaseModel):
    results: list[dict[str, Any]]
    row_count: int


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/execute-sql", response_model=ExecuteSqlResponse)
async def execute_sql_endpoint(body: ExecuteSqlRequest) -> ExecuteSqlResponse:
    """Validate and execute a SQL query safely."""
    if not body.sql_query.strip():
        raise HTTPException(status_code=400, detail="SQL query cannot be empty")
        
    try:
        data = execute_query(sql_query=body.sql_query, tenant_id=body.tenant_id, source_id=body.source_id)
        return ExecuteSqlResponse(
            results=data,
            row_count=len(data)
        )
    except SqlExecutionError as exc:
        raise HTTPException(status_code=400, detail=exc.message)

@app.get("/internal/audit")
def get_audit_logs(tenant_id: str):
    """Retrieve audit logs for a given tenant."""
    try:
        from app.connection_manager import _global_engine
    except ImportError:
        from backend.services.sql_executor.app.connection_manager import _global_engine
        
    from sqlalchemy import text
    
    with _global_engine.connect() as conn:
        res = conn.execute(
            text("SELECT id, sql_hash, decision, duration_ms, row_count, status, error, created_at FROM execution_audits WHERE tenant_id = :tenant_id ORDER BY created_at DESC LIMIT 100"),
            {"tenant_id": tenant_id}
        )
        logs = []
        for row in res:
            logs.append({
                "id": row[0],
                "sql_hash": row[1],
                "decision": row[2],
                "duration_ms": row[3],
                "row_count": row[4],
                "status": row[5],
                "error": row[6],
                "created_at": str(row[7])
            })
        return {"audits": logs}
