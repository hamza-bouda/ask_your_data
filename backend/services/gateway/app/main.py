"""API Gateway Service — Single public entry point.

Responsibilities:
- Authenticates requests via Identity Service
- Enforces Rate Limiting via Redis
- Injects Correlation IDs for tracing
- Proxies requests to Conversation Orchestrator
- Exposes SSE stream for real-time frontend updates
"""

from __future__ import annotations

import json
from typing import AsyncGenerator
import httpx
from fastapi import Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from contracts.service_factory import create_service_app
from contracts.tenant import TenantContext

try:
    from app.config import ORCHESTRATOR_URL
    from app.dependencies import get_tenant_context
    from app.rate_limit import init_redis, close_redis, check_rate_limit
    from app.middleware import CorrelationIdMiddleware
except ImportError:
    from backend.services.gateway.app.config import ORCHESTRATOR_URL
    from backend.services.gateway.app.dependencies import get_tenant_context
    from backend.services.gateway.app.rate_limit import init_redis, close_redis, check_rate_limit
    from backend.services.gateway.app.middleware import CorrelationIdMiddleware


# ── Create App & Add Middleware ─────────────────────────────────

app = create_service_app(service_name="gateway")
app.add_middleware(CorrelationIdMiddleware)

@app.on_event("startup")
async def startup():
    await init_redis()

@app.on_event("shutdown")
async def shutdown():
    await close_redis()


# ── Request/Response Models ─────────────────────────────────────

class CreateConversationRequest(BaseModel):
    title: str | None = None

class SendMessageRequest(BaseModel):
    message: str


# ── Endpoints ───────────────────────────────────────────────────

@app.post("/v1/conversations")
async def create_conversation(
    request: Request,
    body: CreateConversationRequest,
    context: TenantContext = Depends(get_tenant_context)
):
    """Create a new conversation."""
    await check_rate_limit(context.user_id)
    correlation_id = request.state.correlation_id
    
    # Proxy to orchestrator
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/internal/conversations",
                json={
                    "tenant_id": context.tenant_id,
                    "user_id": context.user_id,
                    "title": body.title,
                },
                headers={"X-Correlation-ID": correlation_id},
                timeout=5.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Orchestrator service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Orchestrator error")


@app.post("/v1/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: Request,
    body: SendMessageRequest,
    context: TenantContext = Depends(get_tenant_context)
):
    """Send a message in an existing conversation."""
    await check_rate_limit(context.user_id)
    correlation_id = request.state.correlation_id
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/internal/conversations/{conversation_id}/messages",
                json={
                    "tenant_id": context.tenant_id,
                    "user_id": context.user_id,
                    "message": body.message,
                },
                headers={"X-Correlation-ID": correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Orchestrator service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Orchestrator error")


# ── SSE Streaming ───────────────────────────────────────────────

async def _orchestrator_event_stream(run_id: str, correlation_id: str) -> AsyncGenerator[str, None]:
    """Connect to the Orchestrator's internal event stream and yield SSE chunks."""
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", 
                f"{ORCHESTRATOR_URL}/internal/runs/{run_id}/events",
                headers={"X-Correlation-ID": correlation_id},
                timeout=None
            ) as response:
                if response.status_code != 200:
                    yield f"event: error\ndata: {json.dumps({'detail': 'Failed to connect to stream'})}\n\n"
                    return
                
                # Forward chunks exactly as received (should be in SSE format)
                async for chunk in response.aiter_text():
                    yield chunk
    except Exception as exc:
        yield f"event: error\ndata: {json.dumps({'detail': 'Stream interrupted'})}\n\n"


@app.get("/v1/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    context: TenantContext = Depends(get_tenant_context)
):
    """Stream events for a specific run using Server-Sent Events (SSE)."""
    # Note: no rate limit check here because SSE is a single long-lived connection, 
    # but could be added if needed to prevent opening too many streams.
    
    correlation_id = request.state.correlation_id
    
    return StreamingResponse(
        _orchestrator_event_stream(run_id, correlation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Essential for Nginx to not buffer SSE
        }
    )
