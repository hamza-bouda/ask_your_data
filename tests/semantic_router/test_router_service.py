"""Tests for the Semantic Router Service — Phase 04 Definition of Done."""

import pytest
from fastapi.testclient import TestClient

from backend.services.semantic_router.app.main import app

client = TestClient(app)

# ── 1. Router Tests ──────────────────────────────────────────────

def test_route_data_query():
    """A standard query should be routed as DATA_QUERY."""
    response = client.post("/internal/route", json={"query": "Combien y a-t-il d'utilisateurs ?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "DATA_QUERY"
    assert data["confidence"] > 0.0

def test_route_chart_generation():
    """A query asking for a chart should be routed as CHART_GENERATION."""
    response = client.post("/internal/route", json={"query": "Fais-moi un graphique des ventes"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "CHART_GENERATION"
    assert data["confidence"] > 0.0

def test_route_unrelated():
    """A chit-chat query should be routed as UNRELATED."""
    response = client.post("/internal/route", json={"query": "Donne-moi une recette de crêpes"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "UNRELATED"
    assert data["confidence"] > 0.0

def test_route_empty_query():
    """An empty query should be rejected."""
    response = client.post("/internal/route", json={"query": "   "})
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
