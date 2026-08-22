"""Integration test suite for Database Registration, Schema Sync and Policy Lifecycle."""

import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.services.catalog.app.main import app as catalog_app


@pytest.fixture
def lifecycle_sqlite_db(tmp_path):
    """Creates a temporary database for lifecycle testing."""
    db_path = tmp_path / "lifecycle_test.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            stock INT DEFAULT 0
        );
    """)
    cursor.execute("INSERT INTO products (title, price, stock) VALUES ('Laptop Pro', 1299.99, 50);")
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


class TestDatabaseLifecycle:
    """Validate full database lifecycle from registration to schema introspection and policy management."""

    def test_datasource_complete_lifecycle(self, lifecycle_sqlite_db):
        """Walk through full datasource lifecycle from registration to policy management."""
        client = TestClient(catalog_app)
        headers = {"x-tenant-id": "lifecycle_corp", "x-user-id": "admin_1", "x-is-admin": "true"}

        # 1. Register Database
        reg_resp = client.post(
            "/api/v1/catalog/register",
            json={"connection_string": lifecycle_sqlite_db, "name": "Inventory DB"},
            headers=headers,
        )
        assert reg_resp.status_code == 200
        source_id = reg_resp.json()["id"]

        # 2. Sync Database Schema
        sync_headers = {**headers, "x-source-id": source_id}
        sync_resp = client.post("/api/v1/catalog/sync", headers=sync_headers)
        assert sync_resp.status_code == 200
        sync_data = sync_resp.json()
        assert sync_data["tables_indexed"] >= 1
        assert sync_data["catalog_version"] >= 1

        # 3. Fetch Catalog Tables
        cat_resp = client.get("/api/v1/catalog/tables", headers=sync_headers)
        assert cat_resp.status_code == 200
        tables = cat_resp.json().get("tables", [])
        assert any(t["table_name"] == "products" for t in tables)

        # 4. Update Table Policy (Allow products table)
        prod_table = next(t for t in tables if t["table_name"] == "products")
        policy_resp = client.patch(
            f"/api/v1/catalog/tables/{prod_table['id']}",
            json={"is_allowed": True},
            headers=sync_headers,
        )
        assert policy_resp.status_code == 200
        assert policy_resp.json().get("status") == "success"

        # 5. Archive Datasource
        update_resp = client.patch(
            f"/api/v1/catalog/sources/{source_id}",
            json={"status": "archived"},
            headers=headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json().get("status") == "archived"
