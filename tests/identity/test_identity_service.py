"""Tests for the Identity & Tenant Service — Phase 02 Definition of Done."""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.services.identity.app.config import JWT_SECRET, JWT_ALGORITHM, JWT_AUDIENCE
from backend.services.identity.app.database import Base, engine, get_db, SessionLocal
from backend.services.identity.app.models import TenantPolicy, RoleBinding, AuthAudit
from backend.services.identity.app.main import app


def override_get_db():
    db = SessionLocal()
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
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def db_session():
    db = SessionLocal()
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


# ── 4. Malformed token ──────────────────────────────────────────

class TestMalformedToken:
    def test_garbage_token_is_rejected(self, client: TestClient) -> None:
        resp = client.post("/internal/resolve-context", json={"token": "not.a.valid.jwt"})
        assert resp.status_code == 401

    def test_empty_token_is_rejected(self, client: TestClient) -> None:
        resp = client.post("/internal/resolve-context", json={"token": ""})
        assert resp.status_code in (401, 422)

    def test_missing_token_field(self, client: TestClient) -> None:
        resp = client.post("/internal/resolve-context", json={})
        assert resp.status_code == 422


# ── 5. Two-tenant isolation ─────────────────────────────────────

class TestTenantIsolation:
    def test_different_tenants_get_different_contexts(self, client: TestClient) -> None:
        token_a = _make_token(tenant_id="tenant-alpha", user_id="alice")
        token_b = _make_token(tenant_id="tenant-beta", user_id="bob")

        ctx_a = client.post("/internal/resolve-context", json={"token": token_a}).json()
        ctx_b = client.post("/internal/resolve-context", json={"token": token_b}).json()

        assert ctx_a["tenant_id"] == "tenant-alpha"
        assert ctx_a["user_id"] == "alice"
        assert ctx_b["tenant_id"] == "tenant-beta"
        assert ctx_b["user_id"] == "bob"
        assert ctx_a["tenant_id"] != ctx_b["tenant_id"]

    def test_tenant_a_permissions_not_visible_to_tenant_b(
        self, client: TestClient, db_session
    ) -> None:
        # Give tenant-alpha:analyst the "export_csv" permission
        db_session.add(TenantPolicy(
            tenant_id="tenant-alpha",
            role_name="analyst",
            permissions=["export_csv", "query"],
        ))
        # Give tenant-beta:analyst only "query"
        db_session.add(TenantPolicy(
            tenant_id="tenant-beta",
            role_name="analyst",
            permissions=["query"],
        ))
        db_session.commit()

        token_a = _make_token(tenant_id="tenant-alpha", user_id="alice", roles=["analyst"])
        token_b = _make_token(tenant_id="tenant-beta", user_id="bob", roles=["analyst"])

        ctx_a = client.post("/internal/resolve-context", json={"token": token_a}).json()
        ctx_b = client.post("/internal/resolve-context", json={"token": token_b}).json()

        assert "export_csv" in ctx_a["permissions"]
        assert "export_csv" not in ctx_b["permissions"]


# ── 6. Auth audit ───────────────────────────────────────────────

class TestAuthAudit:
    def test_successful_auth_is_logged(self, client: TestClient, db_session) -> None:
        token = _make_token(tenant_id="audit-co", user_id="carol")
        client.post("/internal/resolve-context", json={"token": token})

        audits = (
            db_session.query(AuthAudit)
            .filter(AuthAudit.tenant_id == "audit-co", AuthAudit.user_id == "carol")
            .all()
        )
        assert len(audits) >= 1
        assert audits[-1].success is True
        assert audits[-1].action == "resolve_context"

    def test_failed_auth_is_logged(self, client: TestClient, db_session) -> None:
        expired_token = _make_token(
            tenant_id="audit-fail-co",
            user_id="dave",
            expires_in=timedelta(seconds=-10),
        )
        client.post("/internal/resolve-context", json={"token": expired_token})

        audits = (
            db_session.query(AuthAudit)
            .filter(AuthAudit.action == "resolve_context", AuthAudit.success == False)
            .all()
        )
        assert len(audits) >= 1
        assert audits[-1].error_code == "TOKEN_EXPIRED"


# ── 7. Permission enrichment from DB ────────────────────────────

class TestPermissionEnrichment:
    def test_permissions_resolved_from_db(self, client: TestClient, db_session) -> None:
        """Role in DB binds permissions that appear in TenantContext."""
        db_session.add(TenantPolicy(
            tenant_id="enrich-co",
            role_name="admin",
            permissions=["query", "view_catalog", "export_csv", "manage_users"],
        ))
        db_session.add(RoleBinding(
            tenant_id="enrich-co",
            user_id="eve",
            role_name="admin",
        ))
        db_session.commit()

        token = _make_token(tenant_id="enrich-co", user_id="eve", roles=["admin"])
        ctx = client.post("/internal/resolve-context", json={"token": token}).json()

        assert "manage_users" in ctx["permissions"]
        assert "export_csv" in ctx["permissions"]
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
        assert create_resp.status_code == 200
        token = create_resp.json()["token"]

        resolve_resp = client.post("/internal/resolve-context", json={"token": token})
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["user_id"] == "tester"


# ── 9. Seed endpoint ────────────────────────────────────────────

class TestSeedEndpoint:
    def test_seed_creates_policy_and_binding(self, client: TestClient, db_session) -> None:
        resp = client.post("/dev/seed", json={
            "tenant_id": "newco", "user_id": "newuser",
            "role_name": "viewer", "permissions": ["read"],
        })
        assert resp.status_code == 200

        policy = (
            db_session.query(TenantPolicy)
            .filter(TenantPolicy.tenant_id == "newco", TenantPolicy.role_name == "viewer")
            .first()
        )
        assert policy is not None
        assert "read" in policy.permissions
