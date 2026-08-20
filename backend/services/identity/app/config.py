"""Configuration for the Identity service.

Loaded from environment variables with sensible dev defaults.
"""

from __future__ import annotations

import os


# ── JWT Settings ─────────────────────────────────────────────────
# In production, this would be the public key from your OIDC provider.
# For dev, we use a shared secret (HS256 symmetric signing).
JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")

# "audience" = who this token is meant for.
# Our Identity service only accepts tokens meant for "ask-your-data".
# If someone sends a token meant for another app, we reject it.
JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "ask-your-data")

# ── Database ─────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://askyourdata:askyourdata_dev@postgres:5432/askyourdata",
)
