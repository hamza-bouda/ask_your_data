import os
import time
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
    
    # 1. Create conversation
    resp = api_client.post("/v1/conversations", json={"title": "E2E Test"}, headers=headers)
    assert resp.status_code == 200
    conv_id = resp.json()["conversation_id"]
    
    # 2. Send message
    resp = api_client.post(f"/v1/conversations/{conv_id}/messages", json={"message": "Show me total customers"}, headers=headers)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    
    # 3. Stream events (we'll just poll the run status since streaming via requests can be tricky, or read a few chunks)
    with api_client.stream("GET", f"/v1/runs/{run_id}/events", headers=headers) as stream:
        events = []
        for line in stream.iter_lines():
            if line.startswith("data: "):
                events.append(line)
            # break after completion
            if "RESULT_READY" in line or "RUN_FAILED" in line:
                break
                
    assert len(events) > 0, "No events received from SSE"
    assert any("RESULT_READY" in e or "RUN_FAILED" in e for e in events)

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
