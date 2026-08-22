"""Black-box E2E contract for the deterministic conversational workflow."""

import json
import os

import httpx
import pytest

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
E2E_DB_URL = os.getenv("E2E_DB_URL", "postgresql://askyourdata:askyourdata_dev@postgres:5432/askyourdata")


@pytest.fixture(scope="module")
def api_client():
    client = httpx.Client(base_url=GATEWAY_URL, timeout=5.0)
    try:
        resp = client.get("/health")
        if resp.status_code != 200:
            pytest.skip("Gateway service is not healthy or running.")
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip(f"Gateway service is not running on {GATEWAY_URL}")
    yield client
    client.close()


@pytest.fixture(scope="module")
def auth_headers(api_client):
    response = api_client.post("/api/v1/auth/login", json={"username": "hamza", "password": "password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture(scope="module")
def governed_source(api_client, auth_headers):
    """Create and explicitly allow one table, exactly as an admin would."""
    response = api_client.post("/api/v1/catalog/register", headers=auth_headers, json={
        "name": "E2E application catalog", "connection_string": E2E_DB_URL,
    })
    assert response.status_code == 200, response.text
    source_id = response.json()["id"]
    response = api_client.post(f"/v1/datasources/{source_id}/sync", headers=auth_headers)
    assert response.status_code == 200, response.text
    response = api_client.get(f"/v1/datasources/{source_id}/catalog", headers=auth_headers)
    assert response.status_code == 200, response.text
    table = next(item for item in response.json()["tables"] if item["columns"])
    response = api_client.patch(f"/v1/datasources/{source_id}/catalog/tables/{table['id']}", headers=auth_headers, json={"is_allowed": True})
    assert response.status_code == 200, response.text
    column = table["columns"][0]
    response = api_client.patch(f"/v1/datasources/{source_id}/catalog/tables/{table['id']}/columns/{column['id']}", headers=auth_headers, json={"is_allowed": True})
    assert response.status_code == 200, response.text
    return source_id, table["table_name"]


def test_health_endpoint(api_client):
    assert api_client.get("/health").status_code == 200


def test_full_catalog_conversation_sse(api_client, auth_headers, governed_source):
    source_id, allowed_table = governed_source
    headers = {**auth_headers, "X-Source-Id": source_id}
    response = api_client.get("/api/v1/catalog/sources", headers=auth_headers)
    assert response.status_code == 200
    assert all("connection_string" not in source for source in response.json()["sources"])
    response = api_client.post("/v1/conversations", headers=headers, json={"title": "E2E catalogue"})
    assert response.status_code == 200, response.text
    conversation_id = response.json()["id"]
    response = api_client.post(f"/v1/conversations/{conversation_id}/messages", headers=headers, json={"message": "Liste les tables disponibles dans le catalogue"})
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]
    events = []
    with api_client.stream("GET", f"/v1/runs/{run_id}/events", headers=headers, timeout=60.0) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            events.append(json.loads(line.split(":", 1)[1].strip()))
            if events[-1].get("event_type") in {"result_ready", "run_failed"}:
                break
    assert events, "No SSE events received"
    assert events[-1]["event_type"] == "result_ready", events[-1]
    response = api_client.get(f"/v1/runs/{run_id}", headers=headers)
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert allowed_table in run["response"]


def test_full_sql_conversation_sse_in_mock_mode(api_client, auth_headers, governed_source):
    source_id, allowed_table = governed_source
    headers = {**auth_headers, "X-Source-Id": source_id}
    response = api_client.post("/v1/conversations", headers=headers, json={"title": "E2E SQL"})
    assert response.status_code == 200, response.text
    conversation_id = response.json()["id"]
    response = api_client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"message": f"Combien de lignes contient la table {allowed_table} ?"},
    )
    assert response.status_code == 200, response.text
    run_id = response.json()["run_id"]

    terminal_event = None
    with api_client.stream("GET", f"/v1/runs/{run_id}/events", headers=headers, timeout=60.0) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line.split(":", 1)[1].strip())
            if event.get("event_type") in {"result_ready", "run_failed"}:
                terminal_event = event
                break
    assert terminal_event and terminal_event["event_type"] == "result_ready", terminal_event
    response = api_client.get(f"/v1/runs/{run_id}", headers=headers)
    assert response.status_code == 200
    run = response.json()
    assert run["status"] == "completed"
    assert run["results"] and "row_count" in run["results"][0]
    assert run["chart_spec"]["chart_type"] == "metric"
