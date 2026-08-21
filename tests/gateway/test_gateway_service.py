"""Tests for the Gateway Service — Phase 03 Definition of Done."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
import json

from backend.services.gateway.app.main import app

client = TestClient(app)

# ── Mocking Utilities ───────────────────────────────────────────

def get_mock_tenant_context():
    return {
        "tenant_id": "acme",
        "user_id": "hamza",
        "roles": ["analyst"],
        "permissions": ["query"]
    }

class MockHttpxResponse:
    def __init__(self, json_data, status_code=200):
        self._json_data = json_data
        self.status_code = status_code

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("POST", "http://test")
            raise httpx.HTTPStatusError("Error", request=request, response=self)

class MockAsyncClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def post(self, url, json=None, headers=None, timeout=None):
        if "identity" in url:
            if json and json.get("token") == "valid_token":
                return MockHttpxResponse(get_mock_tenant_context(), 200)
            return MockHttpxResponse({"detail": "Invalid token"}, 401)
        elif "orchestrator" in url:
            return MockHttpxResponse({"id": "conv-123"}, 200)
        return MockHttpxResponse({}, 404)

# ── 1. Authentication Tests ─────────────────────────────────────

@patch("backend.services.gateway.app.dependencies.httpx.AsyncClient", new=MockAsyncClient)
@patch("backend.services.gateway.app.main.check_rate_limit", new_callable=AsyncMock)
def test_create_conversation_valid_token(mock_check_rate_limit):
    """A valid token routes to orchestrator and returns 200."""
    response = client.post(
        "/v1/conversations",
        headers={"Authorization": "Bearer valid_token"},
        json={"title": "Test Chat"}
    )
    assert response.status_code == 200
    assert response.json() == {"id": "conv-123"}
    # Verify correlation ID is injected
    assert "x-correlation-id" in response.headers

@patch("backend.services.gateway.app.dependencies.httpx.AsyncClient", new=MockAsyncClient)
@patch("backend.services.gateway.app.main.check_rate_limit", new_callable=AsyncMock)
def test_create_conversation_invalid_token(mock_check_rate_limit):
    """An invalid token is rejected with 401."""
    response = client.post(
        "/v1/conversations",
        headers={"Authorization": "Bearer invalid"},
        json={"title": "Test Chat"}
    )
    assert response.status_code == 401
    
@patch("backend.services.gateway.app.dependencies.httpx.AsyncClient", new=MockAsyncClient)
@patch("backend.services.gateway.app.main.check_rate_limit", new_callable=AsyncMock)
def test_create_conversation_missing_token(mock_check_rate_limit):
    """Every protected endpoint rejects missing authentication."""
    response = client.post("/v1/conversations", json={"title": "Test Chat"})
    assert response.status_code == 401


def test_token_query_is_rejected_by_default():
    """Bearer tokens must not silently be accepted from arbitrary query URLs."""
    response = client.get("/v1/conversations?token=valid_token")
    assert response.status_code == 401


# ── 2. Rate Limiting Tests ──────────────────────────────────────

@patch("backend.services.gateway.app.dependencies.httpx.AsyncClient", new=MockAsyncClient)
def test_rate_limit_exceeded():
    """If check_rate_limit throws 429, the gateway returns 429."""
    from fastapi import HTTPException
    
    async def mock_rate_limit_fail(user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    with patch("backend.services.gateway.app.main.check_rate_limit", side_effect=mock_rate_limit_fail):
        response = client.post(
            "/v1/conversations",
            headers={"Authorization": "Bearer valid_token"},
            json={"title": "Test Chat"}
        )
        assert response.status_code == 429
        error_text = (response.json().get("message") or response.json().get("detail") or "")
        assert "Rate limit" in error_text


# ── 3. SSE Streaming Tests ──────────────────────────────────────

def test_sse_streaming_format():
    """Verify that the SSE endpoint returns a streaming response with the correct headers."""
    # We'll just mock the inner generator to yield a couple of events
    async def mock_event_stream(run_id, corr_id):
        yield "event: message\ndata: {\"status\": \"started\"}\n\n"
        yield "event: message\ndata: {\"status\": \"completed\"}\n\n"

    with patch("backend.services.gateway.app.main._orchestrator_event_stream", side_effect=mock_event_stream):
        with patch("backend.services.gateway.app.dependencies.httpx.AsyncClient", new=MockAsyncClient):
            response = client.get(
                "/v1/runs/run-123/events",
                headers={"Authorization": "Bearer valid_token"}
            )
            
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers["cache-control"] == "no-cache"
            
            content = response.content.decode("utf-8")
            assert "event: message" in content
            assert "started" in content
            assert "completed" in content
