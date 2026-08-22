"""SQL Execution Engine with Multi-Dialect AST Safety Checks.

Parses SQL statically via SQLGlot AST to ensure no mutating commands or system functions are run,
checks tables/columns against an allowlist, injects LIMIT,
and executes in a read-only transaction context with a hashed audit trail.
"""

import re
import time
import hashlib
from typing import Any
import sqlglot
import sqlglot.expressions as exp
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

try:
    from app.connection_manager import get_global_engine, get_engine_for_tenant
    from app.adapters.factory import DatabaseAdapterFactory
except ImportError:
    from backend.services.sql_executor.app.connection_manager import get_global_engine, get_engine_for_tenant
    from backend.services.sql_executor.app.adapters.factory import DatabaseAdapterFactory


class SqlExecutionError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class SecurityCheckResult:
    """Result of static AST SQL security check."""
    def __init__(self, is_valid: bool, sanitized_sql: str = "", error_message: str = ""):
        self.is_valid = is_valid
        self.sanitized_sql = sanitized_sql
        self.error_message = error_message


# Forbidden system and dangerous functions across dialects
FORBIDDEN_FUNCTIONS = {
    # Postgres & Generic
    "pg_read_file", "pg_read_binary_file", "pg_write_file", "pg_ls_dir",
    "pg_sleep", "lo_import", "lo_export", "query_to_xml", "version",
    "current_setting", "current_user", "session_user",
    # MySQL
    "load_file", "sleep", "benchmark", "sys_eval", "sys_exec", "user",
    # MSSQL
    "xp_cmdshell", "sp_executesql", "openrowset", "opendatasource", "openquery",
    # SQLite
    "load_extension",
}

FORBIDDEN_KEYWORDS_REGEX = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
    r"\bALTER\b", r"\bGRANT\b", r"\bREVOKE\b", r"\bTRUNCATE\b",
    r"\bCREATE\b", r"\bREPLACE\b", r"\bEXECUTE\b", r"\bMERGE\b",
    r"\bCALL\b", r"\bEXEC\b", r"\bPRAGMA\b", r"\bATTACH\b", r"\bDETACH\b",
    r"\bINTO\s+OUTFILE\b", r"\bINTO\s+DUMPFILE\b",
]


def get_allowed_schema(tenant_id: str, source_id: str | None = None) -> dict[str, set[str]]:
    """Fetch the allowed tables and columns from the global catalog."""
    allowed: dict[str, set[str]] = {}
    try:
        engine = get_global_engine()
        with engine.connect() as conn:
            source_id = source_id or tenant_id
            db_res = conn.execute(
                text(
                    "SELECT is_allowed FROM data_sources WHERE id = :source_id AND tenant_id = :tenant_id AND status = 'active'"
                ),
                {"tenant_id": tenant_id, "source_id": source_id},
            ).fetchone()

            if not db_res or not db_res[0]:
                return {}  # Deny-All if not allowed or not active

            res = conn.execute(
                text("""
                SELECT t.table_name, c.column_name
                FROM tables t
                JOIN columns c ON t.id = c.table_id
                WHERE t.source_id = :source_id
                  AND t.is_allowed IS TRUE
                  AND c.is_allowed IS TRUE
                """),
                {"source_id": source_id},
            )
            for row in res:
                t_name = row[0].lower()
                c_name = row[1].lower()
                if t_name not in allowed:
                    allowed[t_name] = set()
                allowed[t_name].add(c_name)
    except Exception:
        # Fallback or empty if DB uninitialized
        return {}
    return allowed


def log_audit(
    tenant_id: str,
    sql_query: str,
    decision: str,
    duration_ms: int,
    row_count: int,
    status: str,
    error_msg: str,
    source_id: str | None = None,
) -> None:
    """Write a hashed execution audit to the global database."""
    sql_hash = hashlib.sha256(sql_query.encode()).hexdigest()
    try:
        engine = get_global_engine()
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(
                    text("""
                    INSERT INTO execution_audits
                    (tenant_id, source_id, sql_hash, decision, duration_ms, row_count, status, error, created_at)
                    VALUES
                    (:tenant_id, :source_id, :sql_hash, :decision, :duration_ms, :row_count, :status, :error, CURRENT_TIMESTAMP)
                    """),
                    {
                        "tenant_id": tenant_id,
                        "source_id": source_id or tenant_id,
                        "sql_hash": sql_hash,
                        "decision": decision,
                        "duration_ms": duration_ms,
                        "row_count": row_count,
                        "status": status,
                        "error": error_msg,
                    },
                )
    except Exception:
        # Audit failure must not crash execution
        pass


def map_sqlglot_dialect(dialect: str) -> str:
    d = (dialect or "postgres").lower()
    if d in ("postgresql", "postgres"):
        return "postgres"
    if d in ("mysql", "mariadb"):
        return "mysql"
    if d in ("sqlite", "sqlite3"):
        return "sqlite"
    if d in ("mssql", "sqlserver", "tsql"):
        return "tsql"
    return "postgres"


