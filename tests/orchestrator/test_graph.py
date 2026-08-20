"""Tests for the Orchestrator LangGraph pipeline — Phase 07 Definition of Done."""

import pytest
import httpx
from unittest.mock import patch

from backend.services.orchestrator.app.graph import orchestrator_graph
from backend.services.orchestrator.app.models import ConversationState

# ── 1. Graph Transition Tests ────────────────────────────────────

def test_graph_ambiguity_clarification():
    """Test transition: ambiguous -> clarify -> end."""
    state = ConversationState(
        tenant_id="acme",
        question="Can you clarify the revenue?",
        run_id="test-1"
    )
    
    # Run the graph
    result = orchestrator_graph.invoke(state.model_dump())
    
    # Should stop at classification because 'clarify' triggers needs_clarification
    assert result["status"] == "needs_clarification"
    assert "clarification_options" in result
    assert len(result["clarification_options"]) > 0

@patch("httpx.post")
def test_graph_happy_path(mock_post):
    """Test transition: classify -> retrieve -> plan -> sql -> execute -> success."""
    
    # Mock both the SQL generator and Executor endpoints
    def mock_post_side_effect(url, **kwargs):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
            def json(self): return self.json_data
            def raise_for_status(self): pass
            
        if "generate-sql" in url:
            return MockResponse({"sql_query": "SELECT * FROM sales"}, 200)
        elif "execute-sql" in url:
            return MockResponse({"results": [{"id": 1, "amount": 100}]}, 200)
            
    mock_post.side_effect = mock_post_side_effect
    
    state = ConversationState(
        tenant_id="acme",
        question="Show me sales",
        run_id="test-2"
    )
    
    result = orchestrator_graph.invoke(state.model_dump())
    
    assert result["status"] == "executed"
    assert result["sql_query"] == "SELECT * FROM sales"
    assert result["results"] == [{"id": 1, "amount": 100}]


@patch("httpx.post")
def test_graph_sql_refused_stop(mock_post):
    """Test transition: SQL validation fail -> repair -> limit reached -> stop."""
    
    # Mock generator returning bad SQL, executor returning 400 (validation fail)
    def mock_post_side_effect(url, **kwargs):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code
            def json(self): return self.json_data
            def raise_for_status(self): pass
            
        if "generate-sql" in url:
            return MockResponse({"sql_query": "DROP TABLE sales"}, 200)
        elif "execute-sql" in url:
            return MockResponse({"detail": "Forbidden keyword detected"}, 400)
            
    mock_post.side_effect = mock_post_side_effect
    
    state = ConversationState(
        tenant_id="acme",
        question="Drop the table",
        run_id="test-3",
        repair_budget=1  # Only 1 repair attempt
    )
    
    result = orchestrator_graph.invoke(state.model_dump())
    
    assert result["status"] == "error"
    assert result["repair_budget"] == 0
    assert "Repair budget exceeded" in result["error_message"]
    assert "Forbidden keyword detected" in result["error_message"]

