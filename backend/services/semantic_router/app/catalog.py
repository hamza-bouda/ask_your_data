"""Data Catalog Search Logic (Mock Version).

In a real implementation, this would use a Vector Store (e.g. pgvector, Qdrant) 
or an Elasticsearch index to find the most relevant tables and columns for a given query.
Here we return a static dummy schema for testing.
"""

import os
import requests
from typing import Any
from pydantic import BaseModel


class ColumnMeta(BaseModel):
    name: str
    type: str
    description: str


class TableMeta(BaseModel):
    name: str
    description: str
    columns: list[ColumnMeta]


class CatalogSearchResult(BaseModel):
    tables: list[TableMeta]


# Mock schema representing an e-commerce database
MOCK_SCHEMA = [
    TableMeta(
        name="users",
        description="Registered users of the platform",
        columns=[
            ColumnMeta(name="id", type="uuid", description="Primary key"),
            ColumnMeta(name="created_at", type="timestamp", description="Registration date"),
            ColumnMeta(name="country", type="varchar", description="User's country"),
        ]
    ),
    TableMeta(
        name="sales",
        description="Completed transactions and orders",
        columns=[
            ColumnMeta(name="id", type="uuid", description="Primary key"),
            ColumnMeta(name="user_id", type="uuid", description="Buyer ID"),
            ColumnMeta(name="amount", type="decimal", description="Total purchase amount"),
            ColumnMeta(name="date", type="timestamp", description="Date of transaction"),
        ]
    ),
]


CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog:8002")

def search_catalog(query: str, tenant_id: str, source_id: str | None = None) -> CatalogSearchResult:
    """Search the catalog for tables relevant to the query via the Catalog service."""
    try:
        # Schema discovery needs the complete allowlisted catalog, not a fuzzy RAG
        # match on the user's natural-language question.
        normalized = query.lower()
        is_discovery = any(term in normalized for term in ("table", "schema", "schéma", "catalog", "catalogue", "colonne", "column"))
        if is_discovery:
            response = requests.get(
                f"{CATALOG_URL}/api/v1/catalog/tables",
                headers={"X-Tenant-Id": tenant_id, "X-Is-Admin": "false", "X-Source-Id": source_id or ""},
                timeout=10,
            )
            response.raise_for_status()
            return CatalogSearchResult(tables=[TableMeta(
                name=table["table_name"],
                description=table.get("description", ""),
                columns=[ColumnMeta(name=column["name"], type=column.get("type", ""), description=column.get("description", "")) for column in table.get("columns", [])],
            ) for table in response.json().get("tables", [])])

        resp = requests.post(
            f"{CATALOG_URL}/internal/catalog/search",
            json={"query": query, "tenant_id": tenant_id, "source_id": source_id, "top_k": 5},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        tables = []
        for document in data.get("results", []):
            metadata = document.get("metadata", {})
            table_name = metadata.get("table_name")
            if not table_name:
                continue
            columns = metadata.get("columns", [])
            tables.append(TableMeta(
                name=table_name,
                description=document.get("content", ""),
                columns=[ColumnMeta(name=column, type="", description="") for column in columns],
            ))
            
        return CatalogSearchResult(tables=tables)
    except Exception as e:
        print(f"Error querying catalog: {e}")
        return CatalogSearchResult(tables=[])
