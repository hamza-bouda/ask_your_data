"""Deep security test suite for AST SQL validation across dialects."""

import pytest
from backend.services.sql_executor.app.executor import (
    validate_ast,
    SecurityCheckResult,
)


class TestSQLSecurityDeep:
    """Validate all SQL security guardrails against malicious or dangerous SQL."""

    def test_allow_valid_select_queries(self):
        """Standard valid SELECT queries with projection pass validation."""
        sql = "SELECT id, name, salary FROM employees WHERE salary > 50000 ORDER BY salary DESC"
        result = validate_ast(sql, dialect="postgres")
        assert result.is_valid is True
        assert "LIMIT 1000" in result.sanitized_sql

    def test_reject_select_star(self):
        """Reject SELECT * to prevent data leakage and excessive memory consumption."""
        sql = "SELECT * FROM employees"
        result = validate_ast(sql, dialect="postgres")
        assert result.is_valid is False
        assert "SELECT *" in result.error_message

    def test_reject_ddl_and_dml(self):
        """Reject DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE statements."""
        forbidden_queries = [
            "DROP TABLE employees",
            "DELETE FROM employees WHERE id = 1",
            "INSERT INTO employees (name) VALUES ('Hacker')",
            "UPDATE employees SET salary = 999999 WHERE id = 1",
            "ALTER TABLE employees ADD COLUMN ssn TEXT",
            "TRUNCATE TABLE employees",
        ]
        for query in forbidden_queries:
            result = validate_ast(query, dialect="postgres")
            assert result.is_valid is False, f"Expected query to be rejected: {query}"
            assert len(result.error_message) > 0

    def test_reject_multiple_statements(self):
        """Reject SQL injection with statement chaining / semicolon separation."""
        sql = "SELECT id, name FROM employees; DROP TABLE employees;"
        result = validate_ast(sql, dialect="postgres")
        assert result.is_valid is False
        assert len(result.error_message) > 0

    def test_reject_dangerous_system_functions(self):
        """Reject dangerous system functions like pg_read_file, load_file, xp_cmdshell, version."""
        dangerous_queries = [
            "SELECT pg_read_file('/etc/passwd'), id FROM employees",
            "SELECT load_file('/etc/passwd'), name FROM employees",
            "SELECT xp_cmdshell('whoami'), id FROM employees",
            "SELECT version(), id FROM employees",
        ]
        for query in dangerous_queries:
            result = validate_ast(query, dialect="postgres")
            assert result.is_valid is False, f"Expected query with system function to be blocked: {query}"

    def test_enforce_allowlist_with_aliases(self):
        """Validate allowlist enforcement resolving table aliases."""
        allowed_tables = ["employees", "departments"]
        sql_valid = "SELECT e.id, e.name, d.name AS dept_name FROM employees e JOIN departments d ON e.department_id = d.id"
        result_valid = validate_ast(sql_valid, allowed_tables=allowed_tables, dialect="postgres")
        assert result_valid.is_valid is True

        sql_forbidden = "SELECT u.id, u.password_hash FROM users u"
        result_forbidden = validate_ast(sql_forbidden, allowed_tables=allowed_tables, dialect="postgres")
        assert result_forbidden.is_valid is False
        assert "users" in result_forbidden.error_message

    def test_multi_dialect_support(self):
        """AST validation succeeds across Postgres, MySQL, SQLite, and TSQL dialects."""
        dialects = ["postgres", "mysql", "sqlite", "tsql"]
        query = "SELECT id, name FROM customers WHERE active = 1"
        for dialect in dialects:
            res = validate_ast(query, dialect=dialect)
            assert res.is_valid is True, f"Failed on dialect {dialect}"

    def test_limit_injection_preserves_existing_smaller_limit(self):
        """If user query already specifies LIMIT 50, it is preserved without forcing 1000."""
        sql = "SELECT id, name FROM employees LIMIT 50"
        result = validate_ast(sql, dialect="postgres")
        assert result.is_valid is True
        assert "LIMIT 50" in result.sanitized_sql or "limit 50" in result.sanitized_sql.lower()
