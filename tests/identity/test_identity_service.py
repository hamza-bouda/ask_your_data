"""Tests for the Identity & Tenant Service — Phase 02 Definition of Done.

Tests cover:
1. Valid token → TenantContext returned
2. Expired token → 401
3. Invalid audience → 401
4. Malformed token → 401
5. Two-tenant isolation → tenant A ≠ tenant B
6. Auth audit → every attempt is logged
7. Permission enrichment from DB → roles/permissions resolved
8. Dev token roundtrip → generate + validate
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

# Force SQLite for tests BEFORE importing the app
os.environ["DATABASE_URL"] = "sqlite:///./test_identity.db"

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Test DB setup ────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///./test_identity.db"
JWT_SECRET = "dev-secret-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "ask-your-data"

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)

from backend.services.identity.app.database import Base, get_db
from backend.services.identity.app.models import TenantPolicy, RoleBinding, AuthAudit
from backend.services.identity.app.main import app


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def _make_token(
    *,
    tenant_id: str = "acme",
    user_id: str = "hamza",
    roles: list[str] | None = None,
    audience: str = JWT_AUDIENCE,
    expires_in: timedelta = timedelta(hours=1),
    secret: str = JWT_SECRET,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": roles or ["analyst"],
        "aud": audience,
        "exp": now + expires_in,
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def db_session():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


# ── 1. Valid token ───────────────────────────────────────────────

class TestValidToken:
    def test_resolve_context_returns_200(self, client: TestClient) -> None:
        token = _make_token()
        resp = client.post("/internal/resolve-context", json={"token": token})
        assert resp.status_code == 200

    def test_resolve_context_has_correct_fields(self, client: TestClient) -> None:
        token = _make_token()
        body = client.post("/internal/resolve-context", json={"token": token}).json()
        assert body["tenant_id"] == "acme"
        assert body["user_id"] == "hamza"
        assert "analyst" in body["roles"]

    def test_me_with_valid_bearer(self, client: TestClient) -> None:
        token = _make_token()
        resp = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "hamza"


# ── 2. Expired token ────────────────────────────────────────────

class TestExpiredToken:
    def test_expired_token_is_rejected(self, client: TestClient) -> None:
        token = _make_token(expires_in=timedelta(seconds=-10))
        resp = client.post("/internal/resolve-context", json={"token": token})
        assert resp.status_code == 401

    def test_expired_token_error_message(self, client: TestClient) -> None:
        token = _make_token(expires_in=timedelta(seconds=-10))
        resp = client.post("/internal/resolve-context", json={"token": token})
        body = resp.json()
        error_text = (body.get("message") or body.get("detail") or "").lower()
        assert "expired" in error_text


# ── 3. Invalid audience ─────────────────────────────────────────

class TestInvalidAudience:
    def test_wrong_audience_is_rejected(self, client: TestClient) -> None:
        token = _make_token(audience="some-other-app")
        resp = client.post("/internal/resolve-context", json={"token": token})
        assert resp.status_code == 401

    def test_wrong_audience_error_message(self, client: TestClient) -> None:
        token = _make_token(audience="some-other-app")
        resp = client.post("/internal/resolve-context", json={"token": token})
        body = resp.json()
        error_text = (body.get("message") or body.get("detail") or "").lower()
        assert "audience" in error_text


# ── 4. Malformed / invalid token ────────────────────────────────

class TestInvalidToken:
    def test_garbage_token(self, client: TestClient) -> None:
        resp = client.post("/internal/resolve-context", json={"token": "not.a.jwt"})
        assert resp.status_code == 401

    def test_wrong_secret(self, client: TestClient) -> None:
        token = _make_token(secret="wrong-secret")
        resp = client.post("/internal/resolve-context", json={"token": token})
        assert resp.status_code == 401

    def test_missing_bearer_prefix(self, client: TestClient) -> None:
        token = _make_token()
        resp = client.get("/v1/me", headers={"Authorization": token})
        assert resp.status_code == 401

    def test_no_authorization_header(self, client: TestClient) -> None:
        resp = client.get("/v1/me")
        assert resp.status_code == 422


# ── 5. Two-tenant isolation ─────────────────────────────────────

class TestTenantIsolation:
    def test_different_tenants_get_different_contexts(self, client: TestClient) -> None:
        token_a = _make_token(tenant_id="alpha", user_id="alice")
        token_b = _make_token(tenant_id="beta", user_id="bob")

        ctx_a = client.post("/internal/resolve-context", json={"token": token_a}).json()
        ctx_b = client.post("/internal/resolve-context", json={"token": token_b}).json()

        assert ctx_a["tenant_id"] == "alpha"
        assert ctx_b["tenant_id"] == "beta"
        assert ctx_a["user_id"] != ctx_b["user_id"]

    def test_tenant_a_permissions_not_visible_to_tenant_b(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Seed permissions for tenant A; tenant B must NOT see them."""
        # Seed tenant A with specific permissions
        db_session.add(TenantPolicy(
            tenant_id="alpha", role_name="admin", permissions=["delete", "manage_users"]
        ))
        db_session.add(RoleBinding(
            tenant_id="alpha", user_id="alice", role_name="admin"
        ))
        db_session.commit()

        # Tenant B user with same role name should get NO permissions
        token_b = _make_token(tenant_id="beta", user_id="bob", roles=["admin"])
        ctx_b = client.post("/internal/resolve-context", json={"token": token_b}).json()

        assert "delete" not in ctx_b["permissions"]
        assert "manage_users" not in ctx_b["permissions"]


