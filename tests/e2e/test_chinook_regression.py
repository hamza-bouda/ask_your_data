"""E2E Regression Test Suite using a Chinook Database schema."""

import sqlite3
import pytest
from contracts.adapters import SQLiteAdapter
from backend.services.sql_executor.app.executor import validate_ast
from backend.services.sql_generator.app.generator import SQLGenerator
from backend.services.orchestrator.app.answer_generator import generate_business_answer
from contracts.llm import MockLLMProvider


@pytest.fixture
def chinook_db(tmp_path):
    """Creates a sample Chinook-like SQLite database."""
    db_path = tmp_path / "chinook_test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE artists (
            ArtistId INTEGER PRIMARY KEY,
            Name NVARCHAR(120)
        );
    """)
    cursor.execute("""
        CREATE TABLE albums (
            AlbumId INTEGER PRIMARY KEY,
            Title NVARCHAR(160) NOT NULL,
            ArtistId INTEGER NOT NULL,
            FOREIGN KEY (ArtistId) REFERENCES artists (ArtistId)
        );
    """)
    cursor.execute("""
        CREATE TABLE customers (
            CustomerId INTEGER PRIMARY KEY,
            FirstName NVARCHAR(40) NOT NULL,
            LastName NVARCHAR(20) NOT NULL,
            Country NVARCHAR(40)
        );
    """)
    cursor.execute("""
        CREATE TABLE invoices (
            InvoiceId INTEGER PRIMARY KEY,
            CustomerId INTEGER NOT NULL,
            Total NUMERIC(10,2) NOT NULL,
            FOREIGN KEY (CustomerId) REFERENCES customers (CustomerId)
        );
    """)

    cursor.execute("INSERT INTO artists VALUES (1, 'AC/DC'), (2, 'Queen'), (3, 'Miles Davis');")
    cursor.execute("INSERT INTO albums VALUES (1, 'Back in Black', 1), (2, 'A Night at the Opera', 2);")
    cursor.execute("INSERT INTO customers VALUES (1, 'Jean', 'Dupont', 'France'), (2, 'John', 'Doe', 'USA');")
    cursor.execute("INSERT INTO invoices VALUES (1, 1, 15.99), (2, 1, 24.50), (3, 2, 45.00);")

    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


class TestChinookRegression:
    """Validate end-to-end Text-to-SQL pipeline on Chinook schema."""

    def test_chinook_schema_introspection(self, chinook_db):
        """Introspect Chinook schema and verify table relations."""
        adapter = SQLiteAdapter()
        catalog = adapter.introspect_schema(chinook_db)
        tables = {t.name: t for t in catalog.tables}

        assert "artists" in tables
        assert "albums" in tables
        assert "customers" in tables
        assert "invoices" in tables

        # Verify foreign keys
        album_fks = tables["albums"].foreign_keys
        assert any(fk.referred_table == "artists" for fk in album_fks)

    def test_chinook_sql_generation_and_execution(self, chinook_db):
        """Test SQL query generation, AST safety check, and execution on Chinook."""
        # Simulated SQL from SQL generator
        generated_sql = (
            "SELECT c.Country, SUM(i.Total) AS TotalRevenue "
            "FROM customers c "
            "JOIN invoices i ON c.CustomerId = i.CustomerId "
            "GROUP BY c.Country "
            "ORDER BY TotalRevenue DESC"
        )

        # 1. AST Validation
        security_check = validate_ast(
            generated_sql,
            allowed_tables=["customers", "invoices"],
            dialect="sqlite",
        )
        assert security_check.is_valid is True

        # 2. Execution via Adapter
        adapter = SQLiteAdapter()
        rows = adapter.execute_read_only(chinook_db, security_check.sanitized_sql)

        assert len(rows) == 2
        # USA has 45.0, France has 40.49
        assert rows[0]["Country"] == "USA"
        assert float(rows[0]["TotalRevenue"]) == 45.0
        assert rows[1]["Country"] == "France"

        # 3. Answer Generator Synthesis
        biz_answer = generate_business_answer(
            question="Quel est le chiffre d'affaires par pays ?",
            results=rows,
            sql_query=security_check.sanitized_sql,
        )
        assert biz_answer.executive_summary is not None
        assert len(biz_answer.key_insights) >= 1
