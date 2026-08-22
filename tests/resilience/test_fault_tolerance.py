"""Resilience and Fault Tolerance Test Suite."""

import pytest
from fastapi.testclient import TestClient
from contracts.llm import BaseLLMProvider, get_llm_provider
from backend.services.orchestrator.app.answer_generator import generate_business_answer
from backend.services.catalog.app.main import app as catalog_app


class FailingLLMProvider(BaseLLMProvider):
    """An LLM provider that simulates 500 error / API outage."""
    def get_chat_model(self, temperature: float = 0.0):
        raise RuntimeError("DeepSeek API 503 Service Unavailable: Rate limit reached or upstream timeout")


class TestFaultTolerance:
    """Validate platform fault tolerance and graceful degradation under failure."""

    def test_llm_failure_graceful_fallback(self):
        """When LLM provider raises an error, AnswerGenerator cleanly falls back to deterministic synthesis."""
        failing_provider = FailingLLMProvider()
        results = [
            {"region": "North", "sales": 50000},
            {"region": "South", "sales": 40000},
        ]

        # Should not raise exception
        answer = generate_business_answer(
            question="Quelles sont les ventes par région ?",
            results=results,
            sql_query="SELECT region, sales FROM regional_sales",
            llm_provider=failing_provider,
        )

        assert answer is not None
        assert answer.answer is not None
        assert answer.executive_summary is not None
        assert len(answer.key_insights) >= 1

    def test_connection_error_masks_credentials(self):
        """Database connection error in catalog does not leak credentials in response."""
        client = TestClient(catalog_app)
        conn_with_secret = "postgresql://secret_user:super_secret_password_999@127.0.0.1:59999/secret_db"

        resp = client.post(
            "/api/v1/catalog/register",
            json={"connection_string": conn_with_secret, "name": "Secret DB"},
            headers={"x-tenant-id": "test_tenant", "x-user-id": "test_user"},
        )

        assert resp.status_code == 400
        detail = str(resp.json().get("detail") or resp.text)
        assert "super_secret_password_999" not in detail
        assert "secret_user" not in detail
