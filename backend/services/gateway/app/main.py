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
from observability import setup_logging, setup_tracing, setup_metrics

from contracts.tenant import TenantContext
from observability import inject_context

try:
    from app.config import ORCHESTRATOR_URL, CORS_ALLOW_ORIGINS
    from app.dependencies import get_tenant_context, require_admin
    from app.rate_limit import init_redis, close_redis, check_rate_limit
    from app.middleware import CorrelationIdMiddleware
except ImportError:
    from backend.services.gateway.app.config import ORCHESTRATOR_URL, CORS_ALLOW_ORIGINS
    from backend.services.gateway.app.dependencies import get_tenant_context, require_admin
    from backend.services.gateway.app.rate_limit import init_redis, close_redis, check_rate_limit
    from backend.services.gateway.app.middleware import CorrelationIdMiddleware


# ── Create App & Add Middleware ─────────────────────────────────
from fastapi.middleware.cors import CORSMiddleware

app = create_service_app(service_name="gateway")

# Observability setup
setup_logging(service_name="gateway")
setup_tracing(service_name="gateway", app=app)
setup_metrics(app)

app.add_middleware(CorrelationIdMiddleware)
from app.middleware import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS so frontend can call Gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await init_redis()

@app.on_event("shutdown")
async def shutdown():
    await close_redis()

# ── Request/Response Models ─────────────────────────────────────
class ChatRequest(BaseModel):
    message: str

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/v1/auth/login")
async def login_proxy(body: LoginRequest):
    """Proxy login request to identity service."""
    try:
        from app.config import IDENTITY_URL
    except ImportError:
        from backend.services.gateway.app.config import IDENTITY_URL
        
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{IDENTITY_URL}/v1/auth/login",
                json={"username": body.username, "password": body.password},
                timeout=5.0
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid username or password")
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Identity service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Identity error")


class RegisterRequest(BaseModel):
    connection_string: str
    name: str | None = None
    source_id: str | None = None


class SourceUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None

@app.post("/api/v1/catalog/register")
async def register_proxy(body: RegisterRequest, request: Request, context: TenantContext = Depends(require_admin)):
    """Proxy catalog register request to catalog service."""
    try:
        CATALOG_URL = "http://catalog:8002"
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{CATALOG_URL}/api/v1/catalog/register",
                json=body.model_dump(),
                headers=inject_context({"X-Tenant-Id": context.tenant_id, "X-User-Id": context.user_id, "X-Correlation-ID": request.state.correlation_id}),
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Catalog service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Catalog error")

@app.get("/api/v1/catalog/source")
async def get_source_proxy(request: Request, context: TenantContext = Depends(require_viewer)):
    """Proxy catalog source request to catalog service."""
    try:
        CATALOG_URL = "http://catalog:8002"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CATALOG_URL}/api/v1/catalog/source",
                headers=inject_context({"X-Tenant-Id": context.tenant_id, "X-Correlation-ID": request.state.correlation_id, "X-Source-Id": request.headers.get("x-source-id", "")}),
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Catalog service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Catalog error")


