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

def test_create_dashboard():
    response = client.post(
        "/internal/dashboards?tenant_id=t1&user_id=u1",
        json={
            "name": "My Dashboard",
            "description": "Test",
            "visibility": "private",
            "items": []
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "created"
    
def test_get_dashboards():
    response = client.get("/internal/dashboards?tenant_id=t1&user_id=u1")
    assert response.status_code == 200
    dashboards = response.json()
    assert len(dashboards) >= 1
    assert dashboards[0]["name"] == "My Dashboard"
    assert dashboards[0]["visibility"] == "private"

def test_tenant_isolation():
    response = client.get("/internal/dashboards?tenant_id=t2&user_id=u2")
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_add_item_to_dashboard():
    # Setup message first
    db = next(get_db())
    conv = Conversation(tenant_id="t1", user_id="u1", title="test")
    db.add(conv)
    db.flush()
    msg = Message(conversation_id=conv.id, role="assistant", content="test", payload={"results": [{"a": 1}]})
    db.add(msg)
    db.commit()

    # Create dashboard
    res = client.post(
        "/internal/dashboards?tenant_id=t1&user_id=u1",
        json={"name": "Dash 2"}
    )
    dash_id = res.json()["id"]

    # Add item
    res_item = client.post(
        f"/internal/dashboards/{dash_id}/items?tenant_id=t1&user_id=u1",
        json={"source_message_id": msg.id, "title": "My Item", "order": 0}
    )
    assert res_item.status_code == 200

    # Verify item exists
    res_get = client.get(f"/internal/dashboards/{dash_id}?tenant_id=t1&user_id=u1")
    assert res_get.status_code == 200
    items = res_get.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "My Item"
    assert items[0]["results"] == [{"a": 1}]
