"""Tests for the SQL Executor Service — Multi-tenant isolation and security guardrails."""

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from backend.services.sql_executor.app.main import app

client = TestClient(app)


def setup_module(module):
    """Setup dummy databases for tenant isolation tests."""
    engine1 = create_engine("sqlite:///tenant_acme.db")
    with engine1.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("INSERT INTO users (name) VALUES ('Alice')"))
        conn.commit()

    engine2 = create_engine("sqlite:///tenant_stark.db")
    with engine2.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("INSERT INTO users (name) VALUES ('Tony'), ('Pepper')"))
        conn.commit()


def teardown_module(module):
    """Clean up sqlite files."""
    for f in ("tenant_acme.db", "tenant_stark.db"):
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass


# ── 1. Execution & Isolation Tests ───────────────────────────────

def mock_get_tenant_db_url(tenant_id, source_id=None):
    return f"sqlite:///tenant_{tenant_id}.db"

def mock_get_allowed_schema(tenant_id, source_id=None):
    return {"users": {"id", "name"}}

@patch("backend.services.sql_executor.app.connection_manager.get_tenant_db_url", side_effect=mock_get_tenant_db_url)
@patch("backend.services.sql_executor.app.executor.get_allowed_schema", side_effect=mock_get_allowed_schema)
def test_execute_sql_tenant_acme(mock_schema, mock_url):
    """Acme should see 1 user (Alice)."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "SELECT id, name FROM users",
        "tenant_id": "acme"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 1
    assert data["results"][0]["name"] == "Alice"


@patch("backend.services.sql_executor.app.connection_manager.get_tenant_db_url", side_effect=mock_get_tenant_db_url)
@patch("backend.services.sql_executor.app.executor.get_allowed_schema", side_effect=mock_get_allowed_schema)
def test_execute_sql_tenant_stark(mock_schema, mock_url):
    """Stark should see 2 users (Tony, Pepper)."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "SELECT id, name FROM users",
        "tenant_id": "stark"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 2


def test_execute_sql_rejects_select_star():
    """SELECT * is forbidden by AST policy."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "SELECT * FROM users",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    detail = response.json().get("detail", "") or response.json().get("message", "")
    assert "SELECT *" in detail


# ── 2. Safety / Validation Tests ─────────────────────────────────

def test_execute_sql_drop_table():
    """DROP TABLE should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "DROP TABLE users;",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    detail = (response.json().get("detail", "") or response.json().get("message", "")).lower()
    assert any(w in detail for w in ("interdit", "forbidden", "not allowed", "seules", "modification"))


def test_execute_sql_insert():
    """INSERT should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "INSERT INTO users (name) VALUES ('Hacker');",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    detail = (response.json().get("detail", "") or response.json().get("message", "")).lower()
    assert any(w in detail for w in ("interdit", "forbidden", "not allowed", "seules", "modification"))


def test_execute_sql_update():
    """UPDATE should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "UPDATE users SET name = 'Hacked';",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    detail = (response.json().get("detail", "") or response.json().get("message", "")).lower()
    assert any(w in detail for w in ("interdit", "forbidden", "not allowed", "seules", "modification"))


def test_execute_sql_injection():
    """SQL injection with stacked queries should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "SELECT id, name FROM users; DELETE FROM users;",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    detail = (response.json().get("detail", "") or response.json().get("message", "")).lower()
    assert any(w in detail for w in ("interdit", "seule", "multiple", "forbidden", "not allowed"))


def test_execute_sql_empty():
    """Empty SQL should be rejected."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "   ",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
