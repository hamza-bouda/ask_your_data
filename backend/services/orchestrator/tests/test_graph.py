import pytest
from unittest.mock import patch
from backend.services.orchestrator.app.models import ConversationState
from backend.services.orchestrator.app.graph import visualization_node

class MockResponse:
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        
    def json(self):
        return self.json_data
        
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception("HTTP Error")

@patch("httpx.post")
def test_visualization_node_success(mock_post):
    mock_post.return_value = MockResponse({
        "chart_type": "bar",
        "title": "Bar Chart",
        "reason": "Test"
    }, 200)
    
    state = ConversationState(
        tenant_id="t1",
        user_id="u1",
        conversation_id="c1",
        question="test",
        run_id="r1",
        results=[{"a": 1, "b": "A"}]
    )
    
    res = visualization_node(state)
    assert res["status"] == "visualized"
    assert res["chart_spec"]["chart_type"] == "bar"

@patch("httpx.post")
def test_visualization_node_failure_fallback(mock_post):
    mock_post.return_value = MockResponse({"detail": "Error"}, 500)
    
    state = ConversationState(
        tenant_id="t1",
        user_id="u1",
        conversation_id="c1",
        question="test",
        run_id="r1",
        results=[{"a": 1, "b": "A"}]
    )
    
    res = visualization_node(state)
    assert res["status"] == "visualized"
    assert res["chart_spec"]["chart_type"] == "table"
    assert "indisponible" in res["chart_spec"]["reason"]
