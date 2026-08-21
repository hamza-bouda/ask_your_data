"""Visualization Service — deterministic chart specification.

Phase 01: skeleton with health/ready endpoints only.
Phase 09 adds ChartSpec generation from ResultSet + SemanticPlan,
deterministic chart type selection.
"""

from typing import Any, Optional
from fastapi import Request
from pydantic import BaseModel

from contracts.service_factory import create_service_app
try:
    from contracts.chart import ChartSpec, ChartType
except ImportError:
    # During some tests without correct PYTHONPATH
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../packages/contracts"))
    from contracts.chart import ChartSpec, ChartType

app = create_service_app(service_name="visualization")


class ChartSpecRequest(BaseModel):
    results: list[dict[str, Any]]
    semantic_plan: Optional[dict[str, Any]] = None
    question: Optional[str] = None


def _is_numeric(val: Any) -> bool:
    if isinstance(val, (int, float)):
        return True
    if isinstance(val, str):
        try:
            float(val)
            return True
        except ValueError:
            pass
    return False


def _is_date_or_time(val: Any) -> bool:
    if isinstance(val, str):
        # Very simple heuristic for dates
        return "-" in val and len(val) >= 10 and val[:4].isdigit()
    return False


@app.post("/internal/chart-spec", response_model=ChartSpec)
async def generate_chart_spec(request: ChartSpecRequest):
    """Generates a ChartSpec deterministically based on data shape."""
    data = request.results
    
    if not data:
        return ChartSpec(
            chart_type=ChartType.TABLE,
            title="Aucune donnée",
            reason="Le jeu de résultats est vide.",
            warnings=["Pas de données à afficher."]
        )

    keys = list(data[0].keys())
    
    # 1. Single row, single numeric value -> Metric
    if len(data) == 1 and len(keys) == 1 and _is_numeric(data[0][keys[0]]):
        return ChartSpec(
            chart_type=ChartType.METRIC,
            title=keys[0].capitalize(),
            y_field=keys[0],
            reason="Un seul nombre retourné, affichage en métrique."
        )
        
    # Over 50 rows -> Table
    if len(data) > 50:
        return ChartSpec(
            chart_type=ChartType.TABLE,
            title="Tableau de résultats",
            reason="Volume de données trop important pour un graphique lisible.",
            warnings=["Plus de 50 lignes retournées, affichage tabulaire forcé pour la lisibilité."]
        )

    # Analyze columns
    numeric_cols = []
    date_cols = []
    cat_cols = []
    
    for key in keys:
        # Check first non-null row
        val = None
        for row in data:
            if row.get(key) is not None:
                val = row[key]
                break
                
        if val is None:
            continue
            
        if _is_numeric(val):
            numeric_cols.append(key)
        elif _is_date_or_time(val):
            date_cols.append(key)
        else:
            cat_cols.append(key)

    # 2. Date/Time + Numeric -> Line
    if len(date_cols) == 1 and len(numeric_cols) >= 1:
        return ChartSpec(
            chart_type=ChartType.LINE,
            title="Évolution temporelle",
            x_field=date_cols[0],
            y_field=numeric_cols[0],
            reason="Présence d'une dimension temporelle et d'une mesure."
        )

    # 3. Category + Numeric -> Bar or Pie
    if len(cat_cols) >= 1 and len(numeric_cols) >= 1:
        cat = cat_cols[0]
        num = numeric_cols[0]
        
        # Check number of distinct categories
        unique_cats = set(row.get(cat) for row in data if row.get(cat) is not None)
        
        if len(unique_cats) <= 6:
            return ChartSpec(
                chart_type=ChartType.PIE,
                title="Répartition",
                x_field=cat,
                y_field=num,
                reason="Peu de catégories distinctes, idéal pour un diagramme circulaire."
            )
        else:
            return ChartSpec(
                chart_type=ChartType.BAR,
                title="Comparaison par catégorie",
                x_field=cat,
                y_field=num,
                reason="Comparaison de plusieurs catégories via un diagramme en barres."
            )

    # Fallback to Table
    return ChartSpec(
        chart_type=ChartType.TABLE,
        title="Résultats tabulaires",
        reason="La structure des données ne correspond pas à un modèle de graphique clair.",
        warnings=["Affichage tabulaire par défaut."]
    )
