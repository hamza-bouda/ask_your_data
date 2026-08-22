"""Base Database Adapter interface and data models for Ask Your Data."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine


class ColumnIntrospection(BaseModel):
    name: str
    data_type: str
    is_nullable: bool = True
    primary_key: bool = False
    default: Optional[str] = None
    comment: Optional[str] = None


class ForeignKeyIntrospection(BaseModel):
    constrained_columns: list[str]
    referred_table: str
    referred_columns: list[str]


class IndexIntrospection(BaseModel):
    name: str
    column_names: list[str]
    unique: bool = False


class TableIntrospection(BaseModel):
    name: str
    comment: Optional[str] = None
    columns: list[ColumnIntrospection] = Field(default_factory=list)
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyIntrospection] = Field(default_factory=list)
    indices: list[IndexIntrospection] = Field(default_factory=list)


class CatalogIntrospection(BaseModel):
    dialect: str
    tables: list[TableIntrospection] = Field(default_factory=list)


class BaseDatabaseAdapter(ABC):
    """Abstract interface that every database dialect adapter must implement."""

    dialect: str = "generic"
    display_name: str = "Generic Database"
    support_status: str = "experimental"  # production-ready | supported-dev-test | experimental

    @abstractmethod
    def test_connection(self, connection_string: str) -> bool:
        """Test whether a connection can be established with the provided connection string."""
        pass

    @abstractmethod
    def introspect_schema(self, connection_string: str) -> CatalogIntrospection:
        """Introspect tables, columns, constraints, foreign keys and indexes."""
        pass

    @abstractmethod
    def execute_read_only(
        self,
        connection_string: str,
        sql_query: str,
        timeout_seconds: int = 15,
        max_rows: int = 1000,
    ) -> list[dict[str, Any]]:
        """Execute a validated SQL query in strict read-only mode with timeout and max_rows limit."""
        pass

    @abstractmethod
    def create_engine(self, connection_string: str, **kwargs) -> Engine:
        """Create and configure a SQLAlchemy engine with connection pooling."""
        pass

    def dispose_engine(self, engine: Engine) -> None:
        """Cleanly dispose of connection pools when datasource is removed or modified."""
        if engine:
            engine.dispose()

    @abstractmethod
    def get_readonly_setup_instructions(self) -> str:
        """Return SQL instructions for configuring a least-privilege read-only database user."""
        pass
