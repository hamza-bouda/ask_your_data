import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Inject a correlation ID into the request state and response headers."""
        # Check if the client provided a correlation ID, otherwise generate a new one
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        
        # Store in request state for use by endpoints
        request.state.correlation_id = correlation_id
        
        # Call the next middleware/endpoint
        response = await call_next(request)
        
        # Add the correlation ID to the response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Inject security headers to harden the application."""
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response
