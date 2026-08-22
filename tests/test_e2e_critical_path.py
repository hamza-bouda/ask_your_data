"""Black-box E2E contract for the complete critical path."""

import json
import os
import httpx
import pytest

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000")
E2E_DB_URL = os.getenv("E2E_DB_URL", "postgresql://askyourdata:askyourdata_dev@postgres:5432/askyourdata")

@pytest.fixture(scope="module")
def api_client():
    with httpx.Client(base_url=GATEWAY_URL, timeout=30.0) as client:
        yield client

@pytest.fixture(scope="module")
def auth_headers(api_client):
    response = api_client.post("/api/v1/auth/login", json={"username": "hamza", "password": "password"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}

def test_full_critical_path(api_client, auth_headers):
    # 1. Connect a new database
    response = api_client.post("/api/v1/catalog/register", headers=auth_headers, json={
        "name": "E2E Critical Path DB", "connection_string": E2E_DB_URL,
    })
    assert response.status_code == 200, response.text
    source_id = response.json()["id"]

    # 2. Sync database
    response = api_client.post(f"/v1/datasources/{source_id}/sync", headers=auth_headers)
    assert response.status_code == 200, response.text

    # 3. Allowlist a table and a column
    response = api_client.get(f"/v1/datasources/{source_id}/catalog", headers=auth_headers)
    assert response.status_code == 200, response.text
    catalog = response.json()
    assert "tables" in catalog and len(catalog["tables"]) > 0
    
    # We will just take the first table that has columns
    table = next(item for item in catalog["tables"] if item["columns"])
    table_id = table["id"]
    column_id = table["columns"][0]["id"]
    table_name = table["table_name"]

    response = api_client.patch(f"/v1/datasources/{source_id}/catalog/tables/{table_id}", headers=auth_headers, json={"is_allowed": True})
    assert response.status_code == 200, response.text
    response = api_client.patch(f"/v1/datasources/{source_id}/catalog/tables/{table_id}/columns/{column_id}", headers=auth_headers, json={"is_allowed": True})
    assert response.status_code == 200, response.text

    # 4. Create conversation
    headers = {**auth_headers, "X-Source-Id": source_id}
    response = api_client.post("/v1/conversations", headers=headers, json={"title": "E2E Test"})
    assert response.status_code == 200, response.text
    conversation_id = response.json()["id"]

    # 5. Send message and get SQL Result
    response = api_client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"message": f"Combien de lignes contient la table {table_name} ?"},
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
    
    final_message_id = run["final_message_id"]

    # 6. Dashboard: Create and save item
    dashboard_payload = {
        "name": "E2E Dashboard",
        "description": "Created by E2E test",
        "visibility": "private"
    }
    response = api_client.post("/v1/dashboards", headers=headers, json=dashboard_payload)
    assert response.status_code == 200, response.text
    dashboard_id = response.json()["id"]

    item_payload = {
        "source_message_id": final_message_id,
        "title": "E2E Chart",
        "order": 0
    }
    response = api_client.post(f"/v1/dashboards/{dashboard_id}/items", headers=headers, json=item_payload)
    assert response.status_code == 200, response.text

    # 7. Export CSV
    response = api_client.get(f"/v1/results/{final_message_id}/export?format=csv", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers.get("content-type", "").startswith("text/csv")
    
    # We shouldn't be able to read it without correct source_id
    bad_headers = {**auth_headers, "X-Source-Id": "non-existent-source"}
    response_bad = api_client.get(f"/v1/results/{final_message_id}/export?format=csv", headers=bad_headers)
    assert response_bad.status_code == 404, "Export should fail if source_id doesn't match"

    # We shouldn't be able to query a non-allowed table (Deny-All)
    response = api_client.post(
        f"/v1/conversations/{conversation_id}/messages",
        headers=headers,
        json={"message": f"Select all from forbidden_table"},
    )
    assert response.status_code == 200, response.text
    run_id2 = response.json()["run_id"]
    
    terminal_event2 = None
    with api_client.stream("GET", f"/v1/runs/{run_id2}/events", headers=headers, timeout=60.0) as stream:
        for line in stream.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line.split(":", 1)[1].strip())
            if event.get("event_type") in {"result_ready", "run_failed"}:
                terminal_event2 = event
                break
                
    response2 = api_client.get(f"/v1/runs/{run_id2}", headers=headers)
    run2 = response2.json()
    assert run2["status"] in ["failed", "error"]
    assert "politique de sécurité" in run2.get("error_message", "").lower() or "deny-all" in run2.get("error_message", "").lower() or "accès" in run2.get("error_message", "").lower()
