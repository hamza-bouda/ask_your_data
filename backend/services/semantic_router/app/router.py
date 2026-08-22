"""Semantic Router Logic.

Classifies user questions into specific intents using DeepSeek API via LangChain and outputs a structured Semantic Plan.
"""
import os
from enum import Enum
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

class Intent(str, Enum):
    DATA_QUERY = "DATA_QUERY"          
    CATALOG_QUERY = "CATALOG_QUERY"
    CHART_GENERATION = "CHART_GENERATION"  
    UNRELATED = "UNRELATED"            
    AMBIGUOUS = "AMBIGUOUS"            

class SemanticPlanOut(BaseModel):
    intent: Intent = Field(description="The classified intent of the user query.")
    confidence: float = Field(description="Confidence score between 0 and 1.")
    clarification_options: list[str] = Field(
        default_factory=list,
        description="If intent is AMBIGUOUS, provide exactly 2 to 4 specific interpretation options."
    )
    source_tables: list[str] = Field(default_factory=list, description="List of table names selected from context.")
    metric: str | None = Field(None, description="The core business metric being requested.")
    dimensions: list[str] = Field(default_factory=list, description="Columns or attributes used to group or slice.")
    filters: list[str] = Field(default_factory=list, description="Specific conditions applied.")
    period: str | None = Field(None, description="The time period for the query.")
    grain: str | None = Field(None, description="The temporal or spatial grain.")
    reasoning: str | None = Field(None, description="Brief explanation of why these tables and metrics were selected.")


def _get_llm():
    return ChatOpenAI(
        model="deepseek-chat", 
        api_key=os.getenv("DEEPSEEK_API_KEY"), 
        base_url="https://api.deepseek.com/v1",
        max_retries=2
    )


def _is_catalog_request(query: str) -> bool:
    """Recognise schema discovery requests without relying on an LLM guess."""
    normalized = query.lower()
    catalog_terms = ("table", "schema", "schéma", "catalog", "catalogue", "colonne", "column")
    discovery_terms = ("liste", "list", "nom", "name", "quelle", "quelles", "which", "existe", "available", "disponible", "montre", "affiche", "show")
    return any(term in normalized for term in catalog_terms) and any(term in normalized for term in discovery_terms)


def _context_table_names(context: dict) -> list[str]:
    return [
        table if isinstance(table, str) else table["name"]
        for table in context.get("tables", [])
        if isinstance(table, str) or table.get("name")
    ]


def _mock_semantic_plan(query: str, context: dict) -> dict:
    """Deterministic, offline plan used only by the test runtime."""
    normalized = query.lower()
    if any(greeting in normalized for greeting in ("bonjour", "salut", "hello")):
        return {"intent": "UNRELATED", "confidence": 1.0, "reasoning": "Mock greeting classification."}
    if normalized in {"montre-moi les données", "montre moi les données", "show me the data"}:
        return {
            "intent": "AMBIGUOUS", "confidence": 1.0,
            "clarification_options": ["Quelle table et quelle mesure souhaitez-vous analyser ?", "Voulez-vous voir un aperçu de la table principale ?"],
            "reasoning": "Mock detected an underspecified data request.",
        }
    tables = _context_table_names(context)
    if not tables:
        return {
            "intent": "AMBIGUOUS", "confidence": 1.0,
            "clarification_options": ["Choisissez une source et une table autorisée.", "Demandez à l'administrateur d'ajouter des tables."],
            "reasoning": "No catalog table is available to the deterministic mock.",
        }
    wants_chart = any(term in normalized for term in ("graph", "graphe", "chart", "visualisation"))
    return {
        "intent": "CHART_GENERATION" if wants_chart else "DATA_QUERY",
        "confidence": 1.0,
        "source_tables": [tables[0]],
        "metric": "row_count",
        "dimensions": [],
        "filters": [],
        "reasoning": "Deterministic mock plan for the offline end-to-end workflow.",
    }

def create_semantic_plan(query: str, context: dict, chat_history: list) -> dict:
    """Classify the intent and generate a semantic plan based on context."""
    if _is_catalog_request(query):
        tables = _context_table_names(context)
        return {
            "intent": "CATALOG_QUERY",
            "confidence": 1.0,
            "source_tables": tables,
            "reasoning": "The user is asking to discover the authorized database schema.",
        }

    if os.getenv("LLM_PROVIDER", "").lower() == "mock":
        return _mock_semantic_plan(query, context)

    system_msg = (
        "You are a semantic router for a BI conversational agent. "
        "Your job is to classify the user's query into one of the following intents:\n"
        "- DATA_QUERY: User is asking a clear question about data.\n"
        "- CATALOG_QUERY: User asks to list or describe available tables or columns (never classify as UNRELATED if they mention tables, data, or schema).\n"
        "- CHART_GENERATION: User explicitly asks for a graph, chart, or plot.\n"
        "- UNRELATED: General chatter, hellos, or questions completely outside a business context.\n"
        "- AMBIGUOUS: The query is too vague, has multiple interpretations, or is missing critical context. "
        "If AMBIGUOUS, you MUST provide exactly 2 to 4 'clarification_options' with specific, actionable ways to interpret it.\n"
        "\nIMPORTANT CONTEXT:\n"
        "You must use 'history' to resolve conversational references (e.g. 'ce graphique', 'et pour 2024 ?', 'ces clients'). "
        "If the user asks a follow-up question, use the 'payload' (semantic_plan, sql_query) from the history to infer the missing tables, metrics, or filters.\n"
        "\nIf the intent is DATA_QUERY or CHART_GENERATION, use the provided schema context (which includes tables, relations, metrics) "
        "to fill in 'source_tables', 'metric', 'dimensions', 'filters', 'period', 'grain' and 'reasoning'. "
        "If you cannot determine the metric or tables even with history, classify as AMBIGUOUS."
    )
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        ("human", "Context: {context}\n\nHistory: {history}\n\nQuery: {query}")
    ])
    
    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(SemanticPlanOut)
        chain = prompt | structured_llm
        result = chain.invoke({
            "query": query, 
            "context": str(context), 
            "history": str(chat_history)
        })
        return result.model_dump()
    except Exception as e:
        print(f"Error creating semantic plan: {e}")
        # A routing failure must never turn into an ungrounded SQL attempt.
        return {
            "intent": "AMBIGUOUS",
            "confidence": 0.0,
            "clarification_options": ["Réessayez votre question dans quelques instants."],
            "reasoning": "Semantic routing is temporarily unavailable.",
        }
