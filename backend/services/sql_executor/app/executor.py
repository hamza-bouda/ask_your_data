"""SQL Execution Engine with Safety Checks.

Parses SQL statically via AST to ensure no mutating commands are run,
checks tables/columns against an allowlist, injects LIMIT, 
and executes in a read-only transaction context with an audit trail.
"""

import re
import time
import hashlib
from typing import Any, Tuple
import sqlglot
import sqlglot.expressions as exp
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

class SqlExecutionError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

def get_allowed_schema(tenant_id: str) -> dict:
    """Fetch the allowed tables and columns from the global catalog."""
    try:
        from app.connection_manager import _global_engine
    except ImportError:
        from backend.services.sql_executor.app.connection_manager import _global_engine
        
    allowed = {}
    with _global_engine.connect() as conn:
        # Check if database is allowed
        db_res = conn.execute(
            text("SELECT is_allowed FROM tenant_databases WHERE tenant_id = :tenant_id AND status = 'active'"),
            {"tenant_id": tenant_id}
        ).fetchone()
        
        if not db_res or not db_res[0]:
            return {} # Not allowed at all
            
        # Get allowed tables and columns
        res = conn.execute(
            text("""
            SELECT t.table_name, c.column_name 
            FROM tables t 
            JOIN columns c ON t.id = c.table_id 
            WHERE t.tenant_id = :tenant_id 
              AND t.is_allowed IS TRUE
              AND c.is_allowed IS TRUE
            """),
            {"tenant_id": tenant_id}
        )
        for row in res:
            t_name = row[0].lower()
            c_name = row[1].lower()
            if t_name not in allowed:
                allowed[t_name] = set()
            allowed[t_name].add(c_name)
    return allowed

def log_audit(tenant_id: str, sql_query: str, decision: str, duration_ms: int, row_count: int, status: str, error_msg: str):
    """Write an execution audit to the global database."""
    try:
        from app.connection_manager import _global_engine
    except ImportError:
        from backend.services.sql_executor.app.connection_manager import _global_engine
        
    sql_hash = hashlib.sha256(sql_query.encode()).hexdigest()
    
    with _global_engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("""
                INSERT INTO execution_audits 
                (tenant_id, sql_hash, decision, duration_ms, row_count, status, error, created_at)
                VALUES 
                (:tenant_id, :sql_hash, :decision, :duration_ms, :row_count, :status, :error, CURRENT_TIMESTAMP)
                """),
                {
                    "tenant_id": tenant_id,
                    "sql_hash": sql_hash,
                    "decision": decision,
                    "duration_ms": duration_ms,
                    "row_count": row_count,
                    "status": status,
                    "error": error_msg
                }
            )

