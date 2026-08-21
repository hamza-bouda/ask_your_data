"""Semantic Router Service.

Analyzes user queries to determine intent and find relevant data schemas.
"""

from fastapi import HTTPException
from pydantic import BaseModel
from typing import Any, List, Optional

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics


try:
    from app.router import create_semantic_plan, SemanticPlanOut
    from app.catalog import search_catalog, CatalogSearchResult
except ImportError:
    from backend.services.semantic_router.app.router import create_semantic_plan, SemanticPlanOut
    from backend.services.semantic_router.app.catalog import search_catalog, CatalogSearchResult


app = create_service_app(service_name="semantic_router")

# Observability setup
setup_logging(service_name="semantic_router")
setup_tracing(service_name="semantic_router", app=app)
setup_metrics(app)



# ── Request Models ───────────────────────────────────────────────

class PlanRequest(BaseModel):
    query: str
    context: dict = {}
    chat_history: List[dict] = []

class CatalogSearchRequest(BaseModel):
    query: str
    tenant_id: str
    source_id: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/plan", response_model=SemanticPlanOut)
async def plan_query(body: PlanRequest) -> SemanticPlanOut:
    """Classify intent and generate semantic plan."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    result_dict = create_semantic_plan(body.query, body.context, body.chat_history)
    return SemanticPlanOut(**result_dict)


@app.post("/internal/catalog/search", response_model=CatalogSearchResult)
async def catalog_search(body: CatalogSearchRequest) -> CatalogSearchResult:
    """Find relevant database schemas for the user's query."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    return search_catalog(query=body.query, tenant_id=body.tenant_id, source_id=body.source_id)
