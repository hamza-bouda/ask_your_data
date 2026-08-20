"""Tests for the SQL Generator Service — Phase 05 Definition of Done."""

import pytest
from fastapi.testclient import TestClient

from backend.services.sql_generator.app.main import app

client = TestClient(app)

# Dummy schema for testing
MOCK_SCHEMA = [
    {
        "name": "users",
        "description": "Registered users",
        "columns": [
            {"name": "id", "type": "uuid", "description": "Primary key"}
        ]
    }
]

def test_generate_sql_count_users():
    """Test generating a SQL query for counting users."""
    response = client.post("/internal/generate-sql", json={
        "query": "Combien y a-t-il d'utilisateurs ?",
        "schema_definition": MOCK_SCHEMA
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "sql_query" in data
    assert "explanation" in data
    assert "SELECT COUNT(*)" in data["sql_query"].upper()

def test_generate_sql_sum_sales():
    """Test generating a SQL query for summing sales."""
    response = client.post("/internal/generate-sql", json={
        "query": "Quel est le total des ventes ?",
        "schema_definition": MOCK_SCHEMA
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "SELECT SUM(" in data["sql_query"].upper()

def test_generate_sql_fallback():
    """Test the fallback query generation."""
    response = client.post("/internal/generate-sql", json={
        "query": "Fais un truc aléatoire",
        "schema_definition": MOCK_SCHEMA
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "SELECT * FROM USERS" in data["sql_query"].upper()

def test_generate_sql_empty_query():
    """An empty query should be rejected."""
    response = client.post("/internal/generate-sql", json={
        "query": "   ",
        "schema_definition": MOCK_SCHEMA
    })
    assert response.status_code == 400

def test_generate_sql_empty_schema():
    """An empty schema should be rejected."""
    response = client.post("/internal/generate-sql", json={
        "query": "Combien d'utilisateurs ?",
        "schema_definition": []
    })
    assert response.status_code == 400
