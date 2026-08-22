"""Integration test suite for Multi-Tenant Isolation."""

import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.services.catalog.app.main import app as catalog_app


@pytest.fixture
def acme_sqlite_db(tmp_path):
    """Creates a private database for tenant ACME."""
    db_path = tmp_path / "acme_private.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE acme_secrets (id INT, project TEXT);")
    cursor.execute("INSERT INTO acme_secrets VALUES (1, 'Acme Project X');")
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


@pytest.fixture
def stark_sqlite_db(tmp_path):
    """Creates a private database for tenant STARK."""
    db_path = tmp_path / "stark_private.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE stark_armor (id INT, model TEXT);")
    cursor.execute("INSERT INTO stark_armor VALUES (1, 'Mark 85');")
    conn.commit()
    conn.close()
    return f"sqlite:///{db_path}"


class TestMultiTenantIsolation:
    """Verify strict tenant data isolation in Catalog and Execution."""

    def test_tenant_isolation_in_catalog(self, acme_sqlite_db, stark_sqlite_db):
        """Tenant Stark cannot view or access Tenant Acme's sources or catalog."""
        client = TestClient(catalog_app)

        # 1. Register Acme database
        acme_headers = {"x-tenant-id": "acme_corp", "x-user-id": "acme_admin"}
        resp_acme_reg = client.post(
            "/api/v1/catalog/register",
            json={"connection_string": acme_sqlite_db, "name": "Acme DB"},
            headers=acme_headers,
        )
        assert resp_acme_reg.status_code == 200
        acme_source_id = resp_acme_reg.json()["id"]

        # 2. Register Stark database
        stark_headers = {"x-tenant-id": "stark_ind", "x-user-id": "stark_admin"}
        resp_stark_reg = client.post(
            "/api/v1/catalog/register",
            json={"connection_string": stark_sqlite_db, "name": "Stark DB"},
            headers=stark_headers,
        )
        assert resp_stark_reg.status_code == 200
        stark_source_id = resp_stark_reg.json()["id"]

        # 3. List sources as Acme -> only Acme source returned
        resp_acme_sources = client.get("/api/v1/catalog/sources", headers=acme_headers)
        assert resp_acme_sources.status_code == 200
        acme_ids = [s["id"] for s in resp_acme_sources.json()["sources"]]
        assert acme_source_id in acme_ids
        assert stark_source_id not in acme_ids

        # 4. List sources as Stark -> only Stark source returned
        resp_stark_sources = client.get("/api/v1/catalog/sources", headers=stark_headers)
        assert resp_stark_sources.status_code == 200
        stark_ids = [s["id"] for s in resp_stark_sources.json()["sources"]]
        assert stark_source_id in stark_ids
        assert acme_source_id not in stark_ids

        # 5. Stark trying to sync or inspect Acme's source gets 404
        stark_tampering_headers = {
            "x-tenant-id": "stark_ind",
            "x-user-id": "stark_admin",
            "x-source-id": acme_source_id,
        }
        resp_tampering = client.post("/api/v1/catalog/sync", headers=stark_tampering_headers)
        assert resp_tampering.status_code in (404, 500)
