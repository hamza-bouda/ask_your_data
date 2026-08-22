"""Microsoft SQL Server Database Adapter for Ask Your Data (Experimental)."""

from typing import Any
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from .base import (
    BaseDatabaseAdapter,
    CatalogIntrospection,
    TableIntrospection,
    ColumnIntrospection,
    ForeignKeyIntrospection,
    IndexIntrospection,
)


class MSSQLAdapter(BaseDatabaseAdapter):
    dialect = "mssql"
    display_name = "Microsoft SQL Server"
    support_status = "experimental"

    def _normalize_connection_string(self, connection_string: str) -> str:
        if "mssql+pyodbc://" in connection_string or "mssql+pymssql://" in connection_string:
            return connection_string
        if connection_string.startswith("mssql://"):
            return "mssql+pymssql://" + connection_string[len("mssql://") :]
        return connection_string

    def create_engine(self, connection_string: str, **kwargs) -> Engine:
        normalized_url = self._normalize_connection_string(connection_string)
        return create_engine(
            normalized_url,
            poolclass=QueuePool,
            pool_size=kwargs.get("pool_size", 5),
            max_overflow=kwargs.get("max_overflow", 10),
            pool_timeout=kwargs.get("pool_timeout", 30),
            pool_recycle=kwargs.get("pool_recycle", 1800),
            pool_pre_ping=True,
            echo=False,
        )

    def test_connection(self, connection_string: str) -> bool:
        try:
            engine = self.create_engine(connection_string, pool_size=1, max_overflow=0)
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                return True
            finally:
                engine.dispose()
        except Exception:
            return False

    def introspect_schema(self, connection_string: str) -> CatalogIntrospection:
        engine = self.create_engine(connection_string, pool_size=2, max_overflow=2)
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
                            data_type=str(c.get("type", "NVARCHAR")),
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
                    conn.execute(text(f"SET LOCK_TIMEOUT {int(timeout_seconds * 1000)}"))
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
            "-- 1. Create a login and user for Microsoft SQL Server\n"
            "CREATE LOGIN askyourdata_readonly WITH PASSWORD = 'ChangeMeSecurely123!';\n"
            "USE analytics_db;\n"
            "CREATE USER askyourdata_readonly FOR LOGIN askyourdata_readonly;\n"
            "-- 2. Grant data reader role only\n"
            "ALTER ROLE db_datareader ADD MEMBER askyourdata_readonly;\n"
            "-- 3. Explicitly deny write/DDL permissions\n"
            "DENY ALTER TO askyourdata_readonly;\n"
            "DENY CONTROL TO askyourdata_readonly;\n"
        )