@app.get("/api/v1/catalog/sources")
async def list_sources_proxy(request: Request, context: TenantContext = Depends(require_viewer)):
    """Expose tenant-owned source metadata so analysts can select their scope."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://catalog:8002/api/v1/catalog/sources",
                headers=inject_context({"X-Tenant-Id": context.tenant_id, "X-Correlation-ID": request.state.correlation_id}),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Catalog service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Catalog error")

@app.get("/api/v1/catalog/tables")
async def get_tables_proxy(request: Request, context: TenantContext = Depends(require_viewer)):
    """Proxy catalog tables request to catalog service."""
    try:
        CATALOG_URL = "http://catalog:8002"
        
        async with httpx.AsyncClient() as client:
            is_admin = str("admin" in context.roles).lower()
            resp = await client.get(
                f"{CATALOG_URL}/api/v1/catalog/tables",
                headers=inject_context({"X-Tenant-Id": context.tenant_id, "X-Correlation-ID": request.state.correlation_id, "X-Is-Admin": is_admin, "X-Source-Id": request.headers.get("x-source-id", "")}),
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Catalog service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Catalog error")

@app.get("/api/v1/catalog/tables/{table_name}/preview")
async def preview_table_proxy(table_name: str, request: Request, limit: int = 10, context: TenantContext = Depends(require_viewer)):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://catalog:8002/api/v1/catalog/tables/{table_name}/preview",
                params={"limit": limit},
                headers=inject_context({"X-Tenant-Id": context.tenant_id, "X-Correlation-ID": request.state.correlation_id, "X-Source-Id": request.headers.get("x-source-id", "")}),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Catalog service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Catalog preview unavailable")

@app.get("/v1/conversations")
async def list_conversations(
    request: Request,
    context: TenantContext = Depends(require_viewer)
):
    """List conversations for the current user."""
    correlation_id = request.state.correlation_id
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ORCHESTRATOR_URL}/internal/conversations",
                params={"tenant_id": context.tenant_id, "user_id": context.user_id},
                headers=inject_context({"X-Correlation-ID": correlation_id}),
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Orchestrator error")


@app.get("/v1/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    context: TenantContext = Depends(require_viewer)
):
    """Get a specific conversation."""
    correlation_id = request.state.correlation_id
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ORCHESTRATOR_URL}/internal/conversations/{conversation_id}",
                params={"tenant_id": context.tenant_id, "user_id": context.user_id},
                headers=inject_context({"X-Correlation-ID": correlation_id}),
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Orchestrator error")


# ── Internal Endpoints ─────────────────────────────────────


class CreateConversationRequest(BaseModel):
    title: str | None = None

class SendMessageRequest(BaseModel):
    message: str


# ── Endpoints ───────────────────────────────────────────────────

@app.post("/v1/conversations")
async def create_conversation(
    request: Request,
    body: CreateConversationRequest,
    context: TenantContext = Depends(require_analyst)
):
    """Create a new conversation."""
    await check_rate_limit(context.user_id, action="run", tenant_id=context.tenant_id)
    correlation_id = request.state.correlation_id
    
    # Proxy to orchestrator
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/internal/conversations",
                json={
                    "tenant_id": context.tenant_id,
                    "user_id": context.user_id,
                    "source_id": request.headers.get("x-source-id") or None,
                    "title": body.title,
                },
                headers=inject_context({"X-Correlation-ID": correlation_id}),
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
    context: TenantContext = Depends(require_analyst)
):
    """Send a message in an existing conversation."""
    await check_rate_limit(context.user_id, action="run", tenant_id=context.tenant_id)
    correlation_id = request.state.correlation_id
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/internal/conversations/{conversation_id}/messages",
                json={
                    "tenant_id": context.tenant_id,
                    "user_id": context.user_id,
                    "source_id": request.headers.get("x-source-id") or None,
                    "message": body.message,
                },
                headers=inject_context({"X-Correlation-ID": correlation_id}),
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Orchestrator service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Orchestrator error")


# ── SSE Streaming ───────────────────────────────────────────────

async def _orchestrator_event_stream(run_id: str, tenant_id: str, user_id: str, correlation_id: str) -> AsyncGenerator[str, None]:
    """Connect to the Orchestrator's internal event stream and yield SSE chunks."""
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET", 
                f"{ORCHESTRATOR_URL}/internal/runs/{run_id}/events",
                params={"tenant_id": tenant_id, "user_id": user_id},
                headers=inject_context({"X-Correlation-ID": correlation_id}),
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
    context: TenantContext = Depends(require_viewer)
):
    """Stream events for a specific run using Server-Sent Events (SSE)."""
    # Note: no rate limit check here because SSE is a single long-lived connection, 
    # but could be added if needed to prevent opening too many streams.
    
    correlation_id = request.state.correlation_id
    
    return StreamingResponse(
        _orchestrator_event_stream(run_id, context.tenant_id, context.user_id, correlation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Essential for Nginx to not buffer SSE
        }
    )

