import pytest
from httpx import AsyncClient
import asyncio
import json
from backend.services.orchestrator.app.main import app, get_db
from backend.services.orchestrator.app.orm_models import Conversation, Message, Run

@pytest.fixture
def override_get_db():
    from backend.services.orchestrator.app.database import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def _get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def mock_redis(mocker):
    class AsyncMockRedis:
        def __init__(self):
            self.xadd_calls = []
            self.xread_calls = 0
            
        async def xadd(self, stream, payload):
            self.xadd_calls.append((stream, payload))
            
        async def xread(self, streams, count=None, block=None):
            self.xread_calls += 1
            if self.xread_calls == 1:
                # First call returns some events
                return [
                    (list(streams.keys())[0], [
                        ("1-0", {"event": json.dumps({"event_type": "run_started"})}),
                        ("2-0", {"event": json.dumps({"event_type": "result_ready", "status": "completed"})})
                    ])
                ]
            return []
            
        async def close(self):
            pass

    mock_instance = AsyncMockRedis()
    mocker.patch("backend.services.orchestrator.app.main.get_redis_client", return_value=mock_instance)
    mocker.patch("backend.services.orchestrator.app.redis_client.get_redis_client", return_value=mock_instance)
    return mock_instance

@pytest.mark.asyncio
async def test_sse_flow_and_run_creation(override_get_db, mock_redis):
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create a conversation
        conv_resp = await client.post("/internal/conversations", json={
            "tenant_id": "test_tenant",
            "user_id": "test_user",
            "title": "Test SSE"
        })
        conv_id = conv_resp.json()["id"]
        
        # Send a message
        msg_resp = await client.post(f"/internal/conversations/{conv_id}/messages", json={
            "tenant_id": "test_tenant",
            "user_id": "test_user",
            "message": "Show me data"
        })
        assert msg_resp.status_code == 200
        data = msg_resp.json()
        assert data["status"] == "pending"
        run_id = data["run_id"]
        
        # Verify Redis XADD was called for tasks
        assert len(mock_redis.xadd_calls) == 1
        assert mock_redis.xadd_calls[0][0] == "stream:tasks:runs"
        assert mock_redis.xadd_calls[0][1]["run_id"] == run_id
        
        # Connect to SSE
        events = []
        async with client.stream("GET", f"/internal/runs/{run_id}/events", params={"tenant_id": "test_tenant", "user_id": "test_user"}) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
                    
        # Check events were streamed from mock_redis
        assert len(events) == 2
        assert events[0]["event_type"] == "run_started"
        assert events[1]["event_type"] == "result_ready"

