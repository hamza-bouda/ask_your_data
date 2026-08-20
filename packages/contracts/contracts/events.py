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

    RUN_STARTED = "run.started"
    CLASSIFYING = "run.classifying"
    CLARIFICATION_REQUESTED = "run.clarification_requested"
    RETRIEVING = "run.retrieving"
    PLANNING = "run.planning"
    SQL_GENERATED = "run.sql_generated"
    SQL_VALIDATED = "run.sql_validated"
    SQL_REJECTED = "run.sql_rejected"
    EXECUTING = "run.executing"
    REPAIRING = "run.repairing"
    RESULT_READY = "run.result_ready"
    RUN_FAILED = "run.failed"
    RUN_COMPLETED = "run.completed"


class RunEvent(BaseModel):
    """A single lifecycle event within a pipeline run.

    Streamed to the browser via SSE through the Gateway.  The payload
    is intentionally ``dict[str, Any]`` so each event type can carry
    its own domain-specific data without inflating the base contract.
    """

    event_id: UUID = Field(
        default_factory=uuid4,
        description="Unique event identifier.",
    )
    run_id: UUID = Field(
        ...,
        description="Pipeline run this event belongs to.",
    )
    event_type: RunEventType = Field(
        ...,
        description="Discriminator for the event payload.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data.",
    )
    trace_id: str = Field(
        default="",
        description="OpenTelemetry trace ID for correlation.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the event.",
    )
