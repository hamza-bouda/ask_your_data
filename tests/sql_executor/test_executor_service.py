"""Tests for the SQL Executor Service — Phase 06 Definition of Done."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from backend.services.sql_executor.app.main import app

client = TestClient(app)

# Setup dummy databases for tests
def setup_module(module):
    # Setup Tenant 1 (Acme) DB
    engine1 = create_engine("sqlite:///tenant_acme.db")
    with engine1.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("INSERT INTO users (name) VALUES ('Alice')"))
        conn.commit()
        
    # Setup Tenant 2 (Stark) DB
    engine2 = create_engine("sqlite:///tenant_stark.db")
    with engine2.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("INSERT INTO users (name) VALUES ('Tony'), ('Pepper')"))
        conn.commit()

# ── 1. Execution & Isolation Tests ───────────────────────────────

def test_execute_sql_tenant_acme():
    """Acme should see 1 user (Alice)."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "SELECT * FROM users",
        "tenant_id": "acme"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 1
    assert data["results"][0]["name"] == "Alice"

def test_execute_sql_tenant_stark():
    """Stark should see 2 users (Tony, Pepper)."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "SELECT * FROM users",
        "tenant_id": "stark"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["row_count"] == 2


# ── 2. Safety / Validation Tests ─────────────────────────────────

def test_execute_sql_drop_table():
    """DROP TABLE should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "DROP TABLE users;",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    assert "Forbidden keyword" in response.json().get("message", "")

def test_execute_sql_insert():
    """INSERT should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "INSERT INTO users (name) VALUES ('Hacker');",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    assert "Forbidden keyword" in response.json().get("message", "")

def test_execute_sql_update():
    """UPDATE should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "UPDATE users SET name = 'Hacked';",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    assert "Forbidden keyword" in response.json().get("message", "")

def test_execute_sql_injection():
    """SQL injection with stacked queries should be blocked."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "SELECT * FROM users; DELETE FROM users;",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    assert "Forbidden keyword" in response.json().get("message", "")

def test_execute_sql_empty():
    """Empty SQL should be rejected."""
    response = client.post("/internal/execute-sql", json={
        "sql_query": "   ",
        "tenant_id": "acme"
    })
    assert response.status_code == 400
    assert "SQL query cannot be empty" in response.json().get("message", "")
