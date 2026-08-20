"""LangGraph workflow definition for the Conversation Orchestrator."""

import httpx
from langgraph.graph import StateGraph, START, END

try:
    from app.models import ConversationState
except ImportError:
    from backend.services.orchestrator.app.models import ConversationState

# Internal service URLs (would be configurable via env vars in a real setup)
SQL_GENERATOR_URL = "http://localhost:8003"
SQL_EXECUTOR_URL = "http://localhost:8004"

# ── Node Functions ───────────────────────────────────────────────

def classify_node(state: ConversationState) -> dict:
    """Classifies the user query to check if it's ambiguous."""
    # Mock behavior: if question contains "clarify", we trigger clarification
    if "clarify" in state.question.lower():
        return {
            "status": "needs_clarification",
            "clarification_options": [
                {"id": "1", "text": "Do you mean Revenue from Subscriptions?"},
                {"id": "2", "text": "Do you mean Revenue from Ads?"}
            ]
        }
    return {"status": "classified"}

def retrieve_node(state: ConversationState) -> dict:
    """Retrieves allowed schema context from the Catalog service."""
    # Mock retrieval
    return {
        "status": "retrieved",
        "context": {"tables": ["users", "sales"]}
    }

def plan_node(state: ConversationState) -> dict:
    """Creates a semantic plan for the query."""
    # Mock planning
    return {
        "status": "planned",
        "semantic_plan": {"metric": "count", "dimension": "users"}
    }

def generate_sql_node(state: ConversationState) -> dict:
    """Calls the SQL Generator service."""
    try:
        # We use a synchronous httpx call for simplicity in nodes, 
        # though async nodes are fully supported by LangGraph.
        response = httpx.post(f"{SQL_GENERATOR_URL}/internal/generate-sql", json={
            "question": state.question,
            "schema_context": state.context if state.context else {}
        }, timeout=10.0)
        
        response.raise_for_status()
        data = response.json()
        
        return {
            "status": "sql_generated",
            "sql_query": data.get("sql_query", "")
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"SQL Generation failed: {str(e)}"
        }

def execute_sql_node(state: ConversationState) -> dict:
    """Calls the SQL Executor service."""
    if not state.sql_query:
        return {"status": "error", "error_message": "No SQL query to execute"}
        
    try:
        response = httpx.post(f"{SQL_EXECUTOR_URL}/internal/execute-sql", json={
            "sql_query": state.sql_query,
            "tenant_id": state.tenant_id
        }, timeout=10.0)
        
        # If execution fails (e.g. safety check), trigger repair
        if response.status_code == 400:
            error_data = response.json()
            return {
                "status": "sql_error",
                "error_message": error_data.get("detail", "Unknown execution error")
            }
            
        response.raise_for_status()
        data = response.json()
        
        return {
            "status": "executed",
            "results": data.get("results", [])
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"SQL Execution failed: {str(e)}"
        }

def repair_node(state: ConversationState) -> dict:
    """Attempts to repair a failed SQL query within budget."""
    if state.repair_budget > 0:
        return {
            "status": "planned",  # Go back to generation
            "repair_budget": state.repair_budget - 1,
            "error_message": f"Retrying. Previous error: {state.error_message}"
        }
    else:
        return {
            "status": "error",
            "error_message": "Repair budget exceeded. " + (state.error_message or "")
        }


# ── Graph Edges ──────────────────────────────────────────────────

def after_classify(state: ConversationState) -> str:
    if state.status == "needs_clarification":
        return "end" # Pause or return clarification options
    return "retrieve"

def after_execute(state: ConversationState) -> str:
    if state.status == "sql_error":
        return "repair"
    elif state.status == "error":
        return "end"
    return "end"

def after_repair(state: ConversationState) -> str:
    if state.status == "error":
        return "end"
    return "generate_sql"


# ── Build Graph ──────────────────────────────────────────────────

builder = StateGraph(ConversationState)

builder.add_node("classify", classify_node)
builder.add_node("retrieve", retrieve_node)
builder.add_node("plan", plan_node)
builder.add_node("generate_sql", generate_sql_node)
builder.add_node("execute_sql", execute_sql_node)
builder.add_node("repair", repair_node)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", after_classify, {
    "end": END,
    "retrieve": "retrieve"
})
builder.add_edge("retrieve", "plan")
builder.add_edge("plan", "generate_sql")
builder.add_edge("generate_sql", "execute_sql")

builder.add_conditional_edges("execute_sql", after_execute, {
    "repair": "repair",
    "end": END
})

builder.add_conditional_edges("repair", after_repair, {
    "end": END,
    "generate_sql": "generate_sql"
})

orchestrator_graph = builder.compile()
