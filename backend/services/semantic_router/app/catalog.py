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

def search_catalog(query: str, tenant_id: str) -> CatalogSearchResult:
    """Search the catalog for tables relevant to the query via the Catalog service."""
    try:
        resp = requests.post(
            f"{CATALOG_URL}/internal/catalog/search",
            json={"query": query, "tenant_id": tenant_id, "top_k": 5},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        tables = []
        for t in data.get("results", []):
            cols = [ColumnMeta(name=c["name"], type=c["type"], description=c.get("description", "")) for c in t["columns"]]
            tables.append(TableMeta(name=t["table_name"], description=t.get("description", ""), columns=cols))
            
        return CatalogSearchResult(tables=tables)
    except Exception as e:
        print(f"Error querying catalog: {e}")
        return CatalogSearchResult(tables=[])
