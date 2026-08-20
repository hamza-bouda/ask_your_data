"""JWT decoding and validation.

This module is the single place where JWT tokens are cracked open.
No other service in the system should ever touch a JWT directly —
they all receive a TenantContext instead.
"""

from __future__ import annotations

from datetime import datetime, timezone

import jwt  # PyJWT library

try:
    from app.config import JWT_SECRET, JWT_ALGORITHM, JWT_AUDIENCE
except ImportError:
    from backend.services.identity.app.config import JWT_SECRET, JWT_ALGORITHM, JWT_AUDIENCE


class TokenError(Exception):
    """Raised when a JWT is invalid for any reason."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def decode_token(raw_token: str) -> dict:
    """Decode and validate a JWT token.

    Checks performed:
    1. Signature — was this token signed with our secret?
    2. Expiration ("exp") — is the token still valid?
    3. Audience ("aud") — is this token meant for our app?

    Returns the payload dict if everything checks out.
    Raises TokenError with a specific code if anything is wrong.
    """
    try:
        payload = jwt.decode(
            raw_token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            # PyJWT automatically checks "exp" if present
        )
        return payload

    except jwt.ExpiredSignatureError:
        # The "exp" field in the payload is in the past
        raise TokenError("TOKEN_EXPIRED", "Token has expired.")

    except jwt.InvalidAudienceError:
        # The "aud" field doesn't match JWT_AUDIENCE
        raise TokenError("INVALID_AUDIENCE", "Token audience does not match.")

    except jwt.DecodeError:
        # The token is malformed or the signature doesn't match
        raise TokenError("INVALID_TOKEN", "Token is malformed or signature is invalid.")

    except jwt.InvalidTokenError as exc:
        # Catch-all for any other JWT validation error
        raise TokenError("INVALID_TOKEN", f"Token validation failed: {exc}")