# ── 6. Auth audit ────────────────────────────────────────────────

class TestAuthAudit:
    def test_successful_auth_is_logged(self, client: TestClient, db_session) -> None:
        token = _make_token()
        client.post("/internal/resolve-context", json={"token": token})

        audits = db_session.query(AuthAudit).all()
        assert len(audits) == 1
        assert audits[0].success is True
        assert audits[0].tenant_id == "acme"
        assert audits[0].user_id == "hamza"
        assert audits[0].action == "resolve_context"

    def test_failed_auth_is_logged(self, client: TestClient, db_session) -> None:
        client.post("/internal/resolve-context", json={"token": "garbage"})

        audits = db_session.query(AuthAudit).all()
        assert len(audits) == 1
        assert audits[0].success is False
        assert audits[0].error_code is not None


# ── 7. Permission enrichment from DB ────────────────────────────

class TestPermissionEnrichment:
    def test_permissions_resolved_from_db(self, client: TestClient, db_session) -> None:
        """When policies + bindings exist in DB, permissions are enriched."""
        db_session.add(TenantPolicy(
            tenant_id="acme", role_name="analyst", permissions=["query", "view_catalog"]
        ))
        db_session.add(RoleBinding(
            tenant_id="acme", user_id="hamza", role_name="analyst"
        ))
        db_session.commit()

        token = _make_token(tenant_id="acme", user_id="hamza", roles=["analyst"])
        ctx = client.post("/internal/resolve-context", json={"token": token}).json()

        assert "query" in ctx["permissions"]
        assert "view_catalog" in ctx["permissions"]

    def test_no_permissions_without_db_entries(self, client: TestClient) -> None:
        """Without DB entries, permissions are empty but auth still works."""
        token = _make_token()
        ctx = client.post("/internal/resolve-context", json={"token": token}).json()
        assert ctx["permissions"] == []


# ── 8. Dev token roundtrip ───────────────────────────────────────

class TestDevToken:
    def test_dev_token_roundtrip(self, client: TestClient) -> None:
        create_resp = client.post("/dev/token", json={
            "tenant_id": "test-co", "user_id": "tester", "roles": ["admin"],
        })
        token = create_resp.json()["token"]

        resolve_resp = client.post("/internal/resolve-context", json={"token": token})
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["tenant_id"] == "test-co"


# ── 9. Seed endpoint ────────────────────────────────────────────

class TestSeedEndpoint:
    def test_seed_creates_policy_and_binding(self, client: TestClient, db_session) -> None:
        resp = client.post("/dev/seed", json={
            "tenant_id": "newco", "user_id": "newuser",
            "role_name": "viewer", "permissions": ["read"],
        })
        assert resp.status_code == 200

        policies = db_session.query(TenantPolicy).filter_by(tenant_id="newco").all()
        bindings = db_session.query(RoleBinding).filter_by(tenant_id="newco").all()
        assert len(policies) == 1
        assert len(bindings) == 1
        assert policies[0].permissions == ["read"]
