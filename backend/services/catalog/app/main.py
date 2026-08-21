import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import Request, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer
from cryptography.fernet import Fernet

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics

from app.database import get_db, create_tables
from app.models import DataSource, TenantDatabase, TableSchema, ColumnSchema, AdminAudit, SemanticMetric, SemanticSynonym, CatalogDocument

app = create_service_app(service_name="catalog")

# Observability setup
setup_logging(service_name="catalog")
setup_tracing(service_name="catalog", app=app)
setup_metrics(app)


# Global embedding model (loaded on startup)
embedder = None
cipher_suite = None

@app.on_event("startup")
def startup_event():
    global embedder, cipher_suite
    create_tables()
    print("Loading embedding model...")
    embedder = SentenceTransformer('BAAI/bge-small-en-v1.5')
    print("Embedding model loaded.")
    
    app_env = os.getenv("APP_ENV", "development").lower()
    is_production = app_env in {"production", "prod"}
    fernet_key = os.getenv("FERNET_KEY")
    if not fernet_key:
        if is_production:
            raise RuntimeError("FERNET_KEY must be configured in production.")
        print("WARNING: FERNET_KEY not set. Using a temporary development key.")
        fernet_key = Fernet.generate_key().decode()
    cipher_suite = Fernet(fernet_key.encode())

def encrypt_secret(secret: str) -> str:
    return cipher_suite.encrypt(secret.encode()).decode()

def decrypt_secret(secret: str) -> str:
    return cipher_suite.decrypt(secret.encode()).decode()

def log_audit(db: Session, tenant_id: str, user_id: str, action: str, target: str, correlation_id: str = None):
    audit = AdminAudit(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        target=target,
        correlation_id=correlation_id
    )
    db.add(audit)
    # Don't commit here, let the caller commit the transaction


