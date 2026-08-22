"""State models for the LangGraph Conversation Orchestrator."""

from typing import Any, Optional
from pydantic import BaseModel


class ConversationState(BaseModel):
    """The state of a single conversation run through the orchestrator pipeline."""

    # Input
    tenant_id: str
    user_id: str
    source_id: Optional[str] = None
    conversation_id: str
    question: str
    run_id: str
    chat_history: Optional[list[dict[str, Any]]] = None

    # Pipeline data
    context: Optional[dict[str, Any]] = None
    semantic_plan: Optional[dict[str, Any]] = None
    sql_query: Optional[str] = None
    results: Optional[list[dict[str, Any]]] = None
    chart_spec: Optional[dict[str, Any]] = None
    response_text: Optional[str] = None

    # Answer Generator structured synthesis
    executive_summary: Optional[str] = None
    key_insights: Optional[list[str]] = None
    warnings: Optional[list[str]] = None
    suggested_followups: Optional[list[str]] = None

    # Clarification
    clarification_options: Optional[list[dict[str, str]]] = None

    # Error handling and repair
    error_message: Optional[str] = None
    repair_budget: int = 2

    status: str = "new"  # e.g., new, retrieved, planned, sql_generated, executed, visualized, answered, error
