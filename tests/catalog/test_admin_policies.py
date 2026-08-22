import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

try:
    from app.main import app
    from app.database import Base, get_db
    from app.models import DataSource, TenantDatabase, TableSchema, ColumnSchema
except ImportError:
    from backend.services.catalog.app.main import app
    from backend.services.catalog.app.database import Base, get_db
    from backend.services.catalog.app.models import DataSource, TenantDatabase, TableSchema, ColumnSchema

# Setup test DB
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

from sqlalchemy import text

@pytest.fixture(autouse=True)
def setup_database():
    with engine.connect() as conn:
        for t in ["columns", "tables", "catalog_documents", "semantic_metrics", "semantic_synonyms", "data_sources", "tenant_databases", "execution_audits", "admin_audits"]:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
            except Exception:
                pass
        conn.commit()
    Base.metadata.create_all(bind=engine)

    # Pre-populate some test data
    db = TestingSessionLocal()

    db.add(TenantDatabase(tenant_id="tenant_A", connection_string="xxx", status="active", is_allowed=True))
    db.add(TenantDatabase(tenant_id="tenant_B", connection_string="yyy", status="active", is_allowed=True))
    db.add(DataSource(id="source_A", tenant_id="tenant_A", connection_string="xxx", name="Tenant A", status="active"))
    db.add(DataSource(id="source_B", tenant_id="tenant_B", connection_string="yyy", name="Tenant B", status="active"))
    db.flush()

    # Tenant A data
    t_a = TableSchema(tenant_id="tenant_A", source_id="source_A", table_name="users", is_allowed=True)
    t_a_denied = TableSchema(tenant_id="tenant_A", source_id="source_A", table_name="secrets", is_allowed=False)
    db.add(t_a)
    db.add(t_a_denied)
    db.flush()

    db.add(ColumnSchema(table_id=t_a.id, column_name="id", data_type="int", is_allowed=True))
    db.add(ColumnSchema(table_id=t_a.id, column_name="password", data_type="str", is_allowed=False))

    # Tenant B data
    t_b = TableSchema(tenant_id="tenant_B", source_id="source_B", table_name="orders", is_allowed=True)
    db.add(t_b)

    db.commit()
    db.close()

    yield
    Base.metadata.drop_all(bind=engine)


def test_tenant_isolation_admin():
    # Tenant A admin getting tables
    response = client.get("/api/v1/catalog/tables", headers={"x-tenant-id": "tenant_A", "x-is-admin": "true"})
    assert response.status_code == 200
    tables = response.json()["tables"]
    assert len(tables) == 2
    table_names = [t["table_name"] for t in tables]
    assert "users" in table_names
    assert "secrets" in table_names
    assert "orders" not in table_names

def test_tenant_isolation_analyst():
    # Tenant A analyst getting tables
    response = client.get("/api/v1/catalog/tables", headers={"x-tenant-id": "tenant_A", "x-is-admin": "false"})
    assert response.status_code == 200
    tables = response.json()["tables"]
    assert len(tables) == 1
    assert tables[0]["table_name"] == "users"

def test_policy_enforcement_analyst():
    response = client.get("/api/v1/catalog/tables", headers={"x-tenant-id": "tenant_A", "x-is-admin": "false"})
    tables = response.json()["tables"]
    users_table = tables[0]

    assert "is_allowed" not in users_table # Analysts should not see the flag
    assert len(users_table["columns"]) == 1
    assert users_table["columns"][0]["name"] == "id" # password column is hidden

def test_policy_enforcement_admin():
    response = client.get("/api/v1/catalog/tables", headers={"x-tenant-id": "tenant_A", "x-is-admin": "true"})
    tables = response.json()["tables"]
    users_table = next(t for t in tables if t["table_name"] == "users")

    assert "is_allowed" in users_table
    assert users_table["is_allowed"] == True
    assert len(users_table["columns"]) == 2
    assert "password" in [c["name"] for c in users_table["columns"]]

def test_policy_mutation_audit():
    # Admin denies "users" table
    response = client.get("/api/v1/catalog/tables", headers={"x-tenant-id": "tenant_A", "x-is-admin": "true"})
    table_id = next(t["id"] for t in response.json()["tables"] if t["table_name"] == "users")

    resp_patch = client.patch(
        f"/api/v1/catalog/tables/{table_id}",
        json={"is_allowed": False},
        headers={"x-tenant-id": "tenant_A", "x-user-id": "admin_1", "x-correlation-id": "corr-123"}
    )
    assert resp_patch.status_code == 200

    # Check audit log
    resp_audit = client.get("/api/v1/catalog/audit", headers={"x-tenant-id": "tenant_A"})
    assert resp_audit.status_code == 200
    audits = resp_audit.json()["audits"]
    assert len(audits) > 0
    assert audits[0]["action"] == "deny_table"
    assert audits[0]["target"] == "table:users"
    assert audits[0]["correlation_id"] == "corr-123"