def source_from_request(db: Session, request: Request, *, active_only: bool = False) -> DataSource:
    """Resolve a tenant-owned datasource, requiring an explicit choice when needed."""
    tenant_id = request.headers.get("x-tenant-id", "acme")
    source_id = request.headers.get("x-source-id")
    query = db.query(DataSource).filter(DataSource.tenant_id == tenant_id)
    if active_only:
        query = query.filter(DataSource.status == "active")
    if source_id:
        source = query.filter(DataSource.id == source_id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Datasource not found")
        return source
    sources = query.order_by(DataSource.created_at.asc()).limit(2).all()
    if not sources:
        raise HTTPException(status_code=404, detail="Source not registered")
    if len(sources) > 1:
        raise HTTPException(status_code=409, detail="Select a datasource before continuing")
    return sources[0]


def refresh_table_document_policy(db: Session, table: TableSchema) -> None:
    """Keep the RAG representation aligned with table and column policies.

    A retrieval document is user-facing context for the LLM, so it must not retain
    column names that the current policy denies.
    """
    allowed_columns = [
        column.column_name
        for column in table.columns
        if column.is_allowed and column.is_available
    ]
    document = (
        db.query(CatalogDocument)
        .filter(
            CatalogDocument.source_id == table.source_id,
            CatalogDocument.doc_type == "table",
            CatalogDocument.metadata_json.op("->>")("table_name") == table.table_name,
        )
        .first()
    )
    if not document:
        return

    document.is_allowed = table.is_allowed and bool(allowed_columns)
    document.metadata_json = {
        "table_name": table.table_name,
        "columns": allowed_columns,
    }
    document.content = (
        f"Table {table.table_name}: {table.description or ''}. "
        f"Authorized columns: {', '.join(allowed_columns)}."
    )
    if embedder:
        document.embedding = embedder.encode(document.content).tolist()


class RegisterRequest(BaseModel):
    connection_string: str
    name: Optional[str] = None
    source_id: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    tenant_id: str
    source_id: Optional[str] = None
    top_k: int = 5

class PolicyUpdateRequest(BaseModel):
    is_allowed: bool

@app.post("/api/v1/catalog/register")
def register_database(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Validates and stores the connection string without introspecting tables."""
    tenant_id = request.headers.get("x-tenant-id", "acme")
    user_id = request.headers.get("x-user-id", "system")
    correlation_id = request.headers.get("x-correlation-id")
    
    # 1. Connect and validate (Test connection)
    try:
        target_engine = create_engine(body.connection_string)
        with target_engine.connect() as conn:
            pass
    except Exception:
        # Driver exceptions can contain host names, usernames, or credentials.
        raise HTTPException(status_code=400, detail="Failed to connect to database")

    # 2. Store encrypted connection string
    encrypted_conn_str = encrypt_secret(body.connection_string)
    dialect = target_engine.dialect.name

    # Child catalog tables still retain their legacy tenant foreign key during
    # the additive migration. Ensure that compatibility parent exists for a
    # brand-new tenant while all source-aware operations use ``DataSource``.
    if not db.query(TenantDatabase).filter(TenantDatabase.tenant_id == tenant_id).first():
        db.add(TenantDatabase(
            tenant_id=tenant_id, connection_string=encrypted_conn_str,
            name=f"Database for {tenant_id}", dialect=dialect,
            status="active", is_allowed=True,
        ))
    
    db_record = None
    if body.source_id:
        db_record = db.query(DataSource).filter(
            DataSource.id == body.source_id, DataSource.tenant_id == tenant_id
        ).first()
        if not db_record:
            raise HTTPException(status_code=404, detail="Datasource not found")
    elif not body.name:
        # Preserve the old single-source registration behaviour for existing
        # clients while allowing named registrations to create extra sources.
        existing = db.query(DataSource).filter(DataSource.tenant_id == tenant_id).limit(2).all()
        if len(existing) == 1:
            db_record = existing[0]

    if not db_record:
        db_record = DataSource(
            id=str(uuid.uuid4()), tenant_id=tenant_id,
            connection_string=encrypted_conn_str, dialect=dialect,
            name=(body.name or f"Database for {tenant_id}"), status="registered",
            is_allowed=True,
        )
        db.add(db_record)
    else:
        db_record.connection_string = encrypted_conn_str
        db_record.dialect = dialect
        db_record.name = body.name or db_record.name
        db_record.status = "registered"
        db_record.is_allowed = True
        
    log_audit(db, tenant_id, user_id, "register_source", f"source:{db_record.id}", correlation_id)
    db.commit()
    
    return {"status": "success", "message": "Database registered successfully", "id": db_record.id}

@app.post("/api/v1/catalog/sync")
def sync_database(request: Request, db: Session = Depends(get_db)):
    """Introspects the target database, extracts full schemas, generates RAG documents."""
    import json
    tenant_id = request.headers.get("x-tenant-id", "acme")
    user_id = request.headers.get("x-user-id", "system")
    correlation_id = request.headers.get("x-correlation-id")
    
    db_record = source_from_request(db, request)
        
    try:
        conn_string = decrypt_secret(db_record.connection_string)
        target_engine = create_engine(conn_string)
        inspector = inspect(target_engine)
        table_names = inspector.get_table_names()
    except Exception:
        db_record.status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to sync database")

    db_record.catalog_version += 1
    current_version = db_record.catalog_version

    existing_tables = db.query(TableSchema).filter(TableSchema.source_id == db_record.id).all()
    existing_tables_map = {t.table_name: t for t in existing_tables}
    
    # Mark all existing as unavailable initially, we will mark them true if they still exist
    for t in existing_tables:
        t.is_available = False
        for c in t.columns:
            c.is_available = False

    for table_name in table_names:
        cols = inspector.get_columns(table_name)
        pk_constraint = inspector.get_pk_constraint(table_name)
        fks = inspector.get_foreign_keys(table_name)
        indices = inspector.get_indexes(table_name)
        table_comment = inspector.get_table_comment(table_name)
        
        primary_key = pk_constraint.get("constrained_columns", []) if pk_constraint else []
        pk_str = primary_key[0] if primary_key else None
        desc = table_comment.get("text", "") if table_comment and table_comment.get("text") else ""
        
        t_record = existing_tables_map.get(table_name)
        if t_record:
            t_record.is_available = True
            t_record.description = desc
            t_record.primary_key = pk_str
            t_record.foreign_keys = fks
            t_record.indices = indices
            t_record.catalog_version = current_version
        else:
            t_record = TableSchema(
                tenant_id=tenant_id,
                source_id=db_record.id,
                table_name=table_name,
                description=desc,
                primary_key=pk_str,
                foreign_keys=fks,
                indices=indices,
                catalog_version=current_version,
                is_allowed=False,
                is_available=True
            )
            db.add(t_record)
            
        db.flush()

        existing_cols = {c.column_name: c for c in t_record.columns}
        col_names = []
        for col in cols:
            c_name = col["name"]
            c_type = str(col["type"])
            c_nullable = col.get("nullable", True)
            c_desc = col.get("comment", "") or ""
            col_names.append(c_name)
            
            c_record = existing_cols.get(c_name)
            if c_record:
                c_record.is_available = True
                c_record.data_type = c_type
                c_record.is_nullable = c_nullable
                c_record.description = c_desc
            else:
                c_record = ColumnSchema(
                    table_id=t_record.id,
                    column_name=c_name,
                    data_type=c_type,
                    description=c_desc,
                    is_nullable=c_nullable,
                    is_allowed=False,
                    is_available=True
                )
                db.add(c_record)
                
        # Generate Table RAG Document
        from app.models import CatalogDocument
        doc_content = f"Table {table_name}: {desc}. Columns: {', '.join(col_names)}."
        if primary_key:
            doc_content += f" Primary Key: {pk_str}."
        if fks:
            fk_strs = [f"{fk['constrained_columns']} references {fk['referred_table']}.{fk['referred_columns']}" for fk in fks]
            doc_content += f" Foreign Keys: {'; '.join(fk_strs)}."
            
        doc_embedding = embedder.encode(doc_content).tolist() if embedder else None
        
        # We store one document per table version, or overwrite the old one
        # To avoid duplicating, we delete old documents for this table
        db.query(CatalogDocument).filter(
            CatalogDocument.source_id == db_record.id,
            CatalogDocument.doc_type == "table",
            CatalogDocument.metadata_json.op("->>")("table_name") == table_name
        ).delete(synchronize_session=False)
        
        doc = CatalogDocument(
            tenant_id=tenant_id,
            source_id=db_record.id,
            doc_type="table",
            content=doc_content,
            metadata_json={"table_name": table_name, "columns": col_names},
            is_allowed=t_record.is_allowed,
            catalog_version=current_version,
            embedding=doc_embedding
        )
        db.add(doc)
    
    db_record.status = "active"
    db_record.last_synced_at = datetime.utcnow()
    
    log_audit(db, tenant_id, user_id, "sync_source", f"source:{db_record.id}", correlation_id)
    db.commit()
    
    return {"status": "success", "tables_indexed": len(table_names), "last_synced_at": db_record.last_synced_at.isoformat(), "catalog_version": current_version}

class SemanticMetricRequest(BaseModel):
    name: str
    description: Optional[str] = None
    sql_expression: str

@app.post("/api/v1/catalog/metrics")
def create_metric(body: SemanticMetricRequest, request: Request, db: Session = Depends(get_db)):
    tenant_id = request.headers.get("x-tenant-id", "acme")
    user_id = request.headers.get("x-user-id", "system")
    correlation_id = request.headers.get("x-correlation-id")
    
    source = source_from_request(db, request)
    metric = SemanticMetric(
        tenant_id=tenant_id,
        source_id=source.id,
        name=body.name,
        description=body.description,
        sql_expression=body.sql_expression
    )
    db.add(metric)
    db.flush()
    
    # Store RAG Document
    doc_content = f"Metric {metric.name}: {metric.description}. Expression: {metric.sql_expression}"
    doc_embedding = embedder.encode(doc_content).tolist() if embedder else None
    
    doc = CatalogDocument(
        tenant_id=tenant_id,
        source_id=source.id,
        doc_type="metric",
        content=doc_content,
        metadata_json={"metric_id": metric.id, "name": metric.name},
        is_allowed=True, # Metrics are certified, therefore available
        embedding=doc_embedding
    )
    db.add(doc)
    
    log_audit(db, tenant_id, user_id, "create_metric", f"metric:{metric.name}", correlation_id)
    db.commit()
    return {"status": "success", "id": metric.id}

@app.get("/api/v1/catalog/metrics")
def get_metrics(request: Request, db: Session = Depends(get_db)):
    source = source_from_request(db, request)
    metrics = db.query(SemanticMetric).filter(SemanticMetric.source_id == source.id, SemanticMetric.is_active == True).all()
    return {"metrics": [{"id": m.id, "name": m.name, "description": m.description, "sql_expression": m.sql_expression} for m in metrics]}




@app.patch("/api/v1/catalog/tables/{table_id}")
def update_table_policy(table_id: int, body: PolicyUpdateRequest, request: Request, db: Session = Depends(get_db)):
    tenant_id = request.headers.get("x-tenant-id", "acme")
    user_id = request.headers.get("x-user-id", "system")
    correlation_id = request.headers.get("x-correlation-id")
    
    source = source_from_request(db, request)
    table = db.query(TableSchema).filter(TableSchema.id == table_id, TableSchema.source_id == source.id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
        
    table.is_allowed = body.is_allowed
    table.modified_by = user_id
    refresh_table_document_policy(db, table)
    
    action_str = "allow_table" if body.is_allowed else "deny_table"
    log_audit(db, tenant_id, user_id, action_str, f"table:{table.table_name}", correlation_id)
    
    db.commit()
    return {"status": "success"}

@app.patch("/api/v1/catalog/columns/{column_id}")
def update_column_policy(column_id: int, body: PolicyUpdateRequest, request: Request, db: Session = Depends(get_db)):
    tenant_id = request.headers.get("x-tenant-id", "acme")
    user_id = request.headers.get("x-user-id", "system")
    correlation_id = request.headers.get("x-correlation-id")
    
    # Needs to join to verify tenant
    source = source_from_request(db, request)
    column = db.query(ColumnSchema).join(TableSchema).filter(ColumnSchema.id == column_id, TableSchema.source_id == source.id).first()
    if not column:
        raise HTTPException(status_code=404, detail="Column not found")
        
    column.is_allowed = body.is_allowed
    column.modified_by = user_id
    refresh_table_document_policy(db, column.table)
    
    action_str = "allow_column" if body.is_allowed else "deny_column"
    log_audit(db, tenant_id, user_id, action_str, f"column:{column.column_name} (table:{column.table.table_name})", correlation_id)
    
    db.commit()
    return {"status": "success"}


@app.get("/api/v1/catalog/audit")
def get_audit_logs(request: Request, db: Session = Depends(get_db)):
    tenant_id = request.headers.get("x-tenant-id", "acme")
    audits = db.query(AdminAudit).filter(AdminAudit.tenant_id == tenant_id).order_by(AdminAudit.timestamp.desc()).limit(100).all()
    
    results = []
    for a in audits:
        results.append({
            "id": a.id,
            "user_id": a.user_id,
            "action": a.action,
            "target": a.target,
            "timestamp": a.timestamp.isoformat(),
            "correlation_id": a.correlation_id
        })
    return {"audits": results}


@app.post("/internal/catalog/search")
def search_catalog(body: SearchRequest, db: Session = Depends(get_db)):
    """Hybrid search for relevant schema and metrics documents."""
    from app.models import CatalogDocument
    from sqlalchemy import or_
    
    query_sources = db.query(DataSource).filter(DataSource.tenant_id == body.tenant_id)
    if body.source_id:
        tenant_db = query_sources.filter(DataSource.id == body.source_id).first()
    else:
        sources = query_sources.limit(2).all()
        tenant_db = sources[0] if len(sources) == 1 else None
    if not tenant_db or not tenant_db.is_allowed:
        return {"results": []}

    query_embedding = embedder.encode(body.query).tolist() if embedder else None
    
    # Simple semantic search on CatalogDocument (policy enforced via is_allowed == True)
    query = db.query(CatalogDocument).filter(
        CatalogDocument.source_id == tenant_db.id,
        CatalogDocument.is_allowed == True
    )
    
    if query_embedding:
        docs = query.order_by(CatalogDocument.embedding.cosine_distance(query_embedding)).limit(body.top_k).all()
    else:
        # Fallback lexical search
        search_term = f"%{body.query}%"
        docs = query.filter(or_(
            CatalogDocument.content.ilike(search_term),
            CatalogDocument.metadata_json.cast(String).ilike(search_term)
        )).limit(body.top_k).all()

    results = []
    for d in docs:
        results.append({
            "doc_type": d.doc_type,
            "content": d.content,
            "metadata": d.metadata_json
        })
        
    return {"results": results}

def serialize_source(db: Session, db_record: DataSource) -> dict:
    table_count = db.query(TableSchema).filter(TableSchema.source_id == db_record.id).count()
    return {
        "id": db_record.id,
        "connected": True, 
        "table_count": table_count,
        "name": db_record.name,
        "dialect": db_record.dialect,
        "status": db_record.status,
        "is_allowed": db_record.is_allowed,
        "last_synced_at": db_record.last_synced_at.isoformat() if db_record.last_synced_at else None
    }


@app.get("/api/v1/catalog/sources")
def list_sources(request: Request, db: Session = Depends(get_db)):
    """List tenant-owned source metadata without ever exposing credentials."""
    tenant_id = request.headers.get("x-tenant-id", "acme")
    sources = db.query(DataSource).filter(DataSource.tenant_id == tenant_id).order_by(DataSource.created_at.asc()).all()
    return {"sources": [serialize_source(db, source) for source in sources]}


@app.get("/api/v1/catalog/source")
def get_source_status(request: Request, db: Session = Depends(get_db)):
    """Compatibility endpoint returning the selected or only datasource."""
    try:
        return serialize_source(db, source_from_request(db, request))
    except HTTPException as exc:
        if exc.status_code == 404:
            return {"connected": False, "table_count": 0, "id": None}
        raise

@app.get("/api/v1/catalog/tables")
def get_tables(request: Request, db: Session = Depends(get_db)):
    """Get tables and columns. Filters disallowed entities based on is_admin header."""
    source = source_from_request(db, request)
    is_admin = request.headers.get("x-is-admin", "false").lower() == "true"
    
    tables = db.query(TableSchema).filter(TableSchema.source_id == source.id).all()
    
    results = []
    for t in tables:
        if not is_admin and not t.is_allowed:
            continue # Non-admins can't see denied tables
            
        cols = []
        for c in t.columns:
            if not is_admin and not c.is_allowed:
                continue
                
            col_data = {
                "id": c.id,
                "name": c.column_name, 
                "type": c.data_type, 
                "description": c.description
            }
            if is_admin:
                col_data["is_allowed"] = c.is_allowed
                col_data["last_modified_at"] = c.last_modified_at.isoformat() if c.last_modified_at else None
                col_data["modified_by"] = c.modified_by
            cols.append(col_data)
            
        table_data = {
            "id": t.id,
            "table_name": t.table_name,
            "description": t.description,
            "columns": cols
        }
        if is_admin:
            table_data["is_allowed"] = t.is_allowed
            table_data["last_modified_at"] = t.last_modified_at.isoformat() if t.last_modified_at else None
            table_data["modified_by"] = t.modified_by
            
        results.append(table_data)
        
    return {"tables": results}


@app.get("/api/v1/catalog/tables/{table_name}/preview")
def preview_table(table_name: str, request: Request, limit: int = 10, db: Session = Depends(get_db)):
    """Read a bounded preview using only currently allowed table columns."""
    source = source_from_request(db, request, active_only=True)
    table = (
        db.query(TableSchema)
        .filter(TableSchema.source_id == source.id, TableSchema.table_name == table_name,
                TableSchema.is_allowed.is_(True), TableSchema.is_available.is_(True))
        .first()
    )
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    columns = [c.column_name for c in table.columns if c.is_allowed and c.is_available]
    if not columns:
        raise HTTPException(status_code=403, detail="No columns allowed for preview")
    quote = lambda identifier: '"' + identifier.replace('"', '""') + '"'
    sql = f"SELECT {', '.join(quote(column) for column in columns)} FROM {quote(table.table_name)} LIMIT :limit"
    try:
        engine = create_engine(decrypt_secret(source.connection_string))
        with engine.connect() as connection:
            rows = connection.execute(text(sql), {"limit": min(max(limit, 1), 100)}).mappings().all()
        return {"columns": columns, "rows": [dict(row) for row in rows]}
    except Exception:
        raise HTTPException(status_code=502, detail="Data preview is unavailable")
