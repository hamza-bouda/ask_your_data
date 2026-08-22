import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Connect to postgres in prod/docker or sqlite in tests
if os.getenv("TESTING") == "1":
    DATABASE_URL = os.getenv("CATALOG_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./catalog_test.db"))
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://askyourdata:askyourdata_dev@postgres:5432/askyourdata")

_is_sqlite = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    if engine.dialect.name == "postgresql":
        with engine.connect() as conn:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
            except Exception:
                pass
    try:
        from app import models
    except ImportError:
        try:
            from backend.services.catalog.app import models
        except ImportError:
            pass
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name != "postgresql":
        return

    additive_columns = {
        "tenant_databases": [
            "name VARCHAR(200)",
            "dialect VARCHAR(50)",
            "status VARCHAR(50) DEFAULT 'active'",
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "last_synced_at TIMESTAMP",
            "is_allowed BOOLEAN DEFAULT FALSE",
            "catalog_version INTEGER DEFAULT 1",
        ],
        "tables": [
            "is_allowed BOOLEAN DEFAULT FALSE",
            "is_available BOOLEAN DEFAULT TRUE",
            "last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "modified_by VARCHAR(100)",
            "primary_key VARCHAR",
            "foreign_keys JSON",
            "indices JSON",
            "catalog_version INTEGER DEFAULT 1",
            "source_id VARCHAR(36)",
        ],
        "columns": [
            "is_allowed BOOLEAN DEFAULT FALSE",
            "is_available BOOLEAN DEFAULT TRUE",
            "last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "modified_by VARCHAR(100)",
            "is_nullable BOOLEAN DEFAULT TRUE",
        ],
        "catalog_documents": [
            "source_id VARCHAR(36)",
        ],
        "semantic_metrics": [
            "source_id VARCHAR(36)",
        ],
        "semantic_synonyms": [
            "source_id VARCHAR(36)",
        ],
    }
    with engine.begin() as conn:
        for table_name, columns in additive_columns.items():
            for column in columns:
                column_name = column.split(" ", 1)[0]
                conn.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN IF NOT EXISTS {column_name} {column[len(column_name):].strip()}"
                    )
                )

        # Move the original one-source-per-tenant entries into the new
        # multi-source table. The legacy tenant id is deliberately reused as
        # the source id so every old catalog row can be backfilled atomically.
        conn.execute(text("""
            INSERT INTO data_sources
                (id, tenant_id, connection_string, name, dialect, status,
                 created_at, last_synced_at, is_allowed, catalog_version)
            SELECT tenant_id, tenant_id, connection_string,
                   COALESCE(name, 'Database for ' || tenant_id), dialect,
                   COALESCE(status, 'active'), COALESCE(created_at, CURRENT_TIMESTAMP),
                   last_synced_at, COALESCE(is_allowed, FALSE), COALESCE(catalog_version, 1)
            FROM tenant_databases
            ON CONFLICT (id) DO NOTHING
        """))
        for table_name in ("tables", "catalog_documents", "semantic_metrics", "semantic_synonyms"):
            conn.execute(text(
                f"UPDATE {table_name} SET source_id = tenant_id WHERE source_id IS NULL"
            ))

if os.getenv("TESTING") == "1":
    try:
        create_tables()
    except Exception:
        pass
