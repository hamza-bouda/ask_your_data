import pytest
from app.executor import validate_and_prepare_sql, SqlExecutionError
import app.executor as executor_module

def test_select_allowed(monkeypatch):
    monkeypatch.setattr(executor_module, "get_allowed_schema", lambda t: {"users": {"id", "name"}})
    sql = "SELECT id, name FROM users"
    safe_sql = validate_and_prepare_sql(sql, "tenant_1")
    assert "LIMIT" in safe_sql.upper()

def test_insert_rejected(monkeypatch):
    monkeypatch.setattr(executor_module, "get_allowed_schema", lambda t: {"users": {"id", "name"}})
    sql = "INSERT INTO users (name) VALUES ('Test')"
    with pytest.raises(SqlExecutionError, match="Forbidden"):
        validate_and_prepare_sql(sql, "tenant_1")

def test_multiple_statements_rejected(monkeypatch):
    monkeypatch.setattr(executor_module, "get_allowed_schema", lambda t: {"users": {"id", "name"}})
    sql = "SELECT * FROM users; DROP TABLE users;"
    with pytest.raises(SqlExecutionError, match="Forbidden keyword"):
        validate_and_prepare_sql(sql, "tenant_1")
        
def test_table_not_allowed(monkeypatch):
    monkeypatch.setattr(executor_module, "get_allowed_schema", lambda t: {"users": {"id", "name"}})
    sql = "SELECT * FROM secrets"
    with pytest.raises(SqlExecutionError, match="denied by policy"):
        validate_and_prepare_sql(sql, "tenant_1")
