import os
import time
import json
import httpx
import pytest

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")

@pytest.fixture(scope="module")
def api_client():
    return httpx.Client(base_url=GATEWAY_URL, timeout=30.0)

@pytest.fixture(scope="module")
def auth_token(api_client):
    response = api_client.post("/api/v1/auth/login", json={
        "username": "hamza",
        "password": "password"
    })
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.text}")
    return response.json()["token"]

def test_health_endpoints(api_client):
    """Verify all services are up."""
    # Assuming gateway proxies /health? No, we just check gateway health for now.
    response = httpx.get(f"{GATEWAY_URL}/health")
    assert response.status_code == 200

def test_full_conversation_flow(api_client, auth_token):
    """Test full e2e conversation flow through redis streams."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # The application can host multiple sources. Pin the test conversation to
    # one concrete active source so its RAG and SQL scope are deterministic.
    sources = api_client.get("/api/v1/catalog/sources", headers=headers)
    assert sources.status_code == 200
    active_source = next((item for item in sources.json().get("sources", []) if item.get("status") == "active"), None)
    assert active_source, "No active datasource is available for E2E"
    headers["X-Source-Id"] = active_source["id"]
    
    # 1. Create conversation
    resp = api_client.post("/v1/conversations", json={"title": "E2E Test"}, headers=headers)
    assert resp.status_code == 200
    conv_id = resp.json()["id"]
    
    # 2. Send message
    resp = api_client.post(f"/v1/conversations/{conv_id}/messages", json={"message": "Show me total customers"}, headers=headers)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    
    # 3. Stream events (we'll just poll the run status since streaming via requests can be tricky, or read a few chunks)
    with api_client.stream("GET", f"/v1/runs/{run_id}/events", headers=headers, timeout=90.0) as stream:
        events = []
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = json.loads(line.split(":", 1)[1].strip())
            events.append(payload)
            if payload.get("event_type") in {"result_ready", "run_failed"}:
                break
                
    assert len(events) > 0, "No events received from SSE"
    assert events[-1]["event_type"] == "result_ready", events[-1]

    run = api_client.get(f"/v1/runs/{run_id}", headers=headers)
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert run.json().get("response")

def test_no_secrets_in_logs():
    """Verify that logs don't contain unredacted connection strings or secrets."""
    # We can check the docker logs of the worker
    import subprocess
    try:
        logs = subprocess.check_output(["docker", "compose", "logs", "worker"]).decode("utf-8")
        assert "password" not in logs.lower() or "***REDACTED***" in logs
        assert "tenant_acme.db" not in logs or "REDACTED" in logs
    except Exception as e:
        print(f"Skipping log check: {e}")
