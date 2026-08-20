"""SQL Execution Engine with Safety Checks.

Parses SQL statically to ensure no mutating commands are run,
then executes it in a read-only transaction context.
"""

import re
from typing import Any
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


class SqlExecutionError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


def validate_sql_safety(sql_query: str) -> None:
    """Check that the SQL query is safe (READ ONLY)."""
    forbidden_keywords = [
        r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b",
        r"\bALTER\b", r"\bGRANT\b", r"\bREVOKE\b", r"\bTRUNCATE\b",
        r"\bCREATE\b", r"\bREPLACE\b", r"\bEXECUTE\b", r"\bMERGE\b"
    ]
    
    upper_query = sql_query.upper()
    
    for keyword in forbidden_keywords:
        if re.search(keyword, upper_query):
            raise SqlExecutionError(f"Forbidden keyword detected. Query must be READ ONLY.")


def execute_query(sql_query: str, tenant_id: str) -> list[dict[str, Any]]:
    """Execute a validated SQL query for a specific tenant and return the results."""
    validate_sql_safety(sql_query)
    
    try:
        from app.connection_manager import get_tenant_session
    except ImportError:
        from backend.services.sql_executor.app.connection_manager import get_tenant_session
        
    db = get_tenant_session(tenant_id)
    
    try:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
        
        # Execute the actual query
        result = db.execute(text(sql_query))
        
        # Fetch results and map rows to dictionaries
        columns = result.keys()
        data = [dict(zip(columns, row)) for row in result.fetchall()]
        
        return data
        
    except SQLAlchemyError as exc:
        db.rollback()
        raise SqlExecutionError(f"Database error during execution: {str(exc)}")
    except Exception as exc:
        db.rollback()
        raise SqlExecutionError(f"Internal execution error: {str(exc)}")
    finally:
        db.close()
