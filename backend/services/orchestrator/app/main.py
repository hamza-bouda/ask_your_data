"""Conversation Orchestrator Service.

Coordinates the end-to-step conversational BI pipeline using LangGraph.
"""

from typing import Any, Optional, List
from fastapi import HTTPException, Depends
from pydantic import BaseModel
import uuid
from datetime import datetime

from contracts.service_factory import create_service_app

try:
    from app.models import ConversationState
    from app.graph import orchestrator_graph
    from app.database import create_tables, get_db
    from app.orm_models import Conversation, Message, Run
except ImportError:
    from backend.services.orchestrator.app.models import ConversationState
    from backend.services.orchestrator.app.graph import orchestrator_graph
    from backend.services.orchestrator.app.database import create_tables, get_db
    from backend.services.orchestrator.app.orm_models import Conversation, Message, Run

from sqlalchemy.orm import Session

app = create_service_app(service_name="orchestrator")

@app.on_event("startup")
def on_startup():
    create_tables()

# ── Request/Response Models ──────────────────────────────────────

class CreateConversationRequest(BaseModel):
    tenant_id: str
    user_id: str
    title: Optional[str] = None

class ConversationResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime

class SendMessageRequest(BaseModel):
    tenant_id: str
    user_id: str
    message: str

class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    payload: Optional[dict] = None
    created_at: datetime

class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse
    messages: List[MessageResponse]

class RunResponse(BaseModel):
    run_id: str
    status: str
    results: Optional[list[dict[str, Any]]] = None
    chart_spec: Optional[dict[str, Any]] = None
    semantic_plan: Optional[dict[str, Any]] = None
    clarification_options: Optional[list[dict[str, str]]] = None
    error_message: Optional[str] = None
    response: Optional[str] = None
    sql_draft: Optional[dict] = None


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/conversations", response_model=ConversationResponse)
async def create_conversation(body: CreateConversationRequest, db: Session = Depends(get_db)):
    """Create a new conversation."""
    conv = Conversation(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        title=body.title or "Nouvelle conversation"
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@app.get("/internal/conversations", response_model=List[ConversationResponse])
async def list_conversations(tenant_id: str, user_id: str, db: Session = Depends(get_db)):
    """List conversations for a user."""
    convs = db.query(Conversation).filter(
        Conversation.tenant_id == tenant_id,
        Conversation.user_id == user_id
    ).order_by(Conversation.updated_at.desc()).all()
    return convs

@app.get("/internal/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(conversation_id: str, tenant_id: str, user_id: str, db: Session = Depends(get_db)):
    """Get a conversation with its messages."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.tenant_id == tenant_id,
        Conversation.user_id == user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    return {
        "conversation": conv,
        "messages": conv.messages
    }

@app.post("/internal/conversations/{conversation_id}/messages", response_model=RunResponse)
async def send_message(conversation_id: str, body: SendMessageRequest, db: Session = Depends(get_db)):
    """Send a message and run the orchestrator."""
    conv = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.tenant_id == body.tenant_id,
        Conversation.user_id == body.user_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    # Auto-title on first message
    if len(conv.messages) == 0 and conv.title == "Nouvelle conversation":
        # Keep it simple, just take the first 30 chars
        conv.title = (body.message[:30] + '...') if len(body.message) > 30 else body.message
        db.add(conv)

    # Save user message
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=body.message
    )
    db.add(user_msg)
    
    # Create Run
    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        conversation_id=conversation_id,
        status="running"
    )
    db.add(run)
    db.commit()

    # Load chat history
    # Limit to last 10 messages for context
    history_msgs = db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(10).all()
    chat_history = [{"role": m.role, "content": m.content} for m in reversed(history_msgs)]

    initial_state = ConversationState(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        conversation_id=conversation_id,
        question=body.message,
        run_id=run_id,
        chat_history=chat_history
    )
    
    try:
        final_state_dict = orchestrator_graph.invoke(initial_state.model_dump())
        final_state = ConversationState(**final_state_dict)
    except Exception as exc:
        run.status = "error"
        run.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Orchestrator failed: {str(exc)}")
        
    run.status = final_state.status
    run.error_message = final_state.error_message
    
    # Save assistant message
    has_error = final_state.error_message is not None
    response_text = final_state.error_message if has_error else "Voici les résultats"
    
    # If the semantic router returned a direct response (e.g., unrelated greeting)
    if final_state.status == "unrelated" and final_state.results and len(final_state.results) > 0 and "response" in final_state.results[0]:
        response_text = final_state.results[0]["response"]
    elif final_state.status == "needs_clarification":
        response_text = "Je n'ai pas bien compris. Pouvez-vous préciser ?"
        
    payload = {
        "semantic_plan": final_state.semantic_plan,
        "results": final_state.results,
        "chart_spec": final_state.chart_spec,
        "sql_query": final_state.sql_query,
        "clarification_options": final_state.clarification_options,
        "error_message": final_state.error_message
    }
    
    ai_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=response_text,
        payload=payload
    )
    db.add(ai_msg)
    db.commit()
    
    return RunResponse(
        run_id=run_id,
        status=final_state.status,
        results=final_state.results,
        chart_spec=final_state.chart_spec,
        semantic_plan=final_state.semantic_plan,
        clarification_options=final_state.clarification_options,
        error_message=final_state.error_message,
        response=response_text,
        sql_draft={"sql_query": final_state.sql_query} if final_state.sql_query else None
    )

# ── Old Run Endpoints for SSE Support (if still needed) ───────────

@app.get("/internal/runs/{run_id}", response_model=RunResponse)
async def get_run_status(run_id: str, db: Session = Depends(get_db)):
    """Retrieve the status and results of a run."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    return RunResponse(
        run_id=run_id,
        status=run.status,
        error_message=run.error_message
    )
