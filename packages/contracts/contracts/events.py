"""RunEvent — structured events emitted during a pipeline run so that
the Gateway can stream progress to the browser via SSE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RunEventType(StrEnum):
    """Exhaustive set of event types emitted by the Orchestrator."""

    RUN_STARTED = "run_started"
    CLASSIFYING = "classifying"
    RETRIEVAL_STARTED = "retrieval_started"
    RETRIEVAL_COMPLETED = "retrieval_completed"
    CLARIFICATION_REQUESTED = "clarification_requested"
    PLANNING = "planning"
    SQL_GENERATING = "sql_generating"
    SQL_VALIDATING = "sql_validating"
    QUERY_EXECUTING = "query_executing"
    VISUALIZATION_GENERATING = "visualization_generating"
    RESULT_READY = "result_ready"
    RUN_FAILED = "run_failed"
    RUN_COMPLETED = "run_completed"


class RunEvent(BaseModel):
    """A single lifecycle event within a pipeline run."""

    event_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique event identifier.",
    )
    run_id: str = Field(
        ...,
        description="Pipeline run this event belongs to.",
    )
    conversation_id: str = Field(
        ...,
        description="Conversation this run belongs to.",
    )
    status: str = Field(
        ...,
        description="Current status of the run (e.g. running, failed, completed).",
    )
    stage: str = Field(
        ...,
        description="Current stage of the run pipeline.",
    )
    event_type: RunEventType = Field(
        ...,
        description="Discriminator for the event payload.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data, guaranteed to be bounded and without sensitive chain-of-thought.",
    )
    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the event.",
    )
