"""SQL Generation Logic.

Uses DeepSeek API to generate valid PostgreSQL queries based on schemas.
"""
import os
from typing import Any, Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

try:
    from app.models import SqlDraft
    from app.prompts import SQL_GENERATION_PROMPT, SQL_REPAIR_PROMPT
except ImportError:
    from backend.services.sql_generator.app.models import SqlDraft
    from backend.services.sql_generator.app.prompts import SQL_GENERATION_PROMPT, SQL_REPAIR_PROMPT

load_dotenv()

def _get_llm():
    return ChatOpenAI(
        model="deepseek-chat", 
        api_key=os.getenv("DEEPSEEK_API_KEY"), 
        base_url="https://api.deepseek.com/v1",
        max_retries=2
    )

def generate_sql(query: str, schema: dict[str, Any]) -> SqlDraft:
    """Generate a SQL query based on natural language and a database schema."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(SqlDraft)
    
    schema_str = str(schema)
    
    chain = SQL_GENERATION_PROMPT | structured_llm
    
    try:
        result = chain.invoke({
            "schema_context": schema_str,
            "question": query
        })
        return result
    except Exception as e:
        # Provide a fallback or raise
        raise RuntimeError(f"LLM Generation failed: {e}")

def repair_sql(query: str, schema: dict[str, Any], previous_sql: str, error_message: str) -> SqlDraft:
    """Attempt to repair a broken SQL query."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(SqlDraft)
    
    schema_str = str(schema)
    
    chain = SQL_REPAIR_PROMPT | structured_llm
    
    try:
        result = chain.invoke({
            "schema_context": schema_str,
            "question": query,
            "previous_sql": previous_sql,
            "error_message": error_message
        })
        return result
    except Exception as e:
        raise RuntimeError(f"LLM Repair failed: {e}")

