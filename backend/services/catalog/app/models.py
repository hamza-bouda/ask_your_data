from datetime import datetime
from sqlalchemy import String, JSON, Integer, ForeignKey, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy import JSON as Vector

try:
    from app.database import Base
except ImportError:
    from backend.services.catalog.app.database import Base


class TenantDatabase(Base):
    """Stores the connection string for a tenant's data database."""
    __tablename__ = "tenant_databases"
    __table_args__ = {"extend_existing": True}

    tenant_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    connection_string: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=True)
    dialect: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=True, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    catalog_version: Mapped[int] = mapped_column(Integer, default=1)

    tables = relationship("TableSchema", back_populates="database", cascade="all, delete-orphan")
    documents = relationship("CatalogDocument", back_populates="database", cascade="all, delete-orphan")
    metrics = relationship("SemanticMetric", back_populates="database", cascade="all, delete-orphan")


class DataSource(Base):
    """A governed physical datasource owned by a tenant."""
    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_data_sources_tenant_name"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    connection_string: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    dialect: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="registered")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    catalog_version: Mapped[int] = mapped_column(Integer, default=1)


class TableSchema(Base):
    """Stores introspection and metadata for a single table."""
    __tablename__ = "tables"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), ForeignKey("tenant_databases.tenant_id"))
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=True)
    table_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    modified_by: Mapped[str] = mapped_column(String(100), nullable=True)

    # Enrichment
    primary_key: Mapped[str] = mapped_column(String, nullable=True)
    foreign_keys: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    indices: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)
    catalog_version: Mapped[int] = mapped_column(Integer, default=1)

    # Deprecated - embeddings moved to CatalogDocument
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=True)

    columns = relationship("ColumnSchema", back_populates="table", cascade="all, delete-orphan")
    database = relationship("TenantDatabase", back_populates="tables")


class ColumnSchema(Base):
    """Stores metadata for a column within a table."""
    __tablename__ = "columns"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(Integer, ForeignKey("tables.id"))
    column_name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    last_modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    modified_by: Mapped[str] = mapped_column(String(100), nullable=True)

    # Enrichment
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True)

    table = relationship("TableSchema", back_populates="columns")


class CatalogDocument(Base):
    """Stores separated, versioned RAG documents for hybrid retrieval."""
    __tablename__ = "catalog_documents"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), ForeignKey("tenant_databases.tenant_id"))
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False) # table, column_group, relation, metric, synonym
    content: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    catalog_version: Mapped[int] = mapped_column(Integer, default=1)

    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=True)

    database = relationship("TenantDatabase", back_populates="documents")


class SemanticMetric(Base):
    """Certified metrics governed by the semantic layer."""
    __tablename__ = "semantic_metrics"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), ForeignKey("tenant_databases.tenant_id"))
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    sql_expression: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=True, default="number")
    time_grains: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)
    dimensions: Mapped[list[str]] = mapped_column(JSON, nullable=True, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    database = relationship("TenantDatabase", back_populates="metrics")


class SemanticSynonym(Base):
    """Glossary and synonyms for the semantic layer."""
    __tablename__ = "semantic_synonyms"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), ForeignKey("tenant_databases.tenant_id"))
    source_id: Mapped[str] = mapped_column(String(36), index=True, nullable=True)
    term: Mapped[str] = mapped_column(String(200), nullable=False)
    synonyms: Mapped[str] = mapped_column(String, nullable=False) # comma-separated
    target_object: Mapped[str] = mapped_column(String(200), nullable=True) # e.g. table.column


class ExecutionAudit(Base):
    __tablename__ = "execution_audits"
    __table_args__ = {"extend_existing": True}
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=True)
    sql_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AdminAudit(Base):
    __tablename__ = "admin_audits"
    __table_args__ = {"extend_existing": True}
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target: Mapped[str] = mapped_column(String(200), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=True)
