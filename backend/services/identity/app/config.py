"""Configuration for the Identity service.

Loaded from environment variables with sensible dev defaults.
"""

from __future__ import annotations

import os


APP_ENV: str = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV in {"production", "prod"}


# ── JWT Settings ─────────────────────────────────────────────────
# In production, this would be the public key from your OIDC provider.
# For dev, we use a shared secret (HS256 symmetric signing).
JWT_SECRET: str = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY") or "dev-secret-change-in-production"
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

if IS_PRODUCTION and JWT_SECRET == "dev-secret-change-in-production":
    raise RuntimeError("JWT_SECRET must be configured in production.")

LOCAL_AUTH_ENABLED = os.getenv(
    "LOCAL_AUTH_ENABLED", "false" if IS_PRODUCTION else "true"
).lower() == "true"
DEV_ENDPOINTS_ENABLED = os.getenv(
    "DEV_ENDPOINTS_ENABLED", "false" if IS_PRODUCTION else "true"
).lower() == "true"

# "audience" = who this token is meant for.
# Our Identity service only accepts tokens meant for "ask-your-data".
# If someone sends a token meant for another app, we reject it.
JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "ask-your-data")

# ── Database ─────────────────────────────────────────────────────
if os.getenv("TESTING") == "1":
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./test_identity.db")
else:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://askyourdata:askyourdata_dev@postgres:5432/askyourdata",
    )
