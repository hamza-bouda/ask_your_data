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
    AREA = "area"
    BAR = "bar"
    HORIZONTAL_BAR = "horizontal_bar"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    RADAR = "radar"
    METRIC = "metric"
    STACKED_BAR = "stacked_bar"
    HEATMAP = "heatmap"
    WATERFALL = "waterfall"
    HISTOGRAM = "histogram"


class ChartSpec(BaseModel):
    """Specification consumed by the frontend to render a chart.

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
    x_field: str | None = Field(
        default=None,
        description="Column name mapped to the x axis or label.",
    )
    y_field: str | None = Field(
        default=None,
        description="Column name mapped to the y axis or value.",
    )
    series_field: str | None = Field(
        default=None,
        description="Column name used to group data into multiple series.",
    )
    aggregation: str | None = Field(
        default=None,
        description="Aggregation applied (e.g. sum, count) if applicable.",
    )
    reason: str = Field(
        default="",
        description="Short justification of the recommended visualization.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about granularity, volume, missing values, etc.",
    )
