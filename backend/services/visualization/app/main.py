"""Visualization Service — deterministic chart specification.

The service selects a safe chart specification from a result set and the
user's explicit request. Rendering is handled by the ECharts frontend.
"""

from typing import Any, Optional
from fastapi import Request
from pydantic import BaseModel

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics

try:
    from contracts.chart import ChartSpec, ChartType
except ImportError:
    # During some tests without correct PYTHONPATH
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), "../../../../packages/contracts"))
    from contracts.chart import ChartSpec, ChartType

app = create_service_app(service_name="visualization")

# Observability setup
setup_logging(service_name="visualization")
setup_tracing(service_name="visualization", app=app)
setup_metrics(app)



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


def _requested_chart_type(question: str | None) -> ChartType | None:
    """Honor an explicit user choice when it is compatible with the result set."""
    normalized = (question or "").lower()
    if any(term in normalized for term in ("sous forme de tableau", "affiche le tableau", "vue tableau", "as a table", "table view")):
        return ChartType.TABLE
    if any(term in normalized for term in ("camembert", "pie chart", "pie chart", "secteur")):
        return ChartType.PIE
    if any(term in normalized for term in ("donut", "doughnut", "anneau")):
        return ChartType.DONUT
    if any(term in normalized for term in ("barre horizontale", "horizontal bar", "horizontal")):
        return ChartType.HORIZONTAL_BAR
    if any(term in normalized for term in ("barre", "bar chart")):
        return ChartType.BAR
    if any(term in normalized for term in ("aire", "area chart")):
        return ChartType.AREA
    if any(term in normalized for term in ("courbe", "ligne", "line chart", "evolution", "évolution")):
        return ChartType.LINE
    if any(term in normalized for term in ("nuage", "scatter", "dispersion")):
        return ChartType.SCATTER
    if any(term in normalized for term in ("radar", "toile")):
        return ChartType.RADAR
    if any(term in normalized for term in ("empilé", "stacked")):
        return ChartType.STACKED_BAR
    if any(term in normalized for term in ("carte de chaleur", "heatmap")):
        return ChartType.HEATMAP
    if any(term in normalized for term in ("cascade", "waterfall")):
        return ChartType.WATERFALL
    if "histogramme" in normalized and "bar" not in normalized:
        return ChartType.HISTOGRAM
    return None

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
    requested_type = _requested_chart_type(request.question)

    if requested_type == ChartType.TABLE:
        return ChartSpec(
            chart_type=ChartType.TABLE,
            title="Tableau de résultats",
            reason="L'utilisateur a demandé explicitement un affichage tabulaire.",
        )
    
    # 1. Single row, single numeric value -> Metric
    if len(data) == 1 and len(keys) == 1 and _is_numeric(data[0][keys[0]]):
        return ChartSpec(
            chart_type=ChartType.METRIC,
            title=keys[0].capitalize(),
            y_field=keys[0],
            reason="Un seul nombre retourné, affichage en métrique."
        )
        
    # Keep the automatic mode readable, but honour an explicit chart choice.
    if len(data) > 50 and not requested_type:
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

    # 2. Date/Time + Numeric -> line/area, unless the user explicitly chose
    # another compatible visualisation.
    if len(date_cols) == 1 and len(numeric_cols) >= 1:
        return ChartSpec(
            chart_type=requested_type if requested_type in (ChartType.LINE, ChartType.AREA) else ChartType.LINE,
            title="Évolution temporelle" if requested_type != ChartType.AREA else "Évolution temporelle (aire)",
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
        
        if requested_type in (ChartType.PIE, ChartType.DONUT, ChartType.BAR, ChartType.HORIZONTAL_BAR, ChartType.RADAR):
            return ChartSpec(
                chart_type=requested_type,
                title={
                    ChartType.PIE: "Répartition (camembert)",
                    ChartType.DONUT: "Répartition (anneau)",
                    ChartType.HORIZONTAL_BAR: "Comparaison par catégorie",
                    ChartType.RADAR: "Comparaison radar",
                }.get(requested_type, "Comparaison par catégorie"),
                x_field=cat,
                y_field=num,
                reason="Type de graphique demandé explicitement par l'utilisateur.",
                warnings=["Le résultat contient de nombreuses catégories ; appliquez un filtre ou demandez un Top N pour une lecture optimale."] if len(unique_cats) > 12 else []
            )
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

    # 4. Two numerical measures -> scatter plot.
    if requested_type == ChartType.SCATTER and len(numeric_cols) >= 2:
        return ChartSpec(
            chart_type=ChartType.SCATTER,
            title="Nuage de points",
            x_field=numeric_cols[0],
            y_field=numeric_cols[1],
            reason="Deux mesures numériques permettent un nuage de points."
        )

    # --- Validations spécifiques pour les nouveaux types demandés ---
    if requested_type == ChartType.STACKED_BAR:
        if len(cat_cols) >= 1 and len(numeric_cols) >= 1:
            return ChartSpec(
                chart_type=ChartType.STACKED_BAR,
                title="Barres empilées",
                x_field=cat_cols[0],
                y_field=numeric_cols[0],
                reason="Type de graphique demandé explicitement par l'utilisateur."
            )
        else:
            return ChartSpec(
                chart_type=ChartType.TABLE,
                title="Tableau de résultats",
                reason="Le graphique en barres empilées nécessite au moins une catégorie et une mesure.",
                warnings=["Impossible d'afficher un graphique empilé avec ces données."]
            )

    if requested_type == ChartType.HEATMAP:
        if len(cat_cols) + len(date_cols) >= 1 and len(numeric_cols) >= 1:
            return ChartSpec(
                chart_type=ChartType.HEATMAP,
                title="Carte de chaleur",
                x_field=date_cols[0] if date_cols else cat_cols[0],
                y_field=numeric_cols[0],
                reason="Type de graphique demandé explicitement."
            )
        else:
            return ChartSpec(
                chart_type=ChartType.TABLE,
                title="Tableau de résultats",
                reason="La carte de chaleur nécessite au moins une dimension et une mesure.",
                warnings=["Impossible d'afficher une carte de chaleur avec ces données."]
            )

    if requested_type == ChartType.WATERFALL:
        if (len(cat_cols) >= 1 or len(date_cols) >= 1) and len(numeric_cols) >= 1:
            return ChartSpec(
                chart_type=ChartType.WATERFALL,
                title="Graphique en cascade",
                x_field=date_cols[0] if date_cols else cat_cols[0],
                y_field=numeric_cols[0],
                reason="Type de graphique demandé explicitement."
            )
        else:
            return ChartSpec(
                chart_type=ChartType.TABLE,
                title="Tableau de résultats",
                reason="Le graphique en cascade nécessite une dimension et une mesure.",
                warnings=["Impossible d'afficher un graphique en cascade avec ces données."]
            )

    if requested_type == ChartType.HISTOGRAM:
        if len(numeric_cols) >= 1:
            return ChartSpec(
                chart_type=ChartType.HISTOGRAM,
                title="Histogramme",
                y_field=numeric_cols[0],
                reason="Type de graphique demandé explicitement."
            )
        else:
            return ChartSpec(
                chart_type=ChartType.TABLE,
                title="Tableau de résultats",
                reason="L'histogramme nécessite au moins une mesure numérique.",
                warnings=["Impossible d'afficher un histogramme sans données numériques."]
            )

    # Fallback to Table
    return ChartSpec(
        chart_type=ChartType.TABLE,
        title="Résultats tabulaires",
        reason="La structure des données ne correspond pas à un modèle de graphique clair.",
        warnings=["Affichage tabulaire par défaut."]
    )
