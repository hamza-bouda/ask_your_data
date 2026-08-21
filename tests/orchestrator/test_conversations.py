import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

os.environ["TESTING"] = "1"

from backend.services.orchestrator.app.main import app
from backend.services.orchestrator.app.database import create_tables, get_db, Base, engine
from backend.services.orchestrator.app.orm_models import Conversation, Message

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_conversation():
    response = client.post("/internal/conversations", json={
        "tenant_id": "tenant1",
        "user_id": "user1",
        "title": "My Test Chat"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant1"
    assert data["title"] == "My Test Chat"
    assert "id" in data

def test_list_conversations_isolation():
    client.post("/internal/conversations", json={"tenant_id": "t1", "user_id": "u1", "title": "Chat 1"})
    client.post("/internal/conversations", json={"tenant_id": "t2", "user_id": "u2", "title": "Chat 2"})

    # t1/u1 should only see Chat 1
    resp1 = client.get("/internal/conversations", params={"tenant_id": "t1", "user_id": "u1"})
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) == 1
    assert data1[0]["title"] == "Chat 1"

def test_get_conversation_with_messages():
    conv_resp = client.post("/internal/conversations", json={"tenant_id": "t1", "user_id": "u1", "title": "Test Chat"})
    conv_id = conv_resp.json()["id"]

    # At this point, the conversation is empty
    resp = client.get(f"/internal/conversations/{conv_id}", params={"tenant_id": "t1", "user_id": "u1"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversation"]["id"] == conv_id
    assert len(data["messages"]) == 0

@patch("backend.services.orchestrator.app.main.orchestrator_graph")
def test_send_message_and_graph_execution(mock_graph):
    # Setup mock for LangGraph
    mock_graph.invoke.return_value = {
        "tenant_id": "t1",
        "user_id": "u1",
        "conversation_id": "some_id",
        "question": "Show me data",
        "run_id": "run1",
        "status": "executed",
        "results": [{"val": 100}],
        "semantic_plan": {"intent": "DATA_QUERY"},
        "sql_query": "SELECT 100 as val",
        "error_message": None,
        "clarification_options": None
    }

    conv_resp = client.post("/internal/conversations", json={"tenant_id": "t1", "user_id": "u1"})
    conv_id = conv_resp.json()["id"]

    resp = client.post(f"/internal/conversations/{conv_id}/messages", json={
        "tenant_id": "t1",
        "user_id": "u1",
        "message": "Show me data"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "executed"
    assert data["results"] == [{"val": 100}]

    # Check persistence
    resp2 = client.get(f"/internal/conversations/{conv_id}", params={"tenant_id": "t1", "user_id": "u1"})
    data2 = resp2.json()
    assert len(data2["messages"]) == 2 # 1 user, 1 assistant
    assert data2["messages"][0]["role"] == "user"
    assert data2["messages"][1]["role"] == "assistant"
    
    # Auto title should be set
    assert data2["conversation"]["title"].startswith("Show me data")
