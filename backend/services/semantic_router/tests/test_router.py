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
