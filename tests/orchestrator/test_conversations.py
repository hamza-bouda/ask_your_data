import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy import text

os.environ["TESTING"] = "1"

from backend.services.orchestrator.app.main import app
from backend.services.orchestrator.app.database import create_tables, get_db, Base, engine
from backend.services.orchestrator.app.orm_models import Conversation, Message

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    with engine.begin() as conn:
        for t in ["export_audits", "dashboard_items", "dashboards", "runs", "messages", "conversations"]:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
    Base.metadata.create_all(bind=engine)
    yield


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

class MockRedis:
    async def xadd(self, stream, payload):
        pass

@patch("backend.services.orchestrator.app.main.get_redis_client", return_value=MockRedis())
def test_send_message_and_graph_execution(mock_redis):
    # Create conv
    conv_resp = client.post("/internal/conversations", json={"tenant_id": "t1", "user_id": "u1", "title": "Chat"})
    conv_id = conv_resp.json()["id"]

    # Send message (asynchronous background queueing)
    resp = client.post(f"/internal/conversations/{conv_id}/messages", json={
        "tenant_id": "t1",
        "user_id": "u1",
        "message": "What are sales?"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "pending"
    assert "run_id" in data

    # Verify message was stored in DB
    db = next(get_db())
    messages = db.query(Message).filter(Message.conversation_id == conv_id).all()
    assert len(messages) >= 1
    assert messages[0].content == "What are sales?"
    assert messages[0].role == "user"
