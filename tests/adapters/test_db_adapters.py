"""Unit tests for Database Adapters (Postgres, MySQL, SQLite, MSSQL, Factory)."""

import sqlite3
import pytest
from contracts.adapters import (
    BaseDatabaseAdapter,
    DatabaseAdapterFactory,
    SQLiteAdapter,
    PostgresAdapter,
    MySQLAdapter,
    MSSQLAdapter,
)


@pytest.fixture
def sample_sqlite_db(tmp_path):
    """Creates a temporary SQLite database with tables, foreign keys, and indexes."""
    db_path = tmp_path / "test_adapters.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            salary REAL NOT NULL,
            department_id INTEGER,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        );
    """)
    cursor.execute("CREATE INDEX idx_emp_dept ON employees(department_id);")
    cursor.execute("INSERT INTO departments (name, location) VALUES ('Engineering', 'Paris');")
    cursor.execute("INSERT INTO employees (name, salary, department_id) VALUES ('Alice', 75000.0, 1);")
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


class TestDatabaseAdapters:
    """Test suite for DBMS adapters."""

    def test_factory_resolves_dialects(self):
        """DatabaseAdapterFactory resolves corresponding adapter by connection URL."""
        assert isinstance(DatabaseAdapterFactory.get_adapter("sqlite:///test.db"), SQLiteAdapter)
        assert isinstance(DatabaseAdapterFactory.get_adapter("postgresql://user:pass@localhost:5432/db"), PostgresAdapter)
        assert isinstance(DatabaseAdapterFactory.get_adapter("postgresql+psycopg2://user:pass@localhost:5432/db"), PostgresAdapter)
        assert isinstance(DatabaseAdapterFactory.get_adapter("mysql://user:pass@localhost:3306/db"), MySQLAdapter)
        assert isinstance(DatabaseAdapterFactory.get_adapter("mysql+pymysql://user:pass@localhost:3306/db"), MySQLAdapter)
        assert isinstance(DatabaseAdapterFactory.get_adapter("mssql+pyodbc://user:pass@localhost/db"), MSSQLAdapter)

    def test_sqlite_adapter_connection_and_introspection(self, sample_sqlite_db):
        """SQLiteAdapter connects, tests connection and performs comprehensive schema introspection."""
        adapter = SQLiteAdapter()
        assert adapter.dialect == "sqlite"
        assert adapter.test_connection(sample_sqlite_db) is True

        catalog = adapter.introspect_schema(sample_sqlite_db)
        assert catalog.dialect == "sqlite"
        table_names = [t.name for t in catalog.tables]
        assert "departments" in table_names
        assert "employees" in table_names

        emp_table = next(t for t in catalog.tables if t.name == "employees")
        col_names = [c.name for c in emp_table.columns]
        assert "id" in col_names
        assert "name" in col_names
        assert "salary" in col_names
        assert "department_id" in col_names

        # Verify Primary Key
        assert "id" in emp_table.primary_key

        # Verify Foreign Keys
        assert len(emp_table.foreign_keys) >= 1
        fk = emp_table.foreign_keys[0]
        assert fk.referred_table == "departments"

    def test_sqlite_read_only_execution(self, sample_sqlite_db):
        """SQLiteAdapter executes read queries in read-only mode."""
        adapter = SQLiteAdapter()
        rows = adapter.execute_read_only(
            sample_sqlite_db,
            "SELECT name, salary FROM employees WHERE department_id = 1",
        )
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"
        assert rows[0]["salary"] == 75000.0

    def test_adapter_invalid_connection(self):
        """Adapters return False on invalid connection test without crashing."""
        pg_adapter = PostgresAdapter()
        assert pg_adapter.test_connection("postgresql://invalid_user:invalid_pass@127.0.0.1:59999/invalid_db") is False

        mysql_adapter = MySQLAdapter()
        assert mysql_adapter.test_connection("mysql://invalid_user:invalid_pass@127.0.0.1:59999/invalid_db") is False

    def test_mssql_adapter_metadata(self):
        """MSSQL adapter is marked experimental with appropriate dialect properties."""
        adapter = MSSQLAdapter()
        assert adapter.dialect == "mssql"
        assert adapter.support_status == "experimental"