@app.get("/v1/runs/{run_id}")
async def get_run(
    run_id: str,
    request: Request,
    context: TenantContext = Depends(require_viewer)
):
    """Get status and results of a run."""
    correlation_id = request.state.correlation_id
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ORCHESTRATOR_URL}/internal/runs/{run_id}",
                params={"tenant_id": context.tenant_id, "user_id": context.user_id},
                headers=inject_context({"X-Correlation-ID": correlation_id}),
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Orchestrator service unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Orchestrator error")


@app.get("/v1/results")
async def list_results(
    request: Request,
    offset: int = 0,
    limit: int = 50,
    context: TenantContext = Depends(require_viewer),
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ORCHESTRATOR_URL}/internal/results",
                params={"tenant_id": context.tenant_id, "user_id": context.user_id, "source_id": request.headers.get("x-source-id") or None, "offset": offset, "limit": limit},
                headers=inject_context({"X-Correlation-ID": request.state.correlation_id}),
                timeout=15.0,
            )
            response.raise_for_status()
            return response.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Orchestrator unavailable")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Orchestrator error")


# ── Admin Datasource Endpoints ─────────────────────────────────
class PolicyUpdateRequest(BaseModel):
    is_allowed: bool


@app.get('/v1/datasources')
async def get_datasources(request: Request, context: TenantContext = Depends(require_admin)):
    try:
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{CATALOG_URL}/api/v1/catalog/sources',
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Is-Admin': 'true'},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json().get("sources", [])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.patch('/v1/datasources/{source_id}')
async def update_datasource(source_id: str, body: SourceUpdateRequest, request: Request, context: TenantContext = Depends(require_admin)):
    try:
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f'{CATALOG_URL}/api/v1/catalog/sources/{source_id}',
                json=body.model_dump(exclude_none=True),
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Is-Admin': 'true'},
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail='Catalog service unavailable')
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.json().get('detail', 'Catalog error'))

