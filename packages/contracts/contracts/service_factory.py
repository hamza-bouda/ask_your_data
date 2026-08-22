"""Shared FastAPI service factory.

Every microservice uses ``create_service_app()`` to get a FastAPI
instance pre-configured with:
- ``GET /health`` (liveness)
- ``GET /ready``  (readiness)
- Uniform ``ApiError`` exception handler
- ``X-Contract-Version`` response header
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from contracts.errors import ApiError

CONTRACT_VERSION = "1"


def create_service_app(
    *,
    service_name: str,
    service_version: str = "0.1.0",
    readiness_check: Callable[[], Awaitable[bool]] | None = None,
) -> FastAPI:
    """Return a FastAPI app with standard health/ready endpoints and error handling."""

    app = FastAPI(
        title=f"Ask Your Data — {service_name}",
        version=service_version,
    )

    # ── Middleware: inject contract version header ────────────────
    @app.middleware("http")
    async def add_contract_version(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Contract-Version"] = CONTRACT_VERSION
        return response

    import os
    import hmac

    @app.middleware("http")
    async def enforce_internal_admin_token(request: Request, call_next: Any) -> Any:
        if request.url.path.startswith("/internal/"):
            expected_token = os.getenv("INTERNAL_ADMIN_TOKEN")
            # If the token is configured, enforce it. (Local dev might not set it).
            if expected_token:
                req_token = request.headers.get("x-internal-admin-token")
                if not req_token or not hmac.compare_digest(req_token, expected_token):
                    return JSONResponse(status_code=404, content={"detail": "Not found"})
        return await call_next(request)

    # ── Exception handler: wrap all errors in ApiError ───────────
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        error = ApiError(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            detail=str(exc) if str(exc) else None,
            trace_id=request.headers.get("x-trace-id", ""),
            timestamp=datetime.now(timezone.utc),
        )
        return JSONResponse(
            status_code=500,
            content=error.model_dump(mode="json"),
            headers={"X-Contract-Version": CONTRACT_VERSION},
        )

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        error = ApiError(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            detail=str(exc.errors()),
            trace_id=request.headers.get("x-trace-id", ""),
            timestamp=datetime.now(timezone.utc),
        )
        return JSONResponse(
            status_code=422,
            content=error.model_dump(mode="json"),
            headers={"X-Contract-Version": CONTRACT_VERSION},
        )

    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail_val = str(exc.detail) if exc.detail is not None else None
        error = ApiError(
            code=f"HTTP_{exc.status_code}",
            message=detail_val or "HTTP Error",
            detail=detail_val,
            trace_id=request.headers.get("x-trace-id", ""),
            timestamp=datetime.now(timezone.utc),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error.model_dump(mode="json"),
            headers={"X-Contract-Version": CONTRACT_VERSION},
        )

    # ── Health & Ready ───────────────────────────────────────────
    @app.get("/health", tags=["infra"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": service_name,
            "version": service_version,
        }

    @app.get("/ready", tags=["infra"])
    async def ready() -> dict[str, str | bool]:
        if readiness_check is not None:
            is_ready = await readiness_check()
        else:
            is_ready = True
        return {
            "ready": is_ready,
            "service": service_name,
        }

    return app
