"""QueryRequest — the contract for submitting a natural-language
question that should be translated into SQL, executed, and returned.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contracts.tenant import TenantContext


class QueryRequest(BaseModel):
    """Payload sent by the Gateway to the Orchestrator.

    Encapsulates the user question, the conversation it belongs to,
    the target datasource, and the resolved tenant context.
    """

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language question from the user.",
    )
    conversation_id: UUID = Field(
        default_factory=uuid4,
        description="Conversation this question belongs to.",
    )
    datasource_id: str = Field(
        ...,
        min_length=1,
        description="Target datasource to query against.",
    )
    tenant_context: TenantContext = Field(
        ...,
        description="Resolved tenant context from Identity service.",
    )
