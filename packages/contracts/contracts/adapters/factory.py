"""Factory for retrieving database adapters based on dialect or connection string."""

from typing import Optional
from .base import BaseDatabaseAdapter
from .postgres import PostgresAdapter
from .mysql import MySQLAdapter
from .sqlite import SQLiteAdapter
from .mssql import MSSQLAdapter

_ADAPTERS: dict[str, BaseDatabaseAdapter] = {
    "postgresql": PostgresAdapter(),
    "postgres": PostgresAdapter(),
    "mysql": MySQLAdapter(),
    "sqlite": SQLiteAdapter(),
    "mssql": MSSQLAdapter(),
    "sqlserver": MSSQLAdapter(),
}


class DatabaseAdapterFactory:
    """Provides the appropriate database adapter for a given dialect or connection string."""

    @classmethod
    def get_adapter(cls, dialect_or_url: str) -> BaseDatabaseAdapter:
        dialect = cls.detect_dialect(dialect_or_url)
        adapter = _ADAPTERS.get(dialect)
        if not adapter:
            raise ValueError(
                f"Unsupported database dialect: '{dialect}'. "
                f"Supported dialects: {cls.supported_dialects()}"
            )
        return adapter

    @classmethod
    def detect_dialect(cls, dialect_or_url: str) -> str:
        s = dialect_or_url.strip().lower()
        if "://" in s:
            scheme = s.split("://", 1)[0]
            for prefix in ("postgresql", "postgres", "mysql", "sqlite", "mssql"):
                if scheme.startswith(prefix):
                    return prefix
            return scheme
        if s in _ADAPTERS:
            return s
        raise ValueError(f"Unable to determine database dialect from: '{dialect_or_url}'")

    @classmethod
    def supported_dialects(cls) -> list[str]:
        return sorted(list(set(_ADAPTERS.keys())))

    @classmethod
    def get_supported_statuses(cls) -> dict[str, str]:
        return {
            name: adapter.support_status
            for name, adapter in _ADAPTERS.items()
        }
