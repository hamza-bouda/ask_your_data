"""Tests for the SQL Generator Service — Phase 08 Definition of Done."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.services.sql_generator.app.main import app
from backend.services.sql_generator.app.models import SqlDraft

client = TestClient(app)

MOCK_SCHEMA = {
    "users": {
        "description": "Registered users",
        "columns": [
            {"name": "id", "type": "uuid", "description": "Primary key"}
        ]
    }
}

@patch("backend.services.sql_generator.app.generator.ChatOpenAI")
def test_generate_sql_count_users(MockChatOpenAI):
    """Test generating a SQL query for counting users."""
    mock_llm = MagicMock()
    MockChatOpenAI.return_value = mock_llm
    
    mock_chain = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain
    
    # The actual chain is prompt | structured_llm, so invoke is called on the sequence
    # To mock prompt | structured_llm, we can patch invoke on the chain or the module level.
    # Actually, it's easier to patch the generator's internal chain or invoke method.
    pass # Wait, let's patch the whole chain invoke or use a different approach.

# Let's patch ChatPromptTemplate | ChatOpenAI directly by patching RunnableSequence.invoke, or just patch _get_llm and its with_structured_output.
# Wait, `chain = prompt | structured_llm`. Mocking structured_llm means `chain.invoke()` will call `structured_llm.invoke()`.
# Let's patch `backend.services.sql_generator.app.generator._get_llm`.

@patch("backend.services.sql_generator.app.generator._get_llm")
def test_generate_sql_endpoint(mock_get_llm):
    """Test the SQL generation endpoint."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    
    mock_get_llm.return_value = mock_llm
    mock_llm.with_structured_output.return_value = mock_structured
    
    # structured_llm.invoke is called when the chain runs
    mock_structured.invoke.return_value = SqlDraft(
        intent="Count users",
        metric="count",
        dimensions=[],
        filters=[],
        sql_query="SELECT COUNT(*) FROM users;",
        confidence=0.9,
        explanation="Counts all users."
    )
    
    response = client.post("/internal/generate-sql", json={
        "query": "Combien y a-t-il d'utilisateurs ?",
        "schema_definition": MOCK_SCHEMA
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["sql_query"] == "SELECT COUNT(*) FROM users;"
    assert data["metric"] == "count"
    assert data["confidence"] == 0.9

@patch("backend.services.sql_generator.app.generator._get_llm")
def test_repair_sql_endpoint(mock_get_llm):
    """Test the SQL repair endpoint."""
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    
    mock_get_llm.return_value = mock_llm
    mock_llm.with_structured_output.return_value = mock_structured
    
    mock_structured.invoke.return_value = SqlDraft(
        intent="Count users",
        metric="count",
        dimensions=[],
        filters=[],
        sql_query="SELECT COUNT(*) FROM users;",
        confidence=0.99,
        explanation="Fixed syntax."
    )
    
    response = client.post("/internal/repair-sql", json={
        "query": "Combien d'utilisateurs ?",
        "schema_definition": MOCK_SCHEMA,
        "previous_sql": "SELECT COUN(*) FROM users;",
        "error_message": "function coun() does not exist"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["sql_query"] == "SELECT COUNT(*) FROM users;"

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
        "schema_definition": {}
    })
    assert response.status_code == 400