def validate_and_prepare_sql(
    sql_query: str,
    tenant_id: str,
    dialect: str = "postgres",
    source_id: str | None = None,
    allowed_schema_override: dict[str, set[str]] | None = None,
) -> str:
    """Check that the SQL query is safe and allowed, then inject LIMIT."""
    if not sql_query or not sql_query.strip():
        raise SqlExecutionError("SQL query cannot be empty")

    sqlglot_dialect = map_sqlglot_dialect(dialect)

    # 1. Regex keyword check
    upper_query = sql_query.upper()
    for pattern in FORBIDDEN_KEYWORDS_REGEX:
        if re.search(pattern, upper_query):
            raise SqlExecutionError("Mot-clé interdit détecté. La requête doit être en LECTURE SEULE.")

    # 2. Parse AST
    try:
        parsed = sqlglot.parse(sql_query, read=sqlglot_dialect)
    except Exception as e:
        raise SqlExecutionError(f"Impossible d'analyser la requête SQL : {e}")

    if not parsed or len(parsed) > 1:
        raise SqlExecutionError("Une seule instruction SQL est autorisée par requête.")

    ast = parsed[0]

    # 3. Restrict AST root to SELECT
    if not isinstance(ast, exp.Select):
        raise SqlExecutionError("Seules les requêtes SELECT sont autorisées.")

    # Check for forbidden AST nodes anywhere in the tree
    forbidden_types = (
        exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
        exp.Command, exp.TruncateTable, exp.Merge,
    )
    for forbidden_type in forbidden_types:
        if list(ast.find_all(forbidden_type)):
            raise SqlExecutionError("Opération interdite détectée (modification de données).")

    # Check for dangerous system functions
    lower_query = sql_query.lower()
    for func in FORBIDDEN_FUNCTIONS:
        if re.search(rf"\b{re.escape(func)}\s*\(", lower_query):
            raise SqlExecutionError(f"Fonction système dangereuse interdite : '{func}'.")

    for node in ast.walk():
        fname = ""
        if isinstance(node, (exp.Func, exp.Anonymous)):
            this_val = getattr(node, "this", None)
            if isinstance(this_val, str):
                fname = this_val
            elif hasattr(this_val, "name"):
                fname = this_val.name
            elif hasattr(this_val, "this") and isinstance(this_val.this, str):
                fname = this_val.this
            else:
                fname = getattr(node, "name", "") or getattr(node, "key", "")
        elif hasattr(node, "key") and str(node.key).lower() in FORBIDDEN_FUNCTIONS:
            fname = str(node.key).lower()
        if fname and str(fname).lower() in FORBIDDEN_FUNCTIONS:
            raise SqlExecutionError(f"Fonction système dangereuse interdite : '{fname}'.")

    # Check for Star / SELECT *
    if list(ast.find_all(exp.Star)):
        raise SqlExecutionError(
            "L'utilisation de 'SELECT *' est interdite. Veuillez sélectionner explicitement les colonnes autorisées."
        )

    # 4. Check Policy Allowlist
    if allowed_schema_override is not None:
        allowed_schema = allowed_schema_override
    else:
        allowed_schema = get_allowed_schema(tenant_id, source_id)

    if not allowed_schema:
        raise SqlExecutionError("Aucune donnée n'est autorisée par la politique d'accès pour cette source (Deny-All).")

    referenced_tables: set[str] = set()
    aliases: dict[str, str] = {}

    for table_node in ast.find_all(exp.Table):
        t_name = table_node.name.lower()
        referenced_tables.add(t_name)
        if t_name not in allowed_schema:
            raise SqlExecutionError(f"L'accès à la table '{table_node.name}' est refusé par la politique de sécurité.")
        if table_node.alias:
            aliases[table_node.alias.lower()] = t_name

    # Check Columns and reject SELECT *
    projection_aliases = {
        expression.alias.lower()
        for expression in ast.expressions
        if isinstance(expression, exp.Alias) and expression.alias
    }

    for column_node in ast.find_all(exp.Column):
        column_name = column_node.name.lower()
        qualifier = (column_node.table or "").lower()

        if column_name == "*":
            raise SqlExecutionError(
                "L'utilisation de 'SELECT *' est interdite. Veuillez sélectionner explicitement les colonnes autorisées."
            )

        if qualifier:
            table_name = aliases.get(qualifier, qualifier)
            if table_name not in allowed_schema:
                raise SqlExecutionError(
                    f"L'accès à la colonne '{column_node.name}' est refusé par la politique de sécurité."
                )
            col_set = allowed_schema.get(table_name, set())
            if col_set and column_name not in col_set:
                raise SqlExecutionError(
                    f"L'accès à la colonne '{column_node.name}' est refusé par la politique de sécurité."
                )
            continue

        if column_name in projection_aliases:
            continue

        matching_tables = [
            table_name
            for table_name in referenced_tables
            if not allowed_schema.get(table_name) or column_name in allowed_schema.get(table_name, set())
        ]
        if len(matching_tables) == 0:
            raise SqlExecutionError(
                f"La colonne '{column_node.name}' est ambiguë ou non explicitement autorisée. Veuillez la préfixer avec le nom de la table."
            )

    # 5. Inject LIMIT if missing or exceeding max_limit
    limit_node = ast.args.get("limit")
    max_limit = 1000
    if not limit_node:
        ast = ast.limit(max_limit)
    else:
        try:
            val = int(limit_node.expression.name)
            if val > max_limit:
                ast = ast.limit(max_limit)
        except Exception:
            ast = ast.limit(max_limit)

    return ast.sql(dialect=sqlglot_dialect)


