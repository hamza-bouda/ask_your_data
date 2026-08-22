"""Answer Generator Service.

Generates business-oriented natural language explanations, executive summaries,
key insights, caveats, and follow-up suggestions from executed SQL results and chart specifications.
Includes deterministic offline fallbacks.
"""

import os
from typing import Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from contracts.llm import get_llm_provider, BaseLLMProvider, MockLLMProvider


class BusinessAnswer(BaseModel):
    """Structured response synthesized from executed SQL results."""

    answer: str = Field(
        description="Clear, professional business explanation answering the user's question directly."
    )
    executive_summary: str = Field(
        description="A concise 1-2 sentence executive summary of the main finding."
    )
    key_insights: list[str] = Field(
        default_factory=list,
        description="2 to 4 bullet points highlighting key numbers, trends, or outliers strictly from the data.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Any caveats, empty results, max limit truncations, or approximations.",
    )
    suggested_followups: list[str] = Field(
        default_factory=list,
        description="2 to 3 relevant follow-up questions the user might want to explore next.",
    )


def _build_deterministic_answer(
    question: str,
    results: list[dict[str, Any]],
    semantic_plan: Optional[dict[str, Any]] = None,
    chart_spec: Optional[dict[str, Any]] = None,
) -> BusinessAnswer:
    """Produces a deterministic structured answer when LLM is unavailable or offline."""
    if not results:
        return BusinessAnswer(
            answer="La requête n'a retourné aucun résultat pour les critères demandés.",
            executive_summary="Aucune donnée ne correspond aux filtres appliqués.",
            key_insights=["0 ligne retournée."],
            warnings=["Vérifiez vos filtres ou la période sélectionnée."],
            suggested_followups=[
                "Afficher la liste des données disponibles",
                "Élargir la période de recherche",
            ],
        )

    row_count = len(results)
    first_row = results[0]
    keys = list(first_row.keys())

    # Find numeric and categorical columns
    numeric_cols = [k for k, v in first_row.items() if isinstance(v, (int, float))]
    categorical_cols = [k for k, v in first_row.items() if isinstance(v, str)]

    insights = []
    insights.append(f"L'analyse porte sur un échantillon de {row_count} enregistrement(s).")

    if numeric_cols:
        num_col = numeric_cols[0]
        values = [r[num_col] for r in results if isinstance(r.get(num_col), (int, float))]
        if values:
            total = sum(values)
            avg = total / len(values)
            max_val = max(values)
            insights.append(f"Total pour '{num_col}' : {total:,.2f} (moyenne : {avg:,.2f}, maximum : {max_val:,.2f}).")

    if categorical_cols and numeric_cols:
        cat_col = categorical_cols[0]
        num_col = numeric_cols[0]
        top_item = max(results, key=lambda r: r.get(num_col, 0) if isinstance(r.get(num_col), (int, float)) else 0)
        insights.append(f"Principal contributeur : {top_item.get(cat_col)} ({top_item.get(num_col)}).")

    followups = [
        f"Voir l'évolution temporelle",
        f"Filtrer par catégorie ou dimension",
        f"Comparer avec la période précédente",
    ]

    warnings = []
    if row_count >= 1000:
        warnings.append("Résultats plafonnés à 1 000 lignes pour préserver les performances.")

    chart_title = (chart_spec or {}).get("title", "l'analyse")

    return BusinessAnswer(
        answer=f"Voici les résultats pour votre demande « {question} ».",
        executive_summary=f"Analyse réussie de {chart_title} avec {row_count} ligne(s) extraite(s).",
        key_insights=insights[:4],
        warnings=warnings,
        suggested_followups=followups[:3],
    )


class AnswerGenerator:
    """Object-oriented wrapper for Answer Generation."""

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm_provider = llm_provider

    def _format_results_sample(self, results: list[dict[str, Any]], max_rows: int = 20) -> str:
        if not results:
            return "Aucun résultat."
        sample = results[:max_rows]
        text = str(sample)
        if len(results) > max_rows:
            text += f" ... (tronqué : {len(results)} lignes au total, affichage des {max_rows} premières)"
        return text

    def generate(
        self,
        question: str,
        results: list[dict[str, Any]],
        sql_query: Optional[str] = None,
        semantic_plan: Optional[dict[str, Any]] = None,
        chart_spec: Optional[dict[str, Any]] = None,
    ) -> BusinessAnswer:
        return generate_business_answer(
            question=question,
            results=results,
            sql_query=sql_query,
            semantic_plan=semantic_plan,
            chart_spec=chart_spec,
            llm_provider=self.llm_provider,
        )


def generate_business_answer(
    question: str,
    results: list[dict[str, Any]],
    sql_query: Optional[str] = None,
    semantic_plan: Optional[dict[str, Any]] = None,
    chart_spec: Optional[dict[str, Any]] = None,
    llm_provider: Optional[BaseLLMProvider] = None,
) -> BusinessAnswer:
    """Synthesizes structured business insights with zero hallucination and fallback."""
    if not results:
        return _build_deterministic_answer(question, results, semantic_plan, chart_spec)

    provider = llm_provider or get_llm_provider()
    if isinstance(provider, MockLLMProvider) and getattr(provider, "canned_response", None) is None and llm_provider is None:
        return _build_deterministic_answer(question, results, semantic_plan, chart_spec)

    total_row_count = len(results)
    safe_sample = results[:20]

    system_prompt = (
        "You are an expert Chief Data Officer and executive BI analyst for 'Ask Your Data'.\n"
        "Your mission is to analyze query results and provide a structured, executive-grade business response.\n"
        "\nCRITICAL RULES:\n"
        "1. STRICT GROUNDING: State facts and numbers ONLY from the provided results. NEVER invent or hallucinate data.\n"
        "2. EXECUTIVE SUMMARY: Provide a concise 1-2 sentence high-level summary suitable for a C-level executive.\n"
        "3. KEY INSIGHTS: Extract 2 to 4 impactful bullet points (e.g., top performers, totals, percentage shares, anomalies).\n"
        "4. CAVEATS / WARNINGS: Explicitly mention if results are empty, if limits were reached, or if certain values are null.\n"
        "5. FOLLOW-UPS: Provide 2 to 3 highly actionable next questions the user can ask to dive deeper.\n"
        "6. TONE: Professional, concise, in French (matching user query language)."
    )

    human_prompt = (
        "Question utilisateur: {question}\n\n"
        "Plan sémantique: {semantic_plan}\n\n"
        "Requête SQL exécutée: {sql_query}\n\n"
        "Nombre total de lignes retournées: {total_count}\n\n"
        "Échantillon des résultats (jusqu'à 20 lignes):\n{results_sample}\n\n"
        "Spécification graphique: {chart_spec}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", human_prompt),
    ])

    try:
        provider = llm_provider or get_llm_provider()
        structured_llm = provider.with_structured_output(BusinessAnswer)
        chain = prompt | structured_llm

        answer = chain.invoke({
            "question": question,
            "semantic_plan": str(semantic_plan or {}),
            "sql_query": sql_query or "",
            "total_count": total_row_count,
            "results_sample": str(safe_sample),
            "chart_spec": str(chart_spec or {}),
        })
        return answer
    except Exception as e:
        print(f"Answer generation LLM call failed: {e}. Falling back to deterministic generation.")
        return _build_deterministic_answer(question, results, semantic_plan, chart_spec)
