"""LangGraph workflow definition for the Conversation Orchestrator."""

import httpx
from langgraph.graph import StateGraph, START, END
from observability import get_tracer

tracer = get_tracer("orchestrator_graph")


try:
    from app.models import ConversationState
except ImportError:
    from backend.services.orchestrator.app.models import ConversationState

# Internal service URLs (would be configurable via env vars in a real setup)
SQL_GENERATOR_URL = "http://sql-generator:8006"
SQL_EXECUTOR_URL = "http://sql-executor:8007"
SEMANTIC_ROUTER_URL = "http://semantic-router:8008"
VISUALIZATION_URL = "http://visualization:8005"

# ── Node Functions ───────────────────────────────────────────────




def retrieve_node(state: ConversationState) -> dict:
    with tracer.start_as_current_span("retrieve_node"):
        """Retrieves allowed schema context from the Catalog service."""
        try:
            response = httpx.post(f"{SEMANTIC_ROUTER_URL}/internal/catalog/search", json={
                "query": state.question,
                "tenant_id": state.tenant_id,
                "source_id": state.source_id,
            }, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        
            return {
                "status": "retrieved",
                "context": data
            }
        except Exception as e:
            print(f"Error retrieving schema: {e}")
            return {
                "status": "retrieved",
                "context": {"documents": []}
            }

def plan_node(state: ConversationState) -> dict:
    with tracer.start_as_current_span("plan_node"):
        """Creates a semantic plan for the query."""
        try:
            response = httpx.post(f"{SEMANTIC_ROUTER_URL}/internal/plan", json={
                "query": state.question,
                "chat_history": state.chat_history,
                "context": state.context
            }, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        
            intent = data.get("intent")
            if intent == "AMBIGUOUS":
                return {
                    "status": "needs_clarification",
                    "clarification_options": [{"id": str(i), "text": opt} for i, opt in enumerate(data.get("clarification_options", []))]
                }
        
            if intent == "UNRELATED":
                context_data = state.context or {}
                tables_info = context_data.get("tables", [])
                example = "« liste les tables disponibles »"
                if tables_info:
                    first_table = tables_info[0]
                    table_name = first_table if isinstance(first_table, str) else first_table.get("name")
                    if table_name:
                         example = f"« montre-moi les données de {table_name} »"

                return {
                    "status": "unrelated",
                    "semantic_plan": data,
                    "results": [{"response": f"Je peux vous aider à explorer les données autorisées, créer une analyse ou un graphique. Par exemple : {example}."}]
                }

            if intent == "CATALOG_QUERY":
                tables = data.get("source_tables", [])
                response_text = (
                    "Tables autorisées disponibles : " + ", ".join(tables) + "."
                    if tables else
                    "Aucune table autorisée n'est disponible pour le moment. Demandez à un administrateur d'autoriser des tables dans le catalogue."
                )
                return {
                    "status": "catalog_response",
                    "semantic_plan": data,
                    "response_text": response_text,
                }
            
            return {
                "status": "planned",
                "semantic_plan": data
            }
        except Exception as e:
            print(f"Error planning: {e}")
            return {"status": "planned", "semantic_plan": {"intent": "DATA_QUERY"}}
def generate_sql_node(state: ConversationState) -> dict:
    with tracer.start_as_current_span("generate_sql_node"):
        """Calls the SQL Generator service."""
        try:
            response = httpx.post(f"{SQL_GENERATOR_URL}/internal/generate-sql", json={
                "query": state.question,
                "semantic_plan": state.semantic_plan if state.semantic_plan else {},
                "schema_definition": state.context if state.context else {},
                "chat_history": state.chat_history
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
    with tracer.start_as_current_span("execute_sql_node"):
        """Calls the SQL Executor service."""
        if not state.sql_query:
            return {"status": "error", "error_message": "No SQL query to execute"}
        
        try:
            response = httpx.post(f"{SQL_EXECUTOR_URL}/internal/execute-sql", json={
                "sql_query": state.sql_query,
                "tenant_id": state.tenant_id,
                "source_id": state.source_id,
            }, timeout=10.0)
        
            # If execution fails (e.g. safety check), trigger repair
            if response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get("detail", "Unknown execution error")
            
                # Policy or strict safety errors shouldn't be blindly retried
                if "policy" in error_msg.lower() or "denied" in error_msg.lower() or "forbidden" in error_msg.lower():
                    return {
                        "status": "error",
                        "error_message": f"La requête a été bloquée par les règles de sécurité : {error_msg}"
                    }
                
                return {
                    "status": "sql_error",
                    "error_message": error_msg
                }            
            response.raise_for_status()
            data = response.json()
        
            return {
                "status": "executed",
                "results": data.get("results", []),
                "error_message": None
            }
        except Exception as e:
            return {
                "status": "error",
                "error_message": f"SQL Execution failed: {str(e)}"
            }

def visualization_node(state: ConversationState) -> dict:
    with tracer.start_as_current_span("visualization_node"):
        """Calls the Visualization service to get a deterministic chart spec."""
        if not state.results:
            return {"status": "visualized"}
        
        try:
            response = httpx.post(f"{VISUALIZATION_URL}/internal/chart-spec", json={
                "results": state.results,
                "semantic_plan": state.semantic_plan,
                "question": state.question
            }, timeout=5.0)
        
            response.raise_for_status()
            chart_spec = response.json()
        
            return {
                "status": "visualized",
                "chart_spec": chart_spec
            }
        except Exception as e:
            # Fallback to table if visualization service fails
            print(f"Visualization service failed: {e}")
            return {
                "status": "visualized",
                "chart_spec": {
                    "chart_type": "table",
                    "title": "Résultats tabulaires (Fallback)",
                    "reason": "Le service de visualisation est indisponible.",
                    "warnings": ["Erreur lors de la génération du graphique."]
                }
            }

def repair_node(state: ConversationState) -> dict:
    with tracer.start_as_current_span("repair_node"):
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

def after_plan(state: ConversationState) -> str:
    if state.status == "needs_clarification":
        return "end"
    if state.status == "unrelated":
        return "end"
    if state.status == "catalog_response":
        return "end"
    return "generate_sql"

def after_execute(state: ConversationState) -> str:
    if state.status == "sql_error":
        return "repair"
    elif state.status == "error":
        return "end"
    return "visualization"

def after_repair(state: ConversationState) -> str:
    if state.status == "error":
        return "end"
    return "generate_sql"


# ── Build Graph ──────────────────────────────────────────────────

builder = StateGraph(ConversationState)

builder.add_node("retrieve", retrieve_node)
builder.add_node("plan", plan_node)
builder.add_node("generate_sql", generate_sql_node)
builder.add_node("execute_sql", execute_sql_node)
builder.add_node("repair", repair_node)
builder.add_node("visualization", visualization_node)

builder.add_edge(START, "retrieve")

builder.add_edge("retrieve", "plan")
builder.add_conditional_edges("plan", after_plan, {
    "end": END,
    "generate_sql": "generate_sql"
})
builder.add_edge("generate_sql", "execute_sql")

builder.add_conditional_edges("execute_sql", after_execute, {
    "repair": "repair",
    "visualization": "visualization",
    "end": END
})

builder.add_edge("visualization", END)

builder.add_conditional_edges("repair", after_repair, {
    "end": END,
    "generate_sql": "generate_sql"
})

orchestrator_graph = builder.compile()
