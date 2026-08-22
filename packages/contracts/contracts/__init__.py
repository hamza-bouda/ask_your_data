"""Ask Your Data — Shared contracts.

Pydantic models and interfaces shared across all microservices to enforce a single
contract for errors, tenant context, query lifecycle events, database adapters,
LLM providers, and chart specifications.
"""

from contracts.tenant import TenantContext
from contracts.query import QueryRequest
from contracts.events import RunEvent, RunEventType
from contracts.chart import ChartSpec, ChartType
from contracts.errors import ApiError
from contracts.semantic import SemanticPlan
from contracts.adapters import (
    BaseDatabaseAdapter,
    CatalogIntrospection,
    TableIntrospection,
    ColumnIntrospection,
    ForeignKeyIntrospection,
    IndexIntrospection,
    DatabaseAdapterFactory,
)
from contracts.llm import (
    BaseLLMProvider,
    DeepSeekLLMProvider,
    OpenAILLMProvider,
    MockLLMProvider,
    get_llm_provider,
)

__all__ = [
    "TenantContext",
    "QueryRequest",
    "RunEvent",
    "RunEventType",
    "ChartSpec",
    "ChartType",
    "ApiError",
    "SemanticPlan",
    "BaseDatabaseAdapter",
    "CatalogIntrospection",
    "TableIntrospection",
    "ColumnIntrospection",
    "ForeignKeyIntrospection",
    "IndexIntrospection",
    "DatabaseAdapterFactory",
    "BaseLLMProvider",
    "DeepSeekLLMProvider",
    "OpenAILLMProvider",
    "MockLLMProvider",
    "get_llm_provider",
]
