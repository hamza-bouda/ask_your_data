"""Semantic Layer Contracts.

Defines the structure of the Semantic Plan produced by the Semantic Router.
"""

from typing import List, Optional
from pydantic import BaseModel, Field

class SemanticPlan(BaseModel):
    """A structured plan defining how to answer the user's analytical query."""
    intent: str = Field(description="The classified intent, e.g., DATA_QUERY, CHART_GENERATION, UNRELATED, AMBIGUOUS.")
    source_tables: List[str] = Field(
        default_factory=list,
        description="List of table names selected from the catalog to answer the query."
    )
    metric: Optional[str] = Field(
        None,
        description="The core business metric being requested (e.g., 'revenue', 'active users')."
    )
    dimensions: List[str] = Field(
        default_factory=list,
        description="Columns or attributes used to group or slice the metric."
    )
    filters: List[str] = Field(
        default_factory=list,
        description="Specific conditions or filters applied to the query."
    )
    period: Optional[str] = Field(
        None,
        description="The time period for the query if applicable (e.g., 'last 30 days', '2023')."
    )
    grain: Optional[str] = Field(
        None,
        description="The temporal or spatial grain (e.g., 'daily', 'by country')."
    )
    confidence: float = Field(
        1.0,
        description="Confidence score in the interpretation (0.0 to 1.0)."
    )
    reasoning: Optional[str] = Field(
        None,
        description="Brief explanation of why these tables and metrics were selected."
    )
    catalog_version: Optional[int] = Field(
        None,
        description="The version of the catalog schema used for this plan."
    )
