"""ApiError — uniform error envelope returned by every service.

All unhandled exceptions and known error conditions are serialized
into this shape so that the Gateway and frontend can rely on a
single error contract.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    """Standard error response shared across all services.

    Every HTTP error (4xx/5xx) MUST be wrapped in this model so
    that consumers can parse errors uniformly.
    """

    code: str = Field(
        ...,
        description="Machine-readable error code, e.g. 'VALIDATION_ERROR'.",
    )
    message: str = Field(
        ...,
        description="Human-readable error summary.",
    )
    detail: str | None = Field(
        default=None,
        description="Optional extended description or debug info.",
    )
    trace_id: str = Field(
        default="",
        description="OpenTelemetry trace ID for correlation.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the error occurred.",
    )
