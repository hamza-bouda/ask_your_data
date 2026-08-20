"""Semantic Router Logic (Mock Version).

Classifies user questions into specific intents.
In a real implementation, this would use a lightweight LLM (like GPT-3.5 or an open-source equivalent)
or a zero-shot classifier. Here we use simple heuristics to unblock architecture development.
"""

from enum import Enum
from pydantic import BaseModel


class Intent(str, Enum):
    DATA_QUERY = "DATA_QUERY"          # Wants to query data (e.g., "Combien d'utilisateurs ?")
    CHART_GENERATION = "CHART_GENERATION"  # Wants a chart (e.g., "Fais un graphique...")
    UNRELATED = "UNRELATED"            # Chit-chat or unrelated to the domain


class RouteResult(BaseModel):
    intent: Intent
    confidence: float


def classify_intent(query: str) -> RouteResult:
    """Classify the intent of a user query based on simple keyword heuristics."""
    q = query.lower()
    
    # Keywords indicating a chart request
    chart_keywords = ["graphe", "graphique", "dessine", "trace", "affiche", "chart", "plot"]
    if any(kw in q for kw in chart_keywords):
        return RouteResult(intent=Intent.CHART_GENERATION, confidence=0.9)
        
    # Keywords indicating unrelated queries
    unrelated_keywords = ["recette", "météo", "blague", "bonjour", "salut"]
    if any(kw in q for kw in unrelated_keywords):
        return RouteResult(intent=Intent.UNRELATED, confidence=0.85)
        
    # Default to data query
    return RouteResult(intent=Intent.DATA_QUERY, confidence=0.7)