def validate_and_prepare_sql(sql_query: str, tenant_id: str, dialect: str = "postgres") -> str:
    """Check that the SQL query is safe and allowed, then inject LIMIT."""
    sqlglot_dialect = {
        "postgresql": "postgres",
        "postgres": "postgres",
        "mysql": "mysql",
        "sqlite": "sqlite",
    }.get(dialect)
    if not sqlglot_dialect:
        raise SqlExecutionError(f"Unsupported SQL dialect: {dialect}")
    
    # 1. Regex fallback defense
    forbidden_keywords = [
        r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
        r"\bALTER\b", r"\bGRANT\b", r"\bREVOKE\b", r"\bTRUNCATE\b",
        r"\bCREATE\b", r"\bREPLACE\b", r"\bEXECUTE\b", r"\bMERGE\b"
    ]
    upper_query = sql_query.upper()
    for keyword in forbidden_keywords:
        if re.search(keyword, upper_query):
            raise SqlExecutionError("Forbidden keyword detected by regex fallback. Query must be READ ONLY.")

    # 2. Parse AST
    try:
        parsed = sqlglot.parse(sql_query, read=sqlglot_dialect)
    except Exception as e:
        raise SqlExecutionError(f"Failed to parse SQL: {e}")
        
    if not parsed or len(parsed) > 1:
        raise SqlExecutionError("Only a single SQL statement is allowed.")
        
    ast = parsed[0]
    
    # 3. Restrict AST type to SELECT or WITH ... SELECT
    if not isinstance(ast, exp.Select):
        raise SqlExecutionError("Only SELECT queries are allowed.")
        
    # Check for forbidden AST nodes anywhere in the tree
    forbidden_types = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command)
    for forbidden_type in forbidden_types:
        if list(ast.find_all(forbidden_type)):
            raise SqlExecutionError("Forbidden operation detected in AST.")

    # 4. Check Policy Allowlist
    allowed_schema = get_allowed_schema(tenant_id)
    if not allowed_schema:
        raise SqlExecutionError("No database or tables are allowed by policy for this tenant.")
        
    for table_node in ast.find_all(exp.Table):
        t_name = table_node.name.lower()
        if t_name not in allowed_schema:
            raise SqlExecutionError(f"Access to table '{table_node.name}' is denied by policy.")

    # Resolve aliases before checking every selected/referenced column.  Table-level
    # approval alone is insufficient: a user can be allowed to see a table while a
    # sensitive column remains denied.
    referenced_tables = set()
    aliases = {}
    for table_node in ast.find_all(exp.Table):
        table_name = table_node.name.lower()
        referenced_tables.add(table_name)
        if table_node.alias:
            aliases[table_node.alias.lower()] = table_name

    # SQL permits ORDER BY a projection alias such as `ORDER BY total DESC`.
    # The alias originates from an already validated expression, so it is not a
    # source column that needs a second policy lookup.
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
                "SELECT * is not allowed. Select explicit columns allowed by policy."
            )

        if qualifier:
            table_name = aliases.get(qualifier, qualifier)
            if table_name not in allowed_schema or column_name not in allowed_schema[table_name]:
                raise SqlExecutionError(
                    f"Access to column '{column_node.name}' is denied by policy."
                )
            continue

        if column_name in projection_aliases:
            continue

        matching_tables = [
            table_name
            for table_name in referenced_tables
            if column_name in allowed_schema.get(table_name, set())
        ]
        if len(matching_tables) != 1:
            raise SqlExecutionError(
                f"Column '{column_node.name}' is not uniquely allowed by policy. Qualify it with an allowed table."
            )
            
    # 5. Inject LIMIT if missing or too large
    limit_node = ast.args.get("limit")
    max_limit = 1000
    if not limit_node:
        ast = ast.limit(max_limit)
    else:
        try:
            val = int(limit_node.expression.name)
            if val > max_limit:
                ast = ast.limit(max_limit)
        except:
            ast = ast.limit(max_limit)
            
    return ast.sql(dialect=sqlglot_dialect)


def execute_query(sql_query: str, tenant_id: str) -> list[dict[str, Any]]:
    """Execute a validated SQL query for a specific tenant and return the results."""
    
    start_time = time.time()
    
    try:
        from app.connection_manager import get_tenant_session
    except ImportError:
        from backend.services.sql_executor.app.connection_manager import get_tenant_session
        
    try:
        db = get_tenant_session(tenant_id)
    except Exception as exc:
        raise SqlExecutionError(f"Database Connection Error: {str(exc)}")
        
    dialect_name = db.bind.dialect.name
    
    try:
        safe_sql = validate_and_prepare_sql(sql_query, tenant_id, dialect=dialect_name)
    except SqlExecutionError as exc:
        log_audit(tenant_id, sql_query, "DENY", 0, 0, "ERROR", exc.message)
        raise
    except Exception as exc:
        log_audit(tenant_id, sql_query, "DENY", 0, 0, "ERROR", "Internal Validation Error")
        raise SqlExecutionError("Internal Validation Error")
    
    try:
        if dialect_name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
            db.execute(text("SET statement_timeout = '15s'"))
        
        # Execute the actual query
        result = db.execute(text(safe_sql))
        
        # Fetch results and map rows to dictionaries
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in result.fetchall()]
        
        duration_ms = int((time.time() - start_time) * 1000)
        log_audit(tenant_id, safe_sql, "ALLOW", duration_ms, len(data), "SUCCESS", "")
        return data
        
    except SQLAlchemyError as exc:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = f"Database error: {str(exc.orig) if hasattr(exc, 'orig') else str(exc)}"
        log_audit(tenant_id, safe_sql, "ALLOW", duration_ms, 0, "ERROR", error_msg)
        raise SqlExecutionError("Database error during execution.")
    except Exception as exc:
        db.rollback()
        duration_ms = int((time.time() - start_time) * 1000)
        log_audit(tenant_id, safe_sql, "ALLOW", duration_ms, 0, "ERROR", "Internal execution error")
        raise SqlExecutionError("Internal execution error.")
    finally:
        db.close()
