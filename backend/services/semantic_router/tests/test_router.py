import pytest
from app.router import create_semantic_plan

def test_semantic_plan_data_query(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    query = "Quel est le chiffre d'affaires total par client en 2023 ?"
    context = {
        "tables": ["sales", "customers"],
        "metrics": [{"name": "Chiffre d'affaires", "description": "Total revenue", "sql_expression": "SUM(amount)"}]
    }
    chat_history = []
    
    plan = create_semantic_plan(query, context, chat_history)
    
    assert plan["intent"] == "DATA_QUERY"
    assert "sales" in plan["source_tables"] or "customers" in plan["source_tables"]
    assert plan["metric"] is not None
    assert plan["confidence"] > 0.5

def test_semantic_plan_ambiguous(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    query = "Montre-moi les données"
    context = {
        "tables": ["sales", "customers", "products"]
    }
    chat_history = []
    
    plan = create_semantic_plan(query, context, chat_history)
    
    assert plan["intent"] == "AMBIGUOUS"
    assert len(plan["clarification_options"]) > 0

def test_semantic_plan_unrelated(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    query = "Bonjour, comment ça va ?"
    context = {}
    chat_history = []
    
    plan = create_semantic_plan(query, context, chat_history)
    
    assert plan["intent"] == "UNRELATED"


def test_catalog_request_is_deterministic_even_with_mock_llm(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    plan = create_semantic_plan(
        "Donne-moi les noms des tables disponibles dans notre base de données",
        {"tables": ["artist", "album"]},
        [],
    )

    assert plan["intent"] == "CATALOG_QUERY"
    assert plan["source_tables"] == ["artist", "album"]


def test_router_failure_fails_closed(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setattr("app.router._get_llm", lambda: (_ for _ in ()).throw(RuntimeError("offline")))

    plan = create_semantic_plan("Quel est le total des ventes ?", {"tables": ["sales"]}, [])

    assert plan["intent"] == "AMBIGUOUS"
    assert plan["confidence"] == 0.0
