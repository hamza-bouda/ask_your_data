"""SQL Generation Logic.

Uses configured LLM Provider (DeepSeek / OpenAI) to generate valid multi-dialect queries based on schemas.
"""

import os
import re
from typing import Any, Optional
from dotenv import load_dotenv

from contracts.llm import get_llm_provider

try:
    from app.models import SqlDraft
    from app.prompts import SQL_GENERATION_PROMPT, SQL_REPAIR_PROMPT
except ImportError:
    from backend.services.sql_generator.app.models import SqlDraft
    from backend.services.sql_generator.app.prompts import SQL_GENERATION_PROMPT, SQL_REPAIR_PROMPT

load_dotenv()


def _mock_sql_draft(semantic_plan: dict[str, Any], schema: dict[str, Any]) -> SqlDraft:
    """Offline deterministic SQL for the test runtime only."""
    tables = semantic_plan.get("source_tables") or []
    if not tables:
        tables = [
            table["name"] if isinstance(table, dict) else table
            for table in schema.get("tables", [])
            if (isinstance(table, dict) and table.get("name")) or isinstance(table, str)
        ]
    if not tables or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tables[0]):
        raise RuntimeError("Mock SQL generation requires one safe source table")
    table_name = tables[0]
    return SqlDraft(
        intent="count rows",
        metric="row_count",
        dimensions=[],
        filters=[],
        sql_query=f'SELECT COUNT(*) AS row_count FROM "{table_name}"',
        confidence=1.0,
        explanation="Deterministic offline count for the end-to-end workflow.",
    )


def generate_sql(
    query: str,
    semantic_plan: dict[str, Any],
    schema: dict[str, Any],
    chat_history: list[dict[str, Any]] = None,
) -> SqlDraft:
    """Generate a SQL query based on natural language and a database schema."""
    provider_name = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider_name in ("mock", "test"):
        return _mock_sql_draft(semantic_plan, schema)

    try:
        provider = get_llm_provider()
        structured_llm = provider.with_structured_output(SqlDraft)

        schema_str = str(schema)
        chain = SQL_GENERATION_PROMPT | structured_llm

        result = chain.invoke({
            "schema_context": schema_str,
            "semantic_plan": str(semantic_plan),
            "history": str(chat_history or []),
            "question": query,
        })
        return result
    except Exception as e:
        raise RuntimeError(f"LLM SQL Generation failed: {e}")


def repair_sql(
    query: str,
    schema: dict[str, Any],
    previous_sql: str,
    error_message: str,
) -> SqlDraft:
    """Attempt to repair a broken SQL query."""
    provider_name = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    if provider_name in ("mock", "test"):
        return _mock_sql_draft({"source_tables": []}, schema)

    try:
        provider = get_llm_provider()
        structured_llm = provider.with_structured_output(SqlDraft)

        schema_str = str(schema)
        chain = SQL_REPAIR_PROMPT | structured_llm

        result = chain.invoke({
            "schema_context": schema_str,
            "question": query,
            "previous_sql": previous_sql,
            "error_message": error_message,
        })
        return result
    except Exception as e:
        raise RuntimeError(f"LLM SQL Repair failed: {e}")


class SQLGenerator:
    """Class wrapper for SQL Generation."""
    @staticmethod
    def generate(
        query: str,
        semantic_plan: dict[str, Any],
        schema: dict[str, Any],
        chat_history: list[dict[str, Any]] | None = None,
    ) -> SqlDraft:
        return generate_sql(query, semantic_plan, schema, chat_history)

    @staticmethod
    def repair(
        query: str,
        schema: dict[str, Any],
        previous_sql: str,
        error_message: str,
    ) -> SqlDraft:
        return repair_sql(query, schema, previous_sql, error_message)
