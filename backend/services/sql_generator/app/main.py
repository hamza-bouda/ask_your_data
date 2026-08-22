"""SQL Generator Service.

Translates natural language questions into executable PostgreSQL queries
based on provided database schemas.
"""

from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics


try:
    from app.generator import generate_sql, repair_sql
    from app.models import SqlDraft
except ImportError:
    from backend.services.sql_generator.app.generator import generate_sql, repair_sql
    from backend.services.sql_generator.app.models import SqlDraft


app = create_service_app(service_name="sql_generator")

# Observability setup
setup_logging(service_name="sql_generator")
setup_tracing(service_name="sql_generator", app=app)
setup_metrics(app)



# ── Request Models ───────────────────────────────────────────────

class GenerateSqlRequest(BaseModel):
    query: str
    semantic_plan: dict[str, Any]
    schema_definition: dict[str, Any]
    chat_history: list[dict[str, Any]] = []

class RepairSqlRequest(BaseModel):
    query: str
    schema_definition: dict[str, Any]
    previous_sql: str
    error_message: str


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/generate-sql", response_model=SqlDraft)
async def generate_sql_endpoint(body: GenerateSqlRequest) -> SqlDraft:
    """Generate a SQL query from natural language and schema."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    if not body.schema_definition:
        raise HTTPException(status_code=400, detail="Schema definition cannot be empty")
        
    return generate_sql(query=body.query, semantic_plan=body.semantic_plan, schema=body.schema_definition, chat_history=body.chat_history)

@app.post("/internal/repair-sql", response_model=SqlDraft)
async def repair_sql_endpoint(body: RepairSqlRequest) -> SqlDraft:
    """Repair a broken SQL query."""
    if not body.previous_sql.strip():
        raise HTTPException(status_code=400, detail="Previous SQL cannot be empty")
        
    return repair_sql(
        query=body.query, 
        schema=body.schema_definition,
        previous_sql=body.previous_sql,
        error_message=body.error_message
    )
