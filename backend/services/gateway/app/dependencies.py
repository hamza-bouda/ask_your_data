from typing import Optional
from fastapi import Request, HTTPException, Depends
import httpx

try:
    from app.config import IDENTITY_URL, ALLOW_SSE_TOKEN_QUERY
except ImportError:
    from backend.services.gateway.app.config import IDENTITY_URL, ALLOW_SSE_TOKEN_QUERY

from contracts.tenant import TenantContext


async def get_tenant_context(request: Request) -> TenantContext:
    """FastAPI dependency to extract the token and resolve it to a TenantContext.
    
    Calls the Identity service to validate the token.
    Raises 401 if missing or invalid.
    """
    auth_header = request.headers.get("Authorization")
    token_query = request.query_params.get("token")
    if not auth_header and not token_query:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    token = None
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Expected 'Bearer <token>' format")
        token = parts[1]
    elif token_query and ALLOW_SSE_TOKEN_QUERY and request.url.path.endswith("/events"):
        token = token_query
    elif token_query:
        raise HTTPException(status_code=401, detail="Bearer token required")
    
    if not token:
        raise HTTPException(status_code=401, detail="Token validation failed")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{IDENTITY_URL}/internal/resolve-context",
                json={"token": token},
                timeout=5.0
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail=resp.json().get("detail", "Token validation failed"))
            
            return TenantContext(**resp.json())
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Identity service unavailable")

async def require_admin(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    """FastAPI dependency to ensure the user has the 'admin' role."""
    if "admin" not in context.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    return context
