"""Tests for the Semantic Router Service."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.services.semantic_router.app.main import app
from backend.services.semantic_router.app.router import SemanticPlanOut, Intent

client = TestClient(app)

@patch("backend.services.semantic_router.app.router._get_llm")
def test_route_data_query(mock_get_llm):
    """Test routing a normal data query."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_get_llm.return_value = mock_llm
    mock_llm.with_structured_output.return_value = mock_structured
    
    mock_structured.invoke.return_value = SemanticPlanOut(
        intent=Intent.DATA_QUERY,
        confidence=0.9,
        clarification_options=[],
        source_tables=[],
        dimensions=[],
        filters=[]
    )
    
    response = client.post("/internal/plan", json={"query": "Combien d'utilisateurs ?", "chat_history": []})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "DATA_QUERY"

@patch("backend.services.semantic_router.app.router._get_llm")
def test_route_ambiguous_query(mock_get_llm):
    """Test routing an ambiguous query requiring clarification."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_get_llm.return_value = mock_llm
    mock_llm.with_structured_output.return_value = mock_structured
    
    mock_structured.invoke.return_value = SemanticPlanOut(
        intent=Intent.AMBIGUOUS,
        confidence=0.8,
        clarification_options=["Option A", "Option B"],
        source_tables=[],
        dimensions=[],
        filters=[]
    )
    
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

def test_catalog_search():
    """Catalog search should return a mocked schema."""
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
    assert "name" in table
    assert "description" in table
    assert "columns" in table
    
    # Check structure of the first column
    col = table["columns"][0]
    assert "name" in col
    assert "type" in col
    assert "description" in col

def test_catalog_search_empty_query():
    """An empty query should be rejected."""
    response = client.post("/internal/catalog/search", json={
        "query": "", 
        "tenant_id": "acme"
    })
    assert response.status_code == 400
