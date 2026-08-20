"""ChartSpec — deterministic chart specification produced by the
Visualization service from a ResultSet and a SemanticPlan.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChartType(StrEnum):
    """Supported visualization types."""

    TABLE = "table"
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    SCATTER = "scatter"
    AREA = "area"


class ChartSpec(BaseModel):
    """Specification consumed by the frontend to render a Plotly chart.

    Built deterministically by the Visualization service — no LLM
    involved in choosing the chart type.
    """

    chart_type: ChartType = Field(
        default=ChartType.TABLE,
        description="Recommended chart type based on data shape.",
    )
    title: str = Field(
        default="",
        description="Human-readable chart title.",
    )
    x_axis: str | None = Field(
        default=None,
        description="Column name mapped to the x axis.",
    )
    y_axis: str | None = Field(
        default=None,
        description="Column name mapped to the y axis.",
    )
    series: list[str] = Field(
        default_factory=list,
        description="Column names for multi-series charts.",
    )
    data: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Row-oriented result data.",
    )
    options: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra Plotly layout/config options.",
    )
