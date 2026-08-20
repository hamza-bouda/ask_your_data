"""SQL Generation Logic (Mock Version).

In a real implementation, this service would take the user query and the database schema
(retrieved from the Semantic Router/Catalog) and use an LLM (e.g. GPT-4, Llama 3) to generate
a valid PostgreSQL query.

Here we use a mock implementation for testing architecture.
"""

from typing import Any
from pydantic import BaseModel


class SqlResult(BaseModel):
    sql_query: str
    explanation: str


def generate_sql(query: str, schema: list[dict[str, Any]]) -> SqlResult:
    """Generate a SQL query based on natural language and a database schema."""
    q = query.lower()
    
    # Mock responses based on keywords in the query
    if "combien" in q and "utilisateur" in q:
        return SqlResult(
            sql_query="SELECT COUNT(*) FROM users;",
            explanation="Compte le nombre total d'utilisateurs enregistrés dans la table users."
        )
        
    if "ventes" in q and "total" in q:
        return SqlResult(
            sql_query="SELECT SUM(amount) FROM sales;",
            explanation="Calcule la somme de tous les montants dans la table sales."
        )
        
    # Default fallback mock response
    return SqlResult(
        sql_query="SELECT * FROM users LIMIT 10;",
        explanation="Requête par défaut sélectionnant les 10 premiers utilisateurs."
    )
