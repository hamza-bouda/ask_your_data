"""Tests for the SQL Generator Service."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from backend.services.sql_generator.app.main import app
from backend.services.sql_generator.app.models import SqlDraft
from contracts.llm import BaseLLMProvider

client = TestClient(app)

MOCK_SCHEMA = {
    "users": {
        "description": "Registered users",
        "columns": [
            {"name": "id", "type": "uuid", "description": "Primary key"}
        ]
    }
}


class MockGeneratorLLM(BaseLLMProvider):
    def __init__(self, draft: SqlDraft):
        self.draft = draft

    def get_chat_model(self):
        return self

    def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        return self.draft.sql_query

    def generate_structured_output(self, prompt: str, schema: dict, system_prompt: str = "") -> dict:
        return self.draft.model_dump()

    def with_structured_output(self, schema_cls):
        return RunnableLambda(lambda _: self.draft)


def test_generate_sql_endpoint():
    """Test the SQL generation endpoint."""
    expected_draft = SqlDraft(
        intent="Count users",
        metric="count",
        dimensions=[],
        filters=[],
        sql_query="SELECT COUNT(id) FROM users;",
        confidence=0.9,
        explanation="Counts all users."
    )
    provider = MockGeneratorLLM(expected_draft)

    with patch("backend.services.sql_generator.app.generator.get_llm_provider", return_value=provider), \
         patch.dict("os.environ", {"LLM_PROVIDER": "deepseek"}):
        response = client.post("/internal/generate-sql", json={
            "query": "Combien y a-t-il d'utilisateurs ?",
            "semantic_plan": {},
            "schema_definition": MOCK_SCHEMA,
            "chat_history": []
        })

    assert response.status_code == 200
    data = response.json()
    assert data["sql_query"] == "SELECT COUNT(id) FROM users;"
    assert data["metric"] == "count"
    assert data["confidence"] == 0.9


def test_repair_sql_endpoint():
    """Test the SQL repair endpoint."""
    expected_draft = SqlDraft(
        intent="Count users",
        metric="count",
        dimensions=[],
        filters=[],
        sql_query="SELECT COUNT(id) FROM users;",
        confidence=0.99,
        explanation="Fixed syntax."
    )
    provider = MockGeneratorLLM(expected_draft)

    with patch("backend.services.sql_generator.app.generator.get_llm_provider", return_value=provider), \
         patch.dict("os.environ", {"LLM_PROVIDER": "deepseek"}):
        response = client.post("/internal/repair-sql", json={
            "query": "Combien d'utilisateurs ?",
            "schema_definition": MOCK_SCHEMA,
            "previous_sql": "SELECT COUN(id) FROM users;",
            "error_message": "function coun() does not exist"
        })

    assert response.status_code == 200
    data = response.json()
    assert data["sql_query"] == "SELECT COUNT(id) FROM users;"


def test_generate_sql_empty_query():
    """An empty query should be rejected."""
    response = client.post("/internal/generate-sql", json={
        "query": "   ",
        "semantic_plan": {},
        "schema_definition": MOCK_SCHEMA
    })
    assert response.status_code == 400


def test_generate_sql_empty_schema():
    """An empty schema should be rejected."""
    response = client.post("/internal/generate-sql", json={
        "query": "Combien d'utilisateurs ?",
        "semantic_plan": {},
        "schema_definition": {}
    })
    assert response.status_code == 400
