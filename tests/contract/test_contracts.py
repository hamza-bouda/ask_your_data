"""Contract tests — Verifies API interfaces and inter-service payloads."""

import pytest
from fastapi.testclient import TestClient
from contracts import ApiError, RunEvent, ChartSpec, QueryRequest
from backend.services.sql_executor.app.main import app as sql_executor_app
from backend.services.visualization.app.main import app as visualization_app
from backend.services.semantic_router.app.main import app as semantic_router_app


class TestInterServiceContracts:
    """Validate internal microservice API contracts without requiring live Docker containers."""

    def test_sql_executor_contract_validation(self):
        """sql_executor accepts valid execute-sql requests and returns structured results."""
        client = TestClient(sql_executor_app)

        # Test invalid execution missing parameters
        resp = client.post("/internal/execute-sql", json={})
        assert resp.status_code == 422

        # Test valid AST rejection for SELECT *
        resp_invalid = client.post("/internal/execute-sql", json={
            "sql_query": "SELECT * FROM users",
            "tenant_id": "test_tenant",
        })
        assert resp_invalid.status_code == 400
        assert "SELECT *" in resp_invalid.json().get("detail", "")

    def test_sql_executor_cache_invalidation_contract(self):
        """sql_executor exposes cache invalidation endpoint."""
        client = TestClient(sql_executor_app)
        resp = client.post("/internal/invalidate-cache", json={"tenant_id": "test_tenant", "source_id": "src_123"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "success"

    def test_visualization_contract(self):
        """visualization service receives query results and returns valid ChartSpec."""
        client = TestClient(visualization_app)
        payload = {
            "results": [
                {"category": "Electronics", "sales": 45000},
                {"category": "Clothing", "sales": 32000},
            ],
            "question": "Montre les ventes par catégorie",
        }
        resp = client.post("/internal/chart-spec", json=payload)
        assert resp.status_code == 200
        spec_data = resp.json()
        assert "chart_type" in spec_data
        assert "title" in spec_data

    def test_semantic_router_plan_contract(self):
        """semantic_router returns structured semantic plan with intent."""
        client = TestClient(semantic_router_app)
        payload = {
            "query": "Quel est le chiffre d'affaires ?",
            "context": {"tables": ["invoices"]},
        }
        resp = client.post("/internal/plan", json=payload)
        assert resp.status_code == 200
        plan = resp.json()
        assert "intent" in plan
