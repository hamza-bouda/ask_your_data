"""Dynamic Connection Manager for SQL Executor.

Manages per-tenant database connections.
"""

import threading
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from cryptography.fernet import Fernet

# Cache for database engines: tenant_id -> Engine
_engine_cache = {}
_lock = threading.Lock()

GLOBAL_DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://askyourdata:askyourdata_dev@postgres:5432/askyourdata")
_global_engine = create_engine(GLOBAL_DB_URL)

fernet_key = os.getenv("FERNET_KEY")
if not fernet_key:
    raise ValueError("FERNET_KEY environment variable is required for decrypting data sources")
cipher_suite = Fernet(fernet_key.encode())

def get_tenant_db_url(tenant_id: str) -> str:
    """Resolve URL for a tenant's database from the global catalog."""
    with _global_engine.connect() as conn:
        result = conn.execute(
            text("SELECT connection_string FROM tenant_databases WHERE tenant_id = :tenant_id AND status = 'active'"),
            {"tenant_id": tenant_id}
        )
        row = result.fetchone()
        if row:
            encrypted_str = row[0]
            try:
                decrypted = cipher_suite.decrypt(encrypted_str.encode()).decode()
                return decrypted
            except Exception as e:
                # If decryption fails, it might be unencrypted if coming from older version. 
                # For safety, we enforce encryption, so we just raise.
                raise ValueError(f"Failed to decrypt connection string for tenant {tenant_id}")
        else:
            raise ValueError(f"No active database configured for tenant {tenant_id}")

def get_engine_for_tenant(tenant_id: str):
    """Retrieve or create a SQLAlchemy engine for the given tenant."""
    with _lock:
        if tenant_id not in _engine_cache:
            db_url = get_tenant_db_url(tenant_id)
            is_sqlite = db_url.startswith("sqlite")
            
            engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False} if is_sqlite else {},
                echo=False,
            )
            _engine_cache[tenant_id] = engine
            
        return _engine_cache[tenant_id]

def get_tenant_session(tenant_id: str) -> Session:
    """Create a new database session for the given tenant."""
    engine = get_engine_for_tenant(tenant_id)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()
