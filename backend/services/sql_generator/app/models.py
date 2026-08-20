"""Pydantic models for the SQL Generator LLM structured output."""

from typing import Optional
from pydantic import BaseModel, Field

class SqlDraft(BaseModel):
    """The structured output from the LLM when generating SQL."""
    
    intent: str = Field(description="A brief description of what the user wants.")
    metric: str = Field(description="The core metric being calculated (e.g., 'count', 'sum').")
    dimensions: list[str] = Field(
        default_factory=list,
        description="The columns used to group or slice the data."
    )
    filters: list[str] = Field(
        default_factory=list,
        description="Any specific filters applied to the query."
    )
    sql_query: str = Field(description="The executable PostgreSQL query.")
    confidence: float = Field(description="Confidence score between 0 and 1.")
    explanation: Optional[str] = Field(
        None, 
        description="Brief explanation of how the query works or any assumptions made."
    )
