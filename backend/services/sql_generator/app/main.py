"""SQL Generator Service.

Translates natural language questions into executable PostgreSQL queries
based on provided database schemas.
"""

from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel

from contracts.service_factory import create_service_app

try:
    from app.generator import generate_sql, SqlResult
except ImportError:
    from backend.services.sql_generator.app.generator import generate_sql, SqlResult


app = create_service_app(service_name="sql_generator")


# ── Request Models ───────────────────────────────────────────────

class GenerateSqlRequest(BaseModel):
    query: str
    schema_definition: list[dict[str, Any]]


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/generate-sql", response_model=SqlResult)
async def generate_sql_endpoint(body: GenerateSqlRequest) -> SqlResult:
    """Generate a SQL query from natural language and schema."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    if not body.schema_definition:
        raise HTTPException(status_code=400, detail="Schema definition cannot be empty")
        
    return generate_sql(query=body.query, schema=body.schema_definition)
