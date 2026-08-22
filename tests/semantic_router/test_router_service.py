"""Tests for the Semantic Router Service."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.services.semantic_router.app.main import app
from backend.services.semantic_router.app.router import SemanticPlanOut, Intent

client = TestClient(app)

class MockLLMProvider:
    def __init__(self, plan_out):
        self.plan_out = plan_out

    def with_structured_output(self, schema):
        mock_runnable = MagicMock()
        mock_runnable.invoke.return_value = self.plan_out
        return mock_runnable

    def __or__(self, other):
        return self

@patch("backend.services.semantic_router.app.router.get_llm_provider")
def test_route_data_query(mock_get_llm):
    """Test routing a normal data query."""
    plan = SemanticPlanOut(
        intent=Intent.DATA_QUERY,
        confidence=0.9,
        clarification_options=[],
        source_tables=["users"],
        dimensions=[],
        filters=[]
    )

    mock_runnable = MagicMock()
    mock_runnable.invoke.return_value = plan

    mock_provider = MagicMock()
    mock_provider.with_structured_output.return_value = mock_runnable
    mock_get_llm.return_value = mock_provider

    with patch("langchain_core.prompts.ChatPromptTemplate.__or__", return_value=mock_runnable):
        response = client.post("/internal/plan", json={"query": "Combien d'utilisateurs ?", "chat_history": []})
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "DATA_QUERY"

@patch("backend.services.semantic_router.app.router.get_llm_provider")
def test_route_ambiguous_query(mock_get_llm):
    """Test routing an ambiguous query requiring clarification."""
    plan = SemanticPlanOut(
        intent=Intent.AMBIGUOUS,
        confidence=0.8,
        clarification_options=["Option A", "Option B"],
        source_tables=[],
        dimensions=[],
        filters=[]
    )

    mock_runnable = MagicMock()
    mock_runnable.invoke.return_value = plan

    mock_provider = MagicMock()
    mock_provider.with_structured_output.return_value = mock_runnable
    mock_get_llm.return_value = mock_provider

    with patch("langchain_core.prompts.ChatPromptTemplate.__or__", return_value=mock_runnable):
        response = client.post("/internal/plan", json={"query": "Le CA total", "chat_history": []})
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "AMBIGUOUS"
        assert len(data["clarification_options"]) == 2

def test_route_empty_query():
    """An empty query should be rejected."""
    response = client.post("/internal/plan", json={"query": "   ", "chat_history": []})
    assert response.status_code == 400


# ── 2. Catalog Tests ─────────────────────────────────────────────

@patch("requests.post")
def test_catalog_search(mock_post):
    """Catalog search should return schema from catalog service."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "content": "Registered users table",
                "metadata": {
                    "table_name": "users",
                    "columns": ["id", "created_at", "country"]
                }
            }
        ]
    }
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    response = client.post("/internal/catalog/search", json={
        "query": "utilisateurs et ventes",
        "tenant_id": "acme"
    })
    assert response.status_code == 200
    data = response.json()

    assert "tables" in data
    assert len(data["tables"]) > 0

    # Check structure of the first table
    table = data["tables"][0]
    assert table["name"] == "users"
    assert "columns" in table
    assert len(table["columns"]) == 3

def test_catalog_search_empty_query():
    """An empty query should be rejected."""
    response = client.post("/internal/catalog/search", json={
        "query": "  ",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
