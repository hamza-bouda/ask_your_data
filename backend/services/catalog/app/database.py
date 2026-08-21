import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Connect to the local postgres container running pgvector
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://askyourdata:askyourdata_dev@postgres:5432/askyourdata")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    # Ensure pgvector extension exists
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)

    # `create_all` only creates missing tables; it never evolves existing ones.
    # Keep this additive compatibility migration until the project adopts a formal
    # Alembic workflow, so a local upgrade does not require dropping tenant metadata.
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
        ],
        "columns": [
            "is_allowed BOOLEAN DEFAULT FALSE",
            "is_available BOOLEAN DEFAULT TRUE",
            "last_modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "modified_by VARCHAR(100)",
            "is_nullable BOOLEAN DEFAULT TRUE",
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
