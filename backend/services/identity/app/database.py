"""Database connection and session management.

Uses SQLAlchemy with a synchronous engine. For tests, we use SQLite
in-memory. In Docker, we connect to PostgreSQL.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

try:
    from .config import DATABASE_URL
except (ImportError, ValueError):
    try:
        from backend.services.identity.app.config import DATABASE_URL
    except ImportError:
        from app.config import DATABASE_URL


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models in this service."""
    pass


# ── Engine & Session Factory ─────────────────────────────────────
# connect_args is needed for SQLite to allow multi-threaded access
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,  # Set to True to see SQL queries in logs
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Session:
    """FastAPI dependency: yields a DB session, auto-closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Create all tables. Called at service startup."""
    try:
        from app import models
    except ImportError:
        try:
            from backend.services.identity.app import models
        except ImportError:
            pass
    Base.metadata.create_all(bind=engine)

import os
if os.getenv("TESTING") == "1":
    try:
        create_tables()
    except Exception:
        pass
