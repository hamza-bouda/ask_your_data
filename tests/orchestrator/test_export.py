import pytest
from fastapi.testclient import TestClient
from backend.services.orchestrator.app.main import app
from backend.services.orchestrator.app.database import Base, engine, get_db
from backend.services.orchestrator.app.orm_models import Conversation, Message

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_export_csv_injection():
    db = next(get_db())
    conv = Conversation(tenant_id="t1", user_id="u1", title="test")
    db.add(conv)
    db.flush()
    msg = Message(
        conversation_id=conv.id, 
        role="assistant", 
        content="test", 
        payload={
            "results": [
                {"name": "Alice", "formula": "=1+1"},
                {"name": "Bob", "formula": "@sum(1)"},
                {"name": "Charlie", "formula": "+A1"},
                {"name": "Dave", "formula": "-B2"}
            ]
        }
    )
    db.add(msg)
    db.commit()

    response = client.get(f"/internal/results/{msg.id}/export?format=csv&tenant_id=t1&user_id=u1")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    
    # Check that dangerous characters are escaped with a single quote
    assert "'=1+1" in content
    assert "'@sum(1)" in content
    assert "'+A1" in content
    assert "'-B2" in content

def test_export_unauthorized_tenant():
    db = next(get_db())
    conv = Conversation(tenant_id="t1", user_id="u1", title="test")
    db.add(conv)
    db.flush()
    msg = Message(conversation_id=conv.id, role="assistant", content="test", payload={"results": [{"a": 1}]})
    db.add(msg)
    db.commit()

    response = client.get(f"/internal/results/{msg.id}/export?format=csv&tenant_id=t2&user_id=u2")
    assert response.status_code == 404
