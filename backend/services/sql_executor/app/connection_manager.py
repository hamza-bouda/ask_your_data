"""Dynamic Connection Manager for SQL Executor.

Manages per-tenant database connections.
"""

import threading
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Cache for database engines: tenant_id -> Engine
_engine_cache = {}
_lock = threading.Lock()

def get_tenant_db_url(tenant_id: str) -> str:
    """Mock URL resolution for a tenant's database."""
    return f"sqlite:///tenant_{tenant_id}.db"

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
