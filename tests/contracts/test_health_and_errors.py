"""Contract tests — Phase 01 Definition of Done.

Verifies that every service:
1. Exposes GET /health → 200 with {status, service, version}
2. Exposes GET /ready  → 200 with {ready, service}
3. Returns ApiError on unknown routes (404)
4. Includes X-Contract-Version header in every response

Run against live Docker services:
    pytest tests/contracts/test_health_and_errors.py -v

Or run against individual TestClient instances (no Docker needed):
    pytest tests/contracts/test_health_and_errors.py -v -k "unit"
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ── Unit tests (no Docker required) ─────────────────────────────
# Import each service's app and test it in-process.

def _get_all_apps() -> list[tuple[str, TestClient]]:
    """Lazily import all service apps and wrap in TestClients."""
    from app import main as _  # noqa: F401 — ensure contracts is importable

    services = []
    service_modules = [
        ("gateway", "backend.services.gateway.app.main"),
        ("identity", "backend.services.identity.app.main"),
        ("catalog", "backend.services.catalog.app.main"),
        ("query_execution", "backend.services.query_execution.app.main"),
        ("orchestrator", "backend.services.orchestrator.app.main"),
        ("visualization", "backend.services.visualization.app.main"),
    ]
    for name, module_path in service_modules:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            services.append((name, TestClient(mod.app)))
        except ImportError:
            pass
    return services


# For simpler testing, we test each service individually via its app
# directly, which doesn't require Docker.

@pytest.fixture(params=[
    "gateway",
    "identity",
    "catalog",
    "query_execution",
    "orchestrator",
    "visualization",
])
def service_client(request: pytest.FixtureRequest) -> tuple[str, TestClient]:
    """Create a TestClient for each service."""
    service_name = request.param
    module_map = {
        "gateway": "backend.services.gateway.app.main",
        "identity": "backend.services.identity.app.main",
        "catalog": "backend.services.catalog.app.main",
        "query_execution": "backend.services.query_execution.app.main",
        "orchestrator": "backend.services.orchestrator.app.main",
        "visualization": "backend.services.visualization.app.main",
    }
    import importlib
    mod = importlib.import_module(module_map[service_name])
    return service_name, TestClient(mod.app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Every service must expose GET /health → 200."""

    def test_unit_health_returns_200(self, service_client: tuple[str, TestClient]) -> None:
        name, client = service_client
        resp = client.get("/health")
        assert resp.status_code == 200, f"{name} /health returned {resp.status_code}"

    def test_unit_health_has_required_fields(self, service_client: tuple[str, TestClient]) -> None:
        name, client = service_client
        body = client.get("/health").json()
        assert "status" in body, f"{name} /health missing 'status'"
        assert "service" in body, f"{name} /health missing 'service'"
        assert "version" in body, f"{name} /health missing 'version'"
        assert body["status"] == "ok"

    def test_unit_health_has_contract_version_header(self, service_client: tuple[str, TestClient]) -> None:
        name, client = service_client
        resp = client.get("/health")
        assert "X-Contract-Version" in resp.headers, f"{name} missing X-Contract-Version header"


class TestReadyEndpoint:
    """Every service must expose GET /ready → 200."""

    def test_unit_ready_returns_200(self, service_client: tuple[str, TestClient]) -> None:
        name, client = service_client
        resp = client.get("/ready")
        assert resp.status_code == 200, f"{name} /ready returned {resp.status_code}"

    def test_unit_ready_has_required_fields(self, service_client: tuple[str, TestClient]) -> None:
        name, client = service_client
        body = client.get("/ready").json()
        assert "ready" in body, f"{name} /ready missing 'ready'"
        assert "service" in body, f"{name} /ready missing 'service'"


class TestErrorContract:
    """Unknown routes must return a well-formed ApiError."""

    def test_unit_404_returns_api_error(self, service_client: tuple[str, TestClient]) -> None:
        name, client = service_client
        resp = client.get("/this-route-does-not-exist")
        assert resp.status_code == 404, f"{name} expected 404, got {resp.status_code}"

        body = resp.json()
        assert "code" in body, f"{name} 404 response missing 'code'"
        assert "message" in body, f"{name} 404 response missing 'message'"
        assert "timestamp" in body, f"{name} 404 response missing 'timestamp'"

    def test_unit_404_has_contract_version_header(self, service_client: tuple[str, TestClient]) -> None:
        name, client = service_client
        resp = client.get("/this-route-does-not-exist")
        assert "X-Contract-Version" in resp.headers, f"{name} 404 missing X-Contract-Version header"


# ── Integration tests (Docker required) ─────────────────────────
# These tests hit the actual running containers.
# Run with: pytest tests/contracts/test_health_and_errors.py -v -k "integration"

DOCKER_SERVICES = {
    "gateway": "http://localhost:8000",
    "identity": "http://localhost:8001",
    "catalog": "http://localhost:8002",
    "query-execution": "http://localhost:8003",
    "orchestrator": "http://localhost:8004",
    "visualization": "http://localhost:8005",
}


@pytest.fixture(params=list(DOCKER_SERVICES.keys()))
def docker_service(request: pytest.FixtureRequest) -> tuple[str, str]:
    return request.param, DOCKER_SERVICES[request.param]


class TestIntegrationHealth:
    """Integration tests against running Docker containers."""

    @pytest.mark.integration
    def test_integration_health(self, docker_service: tuple[str, str]) -> None:
        import httpx
        name, base_url = docker_service
        resp = httpx.get(f"{base_url}/health", timeout=5)
        assert resp.status_code == 200, f"{name} /health returned {resp.status_code}"
        body = resp.json()
        assert body["status"] == "ok"
        assert "X-Contract-Version" in resp.headers

    @pytest.mark.integration
    def test_integration_ready(self, docker_service: tuple[str, str]) -> None:
        import httpx
        name, base_url = docker_service
        resp = httpx.get(f"{base_url}/ready", timeout=5)
        assert resp.status_code == 200

    @pytest.mark.integration
    def test_integration_404_error_format(self, docker_service: tuple[str, str]) -> None:
        import httpx
        name, base_url = docker_service
        resp = httpx.get(f"{base_url}/nonexistent", timeout=5)
        assert resp.status_code == 404
        body = resp.json()
        assert "code" in body
        assert "message" in body
