"""Identity & Tenant Service — JWT validation and tenant resolution.

Endpoints:
- POST /internal/resolve-context  →  Gateway sends a JWT, gets back a TenantContext
- GET  /v1/me                     →  User-facing: "who am I?" (also needs JWT)
- POST /dev/token                 →  Dev-only: generate a test JWT
- POST /dev/seed                  →  Dev-only: seed policies and role bindings
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Header, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics

from contracts.tenant import TenantContext

try:
    from app.jwt_handler import decode_token, TokenError
    from app.database import get_db, create_tables, SessionLocal
    from app.models import TenantPolicy, RoleBinding, AuthAudit, User
except ImportError:
    from backend.services.identity.app.jwt_handler import decode_token, TokenError
    from backend.services.identity.app.database import get_db, create_tables, SessionLocal
    from backend.services.identity.app.models import TenantPolicy, RoleBinding, AuthAudit, User


app = create_service_app(service_name="identity")

# Observability setup
setup_logging(service_name="identity")
setup_tracing(service_name="identity", app=app)
setup_metrics(app)



# Create tables on startup
@app.on_event("startup")
def on_startup() -> None:
    create_tables()
    # Seed a default user for testing
    db = SessionLocal()
    if not db.query(User).filter(User.username == "hamza").first():
        db.add(User(id="hamza", tenant_id="acme", username="hamza", password="password"))
        db.commit()
    db.close()


# ── Request/Response models ──────────────────────────────────────

class ResolveContextRequest(BaseModel):
    token: str

class LoginRequest(BaseModel):
    username: str
    password: str


class DevTokenRequest(BaseModel):
    tenant_id: str = "acme"
    user_id: str = "hamza"
    roles: list[str] = ["analyst"]
    expires_in_minutes: int = 60


class SeedRequest(BaseModel):
    """Dev-only: create a tenant policy and a role binding in one call."""
    tenant_id: str = "acme"
    user_id: str = "hamza"
    role_name: str = "analyst"
    permissions: list[str] = ["query", "view_catalog"]


# ── Helpers ──────────────────────────────────────────────────────

def _payload_to_context(payload: dict, db: Session | None = None) -> TenantContext:
    """Map JWT payload → TenantContext, optionally enriching permissions from DB.

    Without DB: permissions come empty (still works for basic auth).
    With DB: we look up the user's roles in role_bindings, then get
    the permissions for those roles from tenant_policies.
    """
    tenant_id = payload.get("tenant_id")
    user_id = payload.get("sub")

    if not tenant_id:
        raise TokenError("MISSING_TENANT", "Token does not contain tenant_id.")
    if not user_id:
        raise TokenError("MISSING_USER", "Token does not contain sub (user_id).")

    roles = payload.get("roles", [])
    permissions: list[str] = []

    # Enrich permissions from DB if available
    if db is not None:
        # Find all roles this user has in this tenant
        bindings = (
            db.query(RoleBinding)
            .filter(RoleBinding.tenant_id == tenant_id, RoleBinding.user_id == user_id)
            .all()
        )
        db_roles = [b.role_name for b in bindings]

        # Merge JWT roles with DB roles (JWT roles take precedence)
        all_roles = list(set(roles + db_roles))

        # Look up permissions for all roles in this tenant
        policies = (
            db.query(TenantPolicy)
            .filter(
                TenantPolicy.tenant_id == tenant_id,
                TenantPolicy.role_name.in_(all_roles),
            )
            .all()
        )
        for policy in policies:
            permissions.extend(policy.permissions or [])

        permissions = list(set(permissions))  # deduplicate
        roles = all_roles

    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=roles,
        permissions=permissions,
    )


def _log_audit(
    db: Session | None,
    *,
    tenant_id: str | None,
    user_id: str | None,
    action: str,
    success: bool,
    error_code: str | None = None,
) -> None:
    """Write one row to auth_audit. Never raises — audit failure must not break auth."""
    if db is None:
        return
    try:
        entry = AuthAudit(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            success=success,
            error_code=error_code,
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()  # Audit failure should never break the auth flow


# ── Endpoints ────────────────────────────────────────────────────

@app.post("/internal/resolve-context", response_model=TenantContext)
def resolve_context(
    body: ResolveContextRequest,
    db: Session = Depends(get_db),
) -> TenantContext:
    """Called by the Gateway to validate a JWT and get a TenantContext.

    1. Decode JWT (signature, expiration, audience)
    2. Extract tenant_id, user_id, roles
    3. Enrich permissions from DB
    4. Log to auth_audit
    5. Return TenantContext
    """
    try:
        payload = decode_token(body.token)
    except TokenError as exc:
        _log_audit(db, tenant_id=None, user_id=None, action="resolve_context",
                   success=False, error_code=exc.code)
        raise HTTPException(status_code=401, detail=exc.message)

    try:
        context = _payload_to_context(payload, db=db)
    except TokenError as exc:
        _log_audit(db, tenant_id=payload.get("tenant_id"), user_id=payload.get("sub"),
                   action="resolve_context", success=False, error_code=exc.code)
        raise HTTPException(status_code=401, detail=exc.message)

    _log_audit(db, tenant_id=context.tenant_id, user_id=context.user_id,
               action="resolve_context", success=True)
    return context


@app.get("/v1/me", response_model=TenantContext)
def get_me(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> TenantContext:
    """User-facing: 'who am I?' Expects Authorization: Bearer <token>."""
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Expected 'Bearer <token>' format.")

    try:
        payload = decode_token(parts[1])
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=exc.message)

    try:
        return _payload_to_context(payload, db=db)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=exc.message)


@app.post("/dev/token")
def create_token(body: DevTokenRequest) -> dict[str, str]:
    """Dev-only: generate a signed JWT for testing."""
    try:
        from app.dev_tokens import create_dev_token
    except ImportError:
        from backend.services.identity.app.dev_tokens import create_dev_token

    token = create_dev_token(
        tenant_id=body.tenant_id,
        user_id=body.user_id,
        roles=body.roles,
        expires_in_minutes=body.expires_in_minutes,
    )
    return {"token": token}


@app.post("/dev/seed")
def seed_data(body: SeedRequest, db: Session = Depends(get_db)) -> dict:
    """Dev-only: create a tenant policy and role binding for testing."""
    # Create policy if it doesn't exist
    existing_policy = (
        db.query(TenantPolicy)
        .filter(TenantPolicy.tenant_id == body.tenant_id, TenantPolicy.role_name == body.role_name)
        .first()
    )
    if not existing_policy:
        db.add(TenantPolicy(
            tenant_id=body.tenant_id,
            role_name=body.role_name,
            permissions=body.permissions,
        ))

    # Create role binding if it doesn't exist
    existing_binding = (
        db.query(RoleBinding)
        .filter(
            RoleBinding.tenant_id == body.tenant_id,
            RoleBinding.user_id == body.user_id,
            RoleBinding.role_name == body.role_name,
        )
        .first()
    )
    if not existing_binding:
        db.add(RoleBinding(
            tenant_id=body.tenant_id,
            user_id=body.user_id,
            role_name=body.role_name,
        ))

    db.commit()
    return {"status": "seeded", "tenant_id": body.tenant_id}


@app.post("/v1/auth/login")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> dict:
    """Authenticates user and returns a JWT token."""
    user = db.query(User).filter(User.username == body.username, User.password == body.password).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    try:
        from app.dev_tokens import create_dev_token
    except ImportError:
        from backend.services.identity.app.dev_tokens import create_dev_token

    # Find roles
    bindings = db.query(RoleBinding).filter(RoleBinding.user_id == user.id).all()
    roles = [b.role_name for b in bindings]
    if not roles:
        roles = ["analyst"] # default role

    token = create_dev_token(
        tenant_id=user.tenant_id,
        user_id=user.id,
        roles=roles,
        expires_in_minutes=1440, # 24 hours
    )
    return {"token": token, "user": {"id": user.id, "username": user.username, "tenant_id": user.tenant_id}}

