"""Configuration for the API Gateway."""

import os

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
IDENTITY_URL = os.getenv("IDENTITY_URL", "http://identity:8001")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8004")
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog:8002")

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))

# Credentials must only be sent to explicitly trusted browser origins. Local
# development remains convenient, while production needs an intentional list.
_default_origins = "http://localhost,http://localhost:80,http://localhost:5173"
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", _default_origins if not IS_PRODUCTION else "").split(",")
    if origin.strip()
]
if IS_PRODUCTION and not CORS_ALLOW_ORIGINS:
    raise RuntimeError("CORS_ALLOW_ORIGINS must be configured in production.")

# Native EventSource cannot send an Authorization header. It is deliberately
# opt-in because a bearer token in a URL can otherwise leak through logs.
ALLOW_SSE_TOKEN_QUERY = os.getenv("ALLOW_SSE_TOKEN_QUERY", "false").lower() == "true"
