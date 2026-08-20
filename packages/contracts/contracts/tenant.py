"""TenantContext — resolved by the Identity service and propagated
through every internal call so that each service can enforce
tenant isolation without re-authenticating the JWT.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TenantContext(BaseModel):
    """Identity-resolved context attached to every internal request.

    Created by the Identity service after JWT validation and forwarded
    as a signed header or request body field to downstream services.
    """

    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Organisation / tenant identifier.",
    )
    user_id: str = Field(
        ...,
        min_length=1,
        description="Authenticated user identifier.",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Roles granted to the user within this tenant.",
    )
    permissions: list[str] = Field(
        default_factory=list,
        description="Fine-grained permissions resolved from roles.",
    )
