import pytest
from fastapi.testclient import TestClient
from backend.services.gateway.app.main import app
from backend.services.gateway.app.dependencies import get_tenant_context
from contracts.tenant import TenantContext

client = TestClient(app)

def override_tenant_context_viewer_tenant_a():
    return TenantContext(tenant_id="tenant_a", user_id="viewer_1", roles=["viewer"])

def override_tenant_context_analyst_tenant_b():
    return TenantContext(tenant_id="tenant_b", user_id="analyst_1", roles=["analyst"])

def test_viewer_cannot_create_conversation():
    app.dependency_overrides[get_tenant_context] = override_tenant_context_viewer_tenant_a
    response = client.post("/v1/conversations", json={"title": "Test"})
    assert response.status_code == 403
    assert "Analyst access required" in response.json()["detail"]
    app.dependency_overrides.clear()

def test_viewer_cannot_sync_source():
    app.dependency_overrides[get_tenant_context] = override_tenant_context_viewer_tenant_a
    response = client.post("/v1/datasources/source_1/sync")
    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]
    app.dependency_overrides.clear()