@app.post('/v1/datasources/{source_id}/sync')
async def sync_datasource(source_id: str, request: Request, context: TenantContext = Depends(require_admin)):
    try:
        await check_rate_limit(context.user_id, action="sync", tenant_id=context.tenant_id)
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f'{CATALOG_URL}/api/v1/catalog/sync',
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Source-Id': source_id},
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get('/v1/datasources/{source_id}/catalog')
async def get_datasource_catalog(source_id: str, request: Request, context: TenantContext = Depends(require_admin)):
    try:
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{CATALOG_URL}/api/v1/catalog/tables',
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Is-Admin': 'true', 'X-Source-Id': source_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.patch('/v1/datasources/{source_id}/catalog/tables/{table_id}')
async def patch_table_policy(source_id: str, table_id: int, body: PolicyUpdateRequest, request: Request, context: TenantContext = Depends(require_admin)):
    try:
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f'{CATALOG_URL}/api/v1/catalog/tables/{table_id}',
                json=body.model_dump(),
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Source-Id': source_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.patch('/v1/datasources/{source_id}/catalog/tables/{table_id}/columns/{column_id}')
async def patch_column_policy(source_id: str, table_id: int, column_id: int, body: PolicyUpdateRequest, request: Request, context: TenantContext = Depends(require_admin)):
    try:
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f'{CATALOG_URL}/api/v1/catalog/columns/{column_id}',
                json=body.model_dump(),
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Source-Id': source_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get('/v1/audit')
async def get_audit_logs_proxy(request: Request, context: TenantContext = Depends(require_admin)):
    """Aggregate audit logs from catalog, sql_executor, and orchestrator."""
    import asyncio
    try:
        CATALOG_URL = 'http://catalog:8002'
        SQL_EXECUTOR_URL = 'http://sql-executor:8003'
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        
        async with httpx.AsyncClient() as client:
            headers = {
                'x-tenant-id': context.tenant_id,
                'x-user-id': context.user_id,
                'x-correlation-id': request.state.correlation_id,
            }
            # Add internal admin token to bypass internal route guards
            import os
            expected_token = os.getenv("INTERNAL_ADMIN_TOKEN")
            if expected_token:
                headers['x-internal-admin-token'] = expected_token
            
            # Fetch all three concurrently
            req_catalog = client.get(f'{CATALOG_URL}/api/v1/catalog/audit', headers=headers)
            req_sql = client.get(f'{SQL_EXECUTOR_URL}/internal/audit', params={"tenant_id": context.tenant_id}, headers=headers)
            req_export = client.get(f'{ORCHESTRATOR_URL}/internal/audit/export', params={"tenant_id": context.tenant_id}, headers=headers)
            
            res_catalog, res_sql, res_export = await asyncio.gather(req_catalog, req_sql, req_export, return_exceptions=True)
            
            all_audits = []
            
            if not isinstance(res_catalog, Exception) and res_catalog.status_code == 200:
                catalog_audits = res_catalog.json().get("audits", [])
                for a in catalog_audits:
                    a["type"] = "catalog_policy"
                    a["action"] = a.get("action", "")
                    all_audits.append(a)
                    
            if not isinstance(res_sql, Exception) and res_sql.status_code == 200:
                sql_audits = res_sql.json().get("audits", [])
                for a in sql_audits:
                    a["type"] = "sql_execution"
                    a["action"] = "query_" + a.get("status", "").lower()
                    a["target"] = "sql_query"
                    a["timestamp"] = a.pop("created_at", None)
                    a["user_id"] = "system" # SQL Executor doesn't currently log user_id directly
                    all_audits.append(a)
                    
            if not isinstance(res_export, Exception) and res_export.status_code == 200:
                export_audits = res_export.json().get("audits", [])
                for a in export_audits:
                    a["type"] = "data_export"
                    a["action"] = "export_" + a.get("status", "").lower()
                    a["target"] = "message_" + a.get("source_message_id", "")
                    all_audits.append(a)
                    
            # Sort by timestamp descending
            all_audits.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            return {"audits": all_audits}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch audit logs")

@app.get('/v1/admin/health/runs/stuck')
async def get_stuck_runs_proxy(request: Request, context: TenantContext = Depends(require_admin)):
    try:
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{ORCHESTRATOR_URL}/internal/runs/stuck',
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get('/v1/admin/health/runs/dlq')
async def get_dlq_runs_proxy(request: Request, context: TenantContext = Depends(require_admin)):
    try:
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{ORCHESTRATOR_URL}/internal/runs/dlq',
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

class SemanticMetricRequest(BaseModel):
    name: str
    description: str | None = None
    sql_expression: str

