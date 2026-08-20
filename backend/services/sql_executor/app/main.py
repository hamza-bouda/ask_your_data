"""SQL Executor Service.

Executes generated SQL queries against the target analytics database.
Enforces read-only safety constraints to prevent data modification.
"""

from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel

from contracts.service_factory import create_service_app

try:
    from app.executor import execute_query, SqlExecutionError
except ImportError:
    from backend.services.sql_executor.app.executor import execute_query, SqlExecutionError


app = create_service_app(service_name="sql_executor")

# ── Request/Response Models ──────────────────────────────────────

class ExecuteSqlRequest(BaseModel):
    sql_query: str
    tenant_id: str


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
        data = execute_query(sql_query=body.sql_query, tenant_id=body.tenant_id)
        return ExecuteSqlResponse(
            results=data,
            row_count=len(data)
        )
    except SqlExecutionError as exc:
        raise HTTPException(status_code=400, detail=exc.message)
