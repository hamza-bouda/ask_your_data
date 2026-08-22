"""SQLAlchemy models for the Identity service.

Three tables, all filtered by tenant_id to enforce isolation:

- tenant_policies:  what roles exist for a tenant and what they can do
- role_bindings:    which user has which role in which tenant
- auth_audit:       immutable log of every authentication attempt
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, Boolean, DateTime, JSON, ForeignKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

try:
    from .database import Base
except (ImportError, ValueError):
    try:
        from backend.services.identity.app.database import Base
    except ImportError:
        from app.database import Base


class TenantPolicy(Base):
    """Defines which roles exist for a tenant and what permissions they grant.

    Example row:
        tenant_id="acme", role_name="analyst", permissions=["query", "view_catalog"]
    """
    __tablename__ = "tenant_policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class RoleBinding(Base):
    """Maps a user to a role within a tenant.

    Example row:
        tenant_id="acme", user_id="hamza", role_name="analyst"
    """
    __tablename__ = "role_bindings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class AuthAudit(Base):
    """Immutable log of every authentication attempt.

    Every call to /internal/resolve-context creates one row.
    We never UPDATE or DELETE rows in this table — it's append-only.

    Example row:
        tenant_id="acme", user_id="hamza", action="resolve_context",
        success=True, error_code=None
    """
    __tablename__ = "auth_audit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class User(Base):
    """User account for the application."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(100), primary_key=True) # UUID or username
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    # Stores a versioned scrypt hash; legacy development rows are migrated on login.
    password: Mapped[str] = mapped_column(String(200), nullable=False)
