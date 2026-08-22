"""Client for the tenant-scoped Data Catalog service.

All schema context comes from the live catalog API. There is deliberately no
static fallback schema in this runtime module: tests must provide an explicit
mock HTTP response or run the catalog service.
"""

import os
import requests
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


CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog:8002")

def search_catalog(query: str, tenant_id: str, source_id: str | None = None) -> CatalogSearchResult:
    """Search the catalog for tables relevant to the query via the Catalog service."""
    try:
        # Schema discovery needs the complete allowlisted catalog, not a fuzzy RAG
        # match on the user's natural-language question.
        normalized = query.lower()
        is_discovery = (
            any(term in normalized for term in ("table", "schema", "schéma", "catalog", "catalogue", "colonne", "column"))
            or os.getenv("LLM_PROVIDER", "").lower() == "mock"
        )
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