def execute_query(
    sql_query: str,
    tenant_id: str,
    source_id: str | None = None,
    allowed_schema_override: dict[str, set[str]] | None = None,
) -> list[dict[str, Any]]:
    """Execute a validated SQL query for a specific tenant and return the results."""
    start_time = time.time()

    # Resolve the target first so validation uses the target database dialect.
    # Parsing a MySQL/MSSQL query as PostgreSQL can silently rewrite dialect-
    # specific syntax before the query reaches the selected adapter.
    try:
        engine = get_engine_for_tenant(tenant_id, source_id)
        dialect_name = engine.dialect.name
    except Exception as exc:
        raise SqlExecutionError(f"Erreur de connexion à la base de données : {str(exc)}")

    # Validate against the actual target dialect before opening an execution
    # transaction. The allowlist remains tenant/source scoped and deny-by-default.
    try:
        safe_sql = validate_and_prepare_sql(
            sql_query,
            tenant_id,
            dialect=dialect_name,
            source_id=source_id,
            allowed_schema_override=allowed_schema_override,
        )
    except SqlExecutionError as exc:
        log_audit(tenant_id, sql_query, "DENY", 0, 0, "ERROR", exc.message, source_id)
        raise
    except Exception as exc:
        log_audit(tenant_id, sql_query, "DENY", 0, 0, "ERROR", "Erreur interne de validation.", source_id)
        raise SqlExecutionError(f"Erreur interne de validation : {str(exc)}")

    try:
        DatabaseAdapterFactory.get_adapter(dialect_name)
        with engine.connect() as conn:
            if dialect_name == "postgresql":
                try:
                    conn.execute(text("SET TRANSACTION READ ONLY"))
                    conn.execute(text("SET statement_timeout = '15s'"))
                except Exception:
                    pass
            elif dialect_name == "mysql":
                try:
                    conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
                    conn.execute(text("SET SESSION max_execution_time = 15000"))
                except Exception:
                    pass
            elif dialect_name == "sqlite":
                try:
                    conn.execute(text("PRAGMA query_only = ON"))
                except Exception:
                    pass

            result = conn.execute(text(safe_sql))
            columns = list(result.keys())
            rows = result.fetchmany(1000)
            data = [dict(zip(columns, row)) for row in rows]

        duration_ms = int((time.time() - start_time) * 1000)
        log_audit(tenant_id, safe_sql, "ALLOW", duration_ms, len(data), "SUCCESS", "", source_id)
        return data

    except SQLAlchemyError as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = f"Erreur de base de données : {str(exc.orig) if hasattr(exc, 'orig') else str(exc)}"
        log_audit(tenant_id, safe_sql, "ALLOW", duration_ms, 0, "ERROR", error_msg, source_id)
        raise SqlExecutionError("Erreur de base de données lors de l'exécution.")
    except Exception as exc:
        duration_ms = int((time.time() - start_time) * 1000)
        log_audit(tenant_id, safe_sql, "ALLOW", duration_ms, 0, "ERROR", "Erreur interne d'exécution.", source_id)
        raise SqlExecutionError("Erreur interne d'exécution.")


def validate_ast(
    sql_query: str,
    allowed_tables: list[str] | None = None,
    dialect: str = "postgres",
    tenant_id: str = "test",
    source_id: str | None = None,
) -> SecurityCheckResult:
    """Convenience validator returning a structured SecurityCheckResult."""
    try:
        if allowed_tables is not None:
            allowed_override = {t.lower(): set() for t in allowed_tables}
        else:
            try:
                temp_parsed = sqlglot.parse(sql_query, read=map_sqlglot_dialect(dialect))
                if temp_parsed and temp_parsed[0]:
                    allowed_override = {t.name.lower(): set() for t in temp_parsed[0].find_all(exp.Table)}
                else:
                    allowed_override = None
            except Exception:
                allowed_override = None

        sanitized = validate_and_prepare_sql(
            sql_query=sql_query,
            tenant_id=tenant_id,
            dialect=dialect,
            source_id=source_id,
            allowed_schema_override=allowed_override,
        )
        return SecurityCheckResult(is_valid=True, sanitized_sql=sanitized)
    except SqlExecutionError as e:
        return SecurityCheckResult(is_valid=False, error_message=e.message)
    except Exception as e:
        return SecurityCheckResult(is_valid=False, error_message=str(e))
