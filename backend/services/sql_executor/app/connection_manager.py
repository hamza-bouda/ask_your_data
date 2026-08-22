"""Dynamic Connection Manager for SQL Executor.

Manages per-tenant and per-datasource database engines, pooling, and lifecycle.
"""

import threading
import os
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from cryptography.fernet import Fernet

try:
    from app.adapters.factory import DatabaseAdapterFactory
except ImportError:
    from backend.services.sql_executor.app.adapters.factory import DatabaseAdapterFactory

# Cache for database engines: cache_key -> Engine
_engine_cache: dict[str, Engine] = {}
_lock = threading.Lock()

if os.getenv("TESTING") == "1":
    GLOBAL_DB_URL = os.getenv("CATALOG_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./catalog_test.db"))
else:
    GLOBAL_DB_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://askyourdata:askyourdata_dev@postgres:5432/askyourdata",
    )

_global_engine: Optional[Engine] = None


def get_global_engine() -> Engine:
    """Lazily initialize and return the global metadata catalog engine."""
    global _global_engine
    if _global_engine is None:
        with _lock:
            if _global_engine is None:
                is_sqlite = GLOBAL_DB_URL.startswith("sqlite")
                _global_engine = create_engine(
                    GLOBAL_DB_URL,
                    connect_args={"check_same_thread": False} if is_sqlite else {},
                    echo=False,
                )
    return _global_engine


def _get_cipher_suite() -> Fernet:
    fernet_key = os.getenv("FERNET_KEY")
    if not fernet_key:
        app_env = os.getenv("APP_ENV", "development").lower()
        if app_env in {"production", "prod"}:
            raise ValueError("FERNET_KEY environment variable is required in production")
        fernet_key = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    try:
        return Fernet(fernet_key.encode())
    except Exception:
        return Fernet(Fernet.generate_key())


def get_tenant_db_url(tenant_id: str, source_id: str | None = None) -> str:
    """Resolve a tenant-owned datasource URL from the global catalog."""
    source_id = source_id or tenant_id
    engine = get_global_engine()
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT connection_string FROM data_sources WHERE id = :source_id AND tenant_id = :tenant_id AND status = 'active'"
            ),
            {"tenant_id": tenant_id, "source_id": source_id},
        )
        row = result.fetchone()
        if row:
            encrypted_str = row[0]
            try:
                cipher = _get_cipher_suite()
                decrypted = cipher.decrypt(encrypted_str.encode()).decode()
                return decrypted
            except Exception:
                # If already unencrypted (e.g. in test fixture), fallback gracefully
                if "://" in encrypted_str:
                    return encrypted_str
                raise ValueError(f"Failed to decrypt connection string for tenant {tenant_id}")
        else:
            raise ValueError(f"No active database configured for tenant {tenant_id} and source {source_id}")


def get_engine_for_tenant(tenant_id: str, source_id: str | None = None) -> Engine:
    """Retrieve or create a SQLAlchemy engine for the given tenant using its dialect adapter."""
    cache_key = f"{tenant_id}:{source_id or tenant_id}"
    with _lock:
        if cache_key not in _engine_cache:
            db_url = get_tenant_db_url(tenant_id, source_id)
            adapter = DatabaseAdapterFactory.get_adapter(db_url)
            engine = adapter.create_engine(db_url)
            _engine_cache[cache_key] = engine
        return _engine_cache[cache_key]


def invalidate_datasource_cache(tenant_id: str, source_id: str | None = None) -> None:
    """Cleanly close and remove cached engines when a datasource is updated or deleted."""
    cache_key = f"{tenant_id}:{source_id or tenant_id}"
    with _lock:
        engine = _engine_cache.pop(cache_key, None)
        if engine:
            try:
                engine.dispose()
            except Exception:
                pass


def get_tenant_session(tenant_id: str, source_id: str | None = None) -> Session:
    """Create a new database session for the given tenant."""
    engine = get_engine_for_tenant(tenant_id, source_id)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()
