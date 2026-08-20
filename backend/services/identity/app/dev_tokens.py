"""Dev-only token generator.

In production, tokens come from an OIDC provider (Google, Auth0, Keycloak...).
For local development, this module lets us create valid JWT tokens
to test the Identity service without setting up a real auth provider.

Usage:
    from app.dev_tokens import create_dev_token
    token = create_dev_token(tenant_id="acme", user_id="hamza", roles=["analyst"])
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import jwt

try:
    from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_AUDIENCE
except ImportError:
    from backend.services.identity.app.config import JWT_SECRET, JWT_ALGORITHM, JWT_AUDIENCE


def create_dev_token(
    *,
    tenant_id: str,
    user_id: str,
    roles: list[str] | None = None,
    expires_in_minutes: int = 60,
) -> str:
    """Create a signed JWT for local development.

    The payload structure mirrors what a real OIDC provider would emit:
    - sub: user identifier
    - tenant_id: organisation identifier
    - roles: list of role names
    - aud: intended audience (our app)
    - exp: expiration timestamp
    - iat: issued-at timestamp
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or ["viewer"],
        "aud": JWT_AUDIENCE,
        "exp": now + timedelta(minutes=expires_in_minutes),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
