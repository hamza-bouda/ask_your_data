"""SQLite Database Adapter for Ask Your Data (Development & Tests)."""

from typing import Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool, NullPool

from .base import (
    BaseDatabaseAdapter,
    CatalogIntrospection,
    TableIntrospection,
    ColumnIntrospection,
    ForeignKeyIntrospection,
    IndexIntrospection,
)


class SQLiteAdapter(BaseDatabaseAdapter):
    dialect = "sqlite"
    display_name = "SQLite"
    support_status = "supported-dev-test"

    def create_engine(self, connection_string: str, **kwargs) -> Engine:
        is_memory = ":memory:" in connection_string
        return create_engine(
            connection_string,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if is_memory else NullPool,
            echo=False,
        )

    def test_connection(self, connection_string: str) -> bool:
        engine = self.create_engine(connection_string)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        finally:
            engine.dispose()

    def introspect_schema(self, connection_string: str) -> CatalogIntrospection:
        engine = self.create_engine(connection_string)
        try:
            inspector = inspect(engine)
            tables: list[TableIntrospection] = []

            table_names = inspector.get_table_names()
            for t_name in table_names:
                try:
                    cols = inspector.get_columns(t_name)
                    pk = inspector.get_pk_constraint(t_name)
                    fks = inspector.get_foreign_keys(t_name)
                    indexes = inspector.get_indexes(t_name)

                    pk_cols = pk.get("constrained_columns", []) if pk else []

                    columns_intro = [
                        ColumnIntrospection(
                            name=c["name"],
                            data_type=str(c.get("type", "TEXT")),
                            is_nullable=bool(c.get("nullable", True)),
                            primary_key=(c["name"] in pk_cols),
                            default=str(c.get("default")) if c.get("default") is not None else None,
                            comment=c.get("comment"),
                        )
                        for c in cols
                    ]

                    fks_intro = [
                        ForeignKeyIntrospection(
                            constrained_columns=fk.get("constrained_columns", []),
                            referred_table=fk.get("referred_table", ""),
                            referred_columns=fk.get("referred_columns", []),
                        )
                        for fk in fks
                    ]

                    indexes_intro = [
                        IndexIntrospection(
                            name=idx.get("name") or f"idx_{t_name}_{'_'.join(idx.get('column_names', []))}",
                            column_names=idx.get("column_names", []),
                            unique=bool(idx.get("unique", False)),
                        )
                        for idx in indexes
                    ]

                    tables.append(
                        TableIntrospection(
                            name=t_name,
                            columns=columns_intro,
                            primary_key=pk_cols,
                            foreign_keys=fks_intro,
                            indices=indexes_intro,
                        )
                    )
                except Exception:
                    continue

            return CatalogIntrospection(dialect=self.dialect, tables=tables)
        finally:
            engine.dispose()

    def execute_read_only(
        self,
        connection_string: str,
        sql_query: str,
        timeout_seconds: int = 15,
        max_rows: int = 1000,
    ) -> list[dict[str, Any]]:
        engine = self.create_engine(connection_string)
        try:
            with engine.connect() as conn:
                try:
                    conn.execute(text("PRAGMA query_only = ON"))
                except Exception:
                    pass

                result = conn.execute(text(sql_query))
                columns = list(result.keys())
                rows = result.fetchmany(max_rows)
                return [dict(zip(columns, row)) for row in rows]
        finally:
            engine.dispose()

    def get_readonly_setup_instructions(self) -> str:
        return (
            "# SQLite stores data in a single file on disk.\n"
            "# For development and testing, restrict write access at the filesystem level:\n"
            "chmod 444 /path/to/database.db\n"
            "# Or connect using read-only URI mode:\n"
            "sqlite:///file:/path/to/database.db?mode=ro&uri=true\n"
        )
