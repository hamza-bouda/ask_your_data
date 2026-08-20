"""Conversation Orchestrator Service.

Coordinates the end-to-step conversational BI pipeline using LangGraph.
"""

from typing import Any, Optional
from fastapi import HTTPException
from pydantic import BaseModel
import uuid

from contracts.service_factory import create_service_app

try:
    from app.models import ConversationState
    from app.graph import orchestrator_graph
except ImportError:
    from backend.services.orchestrator.app.models import ConversationState
    from backend.services.orchestrator.app.graph import orchestrator_graph

app = create_service_app(service_name="orchestrator")

# In-memory store for runs (in a real app, LangGraph Checkpointer + PostgreSQL would be used)
_runs = {}


# ── Request/Response Models ──────────────────────────────────────

class RunRequest(BaseModel):
    tenant_id: str
    question: str


class RunResponse(BaseModel):
    run_id: str
    status: str
    results: Optional[list[dict[str, Any]]] = None
    clarification_options: Optional[list[dict[str, str]]] = None
    error_message: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/runs", response_model=RunResponse)
async def start_run(body: RunRequest) -> RunResponse:
    """Start a new conversation run through the orchestrator pipeline."""
    run_id = str(uuid.uuid4())
    
    initial_state = ConversationState(
        tenant_id=body.tenant_id,
        question=body.question,
        run_id=run_id
    )
    
    # Execute the graph synchronously for this version.
    # In a real environment with long-running steps, we would use `.ainvoke()` 
    # and a background worker, streaming results back via SSE.
    try:
        final_state_dict = orchestrator_graph.invoke(initial_state.model_dump())
        final_state = ConversationState(**final_state_dict)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Orchestrator failed: {str(exc)}")
        
    _runs[run_id] = final_state
    
    return RunResponse(
        run_id=run_id,
        status=final_state.status,
        results=final_state.results,
        clarification_options=final_state.clarification_options,
        error_message=final_state.error_message
    )


@app.get("/internal/runs/{run_id}", response_model=RunResponse)
async def get_run_status(run_id: str) -> RunResponse:
    """Retrieve the status and results of a run."""
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Run not found")
        
    return RunResponse(
        run_id=run_id,
        status=state.status,
        results=state.results,
        clarification_options=state.clarification_options,
        error_message=state.error_message
    )
