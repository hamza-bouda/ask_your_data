"""Semantic Router Service.

Analyzes user queries to determine intent and find relevant data schemas.
Currently uses mocked logic to validate the architecture before integrating LLMs.
"""

from fastapi import HTTPException
from pydantic import BaseModel

from contracts.service_factory import create_service_app

try:
    from app.router import classify_intent, RouteResult
    from app.catalog import search_catalog, CatalogSearchResult
except ImportError:
    from backend.services.semantic_router.app.router import classify_intent, RouteResult
    from backend.services.semantic_router.app.catalog import search_catalog, CatalogSearchResult


app = create_service_app(service_name="semantic_router")


# ── Request Models ───────────────────────────────────────────────

class RouteRequest(BaseModel):
    query: str

class CatalogSearchRequest(BaseModel):
    query: str
    tenant_id: str


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/route", response_model=RouteResult)
async def route_query(body: RouteRequest) -> RouteResult:
    """Classify the intent of the user's query."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    return classify_intent(body.query)


@app.post("/internal/catalog/search", response_model=CatalogSearchResult)
async def catalog_search(body: CatalogSearchRequest) -> CatalogSearchResult:
    """Find relevant database schemas for the user's query."""
    if not body.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
        
    return search_catalog(query=body.query, tenant_id=body.tenant_id)