@app.post('/v1/datasources/{source_id}/metrics')
async def create_metric_proxy(source_id: str, body: SemanticMetricRequest, request: Request, context: TenantContext = Depends(require_admin)):
    try:
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f'{CATALOG_URL}/api/v1/catalog/metrics',
                json=body.model_dump(),
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Source-Id': source_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get('/v1/datasources/{source_id}/metrics')
async def get_metrics_proxy(source_id: str, request: Request, context: TenantContext = Depends(require_admin)):
    try:
        CATALOG_URL = 'http://catalog:8002'
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{CATALOG_URL}/api/v1/catalog/metrics',
                headers={'X-Tenant-Id': context.tenant_id, 'X-User-Id': context.user_id, 'X-Correlation-ID': request.state.correlation_id, 'X-Source-Id': source_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# --- Dashboards & Export Proxy ---

@app.post("/v1/dashboards")
async def create_dashboard(request: Request, context: TenantContext = Depends(require_analyst)):
    try:
        body = await request.json()
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f'{ORCHESTRATOR_URL}/internal/dashboards',
                params={'tenant_id': context.tenant_id, 'user_id': context.user_id, 'source_id': request.headers.get("x-source-id") or None},
                json=body,
                headers={'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@app.get("/v1/dashboards")
async def get_dashboards(request: Request, context: TenantContext = Depends(require_viewer)):
    try:
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{ORCHESTRATOR_URL}/internal/dashboards',
                params={'tenant_id': context.tenant_id, 'user_id': context.user_id, 'source_id': request.headers.get("x-source-id") or None},
                headers={'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@app.get("/v1/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str, request: Request, context: TenantContext = Depends(require_viewer)):
    try:
        is_admin = str("admin" in context.roles or "manager" in context.roles).lower()
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f'{ORCHESTRATOR_URL}/internal/dashboards/{dashboard_id}',
                params={'tenant_id': context.tenant_id, 'user_id': context.user_id, 'is_admin': is_admin, 'source_id': request.headers.get("x-source-id") or None},
                headers={'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@app.patch("/v1/dashboards/{dashboard_id}")
async def update_dashboard(dashboard_id: str, request: Request, context: TenantContext = Depends(require_analyst)):
    try:
        body = await request.json()
        is_admin = str("admin" in context.roles or "manager" in context.roles).lower()
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f'{ORCHESTRATOR_URL}/internal/dashboards/{dashboard_id}',
                params={'tenant_id': context.tenant_id, 'user_id': context.user_id, 'is_admin': is_admin, 'source_id': request.headers.get("x-source-id") or None},
                json=body,
                headers={'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@app.delete("/v1/dashboards/{dashboard_id}")
async def delete_dashboard(dashboard_id: str, request: Request, context: TenantContext = Depends(require_analyst)):
    try:
        is_admin = str("admin" in context.roles or "manager" in context.roles).lower()
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f'{ORCHESTRATOR_URL}/internal/dashboards/{dashboard_id}',
                params={'tenant_id': context.tenant_id, 'user_id': context.user_id, 'is_admin': is_admin},
                headers={'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@app.post("/v1/dashboards/{dashboard_id}/items")
async def add_dashboard_item(dashboard_id: str, request: Request, context: TenantContext = Depends(require_analyst)):
    try:
        body = await request.json()
        is_admin = str("admin" in context.roles or "manager" in context.roles).lower()
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f'{ORCHESTRATOR_URL}/internal/dashboards/{dashboard_id}/items',
                params={'tenant_id': context.tenant_id, 'user_id': context.user_id, 'is_admin': is_admin},
                json=body,
                headers={'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@app.delete("/v1/dashboards/{dashboard_id}/items/{item_id}")
async def delete_dashboard_item(dashboard_id: str, item_id: str, request: Request, context: TenantContext = Depends(require_analyst)):
    try:
        is_admin = str("admin" in context.roles or "manager" in context.roles).lower()
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f'{ORCHESTRATOR_URL}/internal/dashboards/{dashboard_id}/items/{item_id}',
                params={'tenant_id': context.tenant_id, 'user_id': context.user_id, 'is_admin': is_admin},
                headers={'X-Correlation-ID': request.state.correlation_id},
                timeout=10.0
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)

@app.get("/v1/results/{message_id}/export")
async def export_results(message_id: str, format: str, request: Request, context: TenantContext = Depends(require_analyst)):
    try:
        await check_rate_limit(context.user_id, action="export", tenant_id=context.tenant_id)
        ORCHESTRATOR_URL = 'http://orchestrator:8004'
        
        # We need to stream the response back
        client = httpx.AsyncClient()
        req = client.build_request(
            "GET",
            f'{ORCHESTRATOR_URL}/internal/results/{message_id}/export',
            params={'format': format, 'tenant_id': context.tenant_id, 'user_id': context.user_id, 'source_id': request.headers.get("x-source-id") or None},
            headers={'X-Correlation-ID': request.state.correlation_id}
        )
        resp = await client.send(req, stream=True)
        resp.raise_for_status()
        
        return StreamingResponse(
            resp.aiter_bytes(),
            media_type=resp.headers.get("Content-Type", "text/csv"),
            headers={"Content-Disposition": resp.headers.get("Content-Disposition", f"attachment; filename=export_{message_id}.csv")}
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
