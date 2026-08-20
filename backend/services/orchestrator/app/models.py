"""State models for the LangGraph Conversation Orchestrator."""

import operator
from typing import Any, Annotated, Optional
from pydantic import BaseModel, Field

class ConversationState(BaseModel):
    """The state of a single conversation run through the orchestrator pipeline."""
    
    # Input
    tenant_id: str
    question: str
    run_id: str
    
    # Pipeline data
    context: Optional[dict[str, Any]] = None
    semantic_plan: Optional[dict[str, Any]] = None
    sql_query: Optional[str] = None
    results: Optional[list[dict[str, Any]]] = None
    
    # Clarification
    clarification_options: Optional[list[dict[str, str]]] = None
    
    # Error handling and repair
    error_message: Optional[str] = None
    repair_budget: int = 2
    
    # We use Annotated with operator.setitem to allow LangGraph to update fields
    # Wait, LangGraph in Python usually takes a TypedDict or Pydantic model. 
    # With Pydantic, we just define the schema. The standard State graph will replace fields.
    
    status: str = "new"  # e.g., new, clarified, retrieved, planned, sql_generated, validated, executed, error
