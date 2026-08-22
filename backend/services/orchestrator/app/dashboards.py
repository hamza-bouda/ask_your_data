import io
import csv
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.orm_models import Dashboard, DashboardItem, ExportAudit, Message
import structlog
from prometheus_client import Counter

logger = structlog.get_logger("orchestrator")

CSV_EXPORTS_TOTAL = Counter("csv_exports_total", "Total CSV exports requested", ["status", "format"])
DASHBOARDS_CREATED_TOTAL = Counter("dashboards_created_total", "Total dashboards created")

router = APIRouter()
VALID_VISIBILITIES = {"private", "tenant_viewers"}

# --- Pydantic Models ---

class DashboardItemCreate(BaseModel):
    source_message_id: str
    title: str
    description: Optional[str] = None
    notes: Optional[str] = None
    order: int = 0
    display_config: Optional[dict] = None

class DashboardCreate(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: str = "private"
    archived: bool = False
    filters: Optional[dict] = {}
    items: Optional[List[DashboardItemCreate]] = []

class DashboardUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visibility: Optional[str] = None
    archived: Optional[bool] = None
    filters: Optional[dict] = None

class DashboardItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    order: Optional[int] = None
    display_config: Optional[dict] = None

# --- Helpers ---

def verify_dashboard_access(dashboard: Dashboard, tenant_id: str, user_id: str, is_admin: bool):
    if dashboard.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    if dashboard.visibility == "private" and dashboard.owner_user_id != user_id:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    # For tenant_viewers, anyone in the tenant can view

def verify_dashboard_modify(dashboard: Dashboard, tenant_id: str, user_id: str, is_admin: bool):
    verify_dashboard_access(dashboard, tenant_id, user_id, is_admin)
    if dashboard.owner_user_id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Forbidden: You can only modify your own dashboards")

# --- Dashboard Endpoints ---

@router.post("/internal/dashboards")
def create_dashboard(
    body: DashboardCreate,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    db: Session = Depends(get_db)
):
    if body.visibility not in VALID_VISIBILITIES:
        raise HTTPException(status_code=422, detail="Invalid dashboard visibility")
    dashboard = Dashboard(
        tenant_id=tenant_id,
        owner_user_id=user_id,
        name=body.name,
        description=body.description,
        visibility=body.visibility,
        archived=body.archived,
        filters=body.filters or {}
    )
    db.add(dashboard)
    db.flush()

    for item in body.items:
        msg = db.query(Message).filter(Message.id == item.source_message_id).first()
        payload_snapshot = None
        if msg:
            payload_snapshot = {
                "results": (msg.payload or {}).get("results"),
                "chart_spec": (msg.payload or {}).get("chart_spec"),
                "sql_query": (msg.payload or {}).get("sql_query"),
                "semantic_context": (msg.payload or {}).get("semantic_plan"),
                "execution_date": msg.created_at.isoformat() if msg.created_at else None,
                "source_id": msg.conversation.source_id
            }

        db_item = DashboardItem(
            dashboard_id=dashboard.id,
            source_message_id=item.source_message_id,
            title=item.title,
            description=item.description,
            notes=item.notes,
            order=item.order,
            display_config=item.display_config,
            payload_snapshot=payload_snapshot
        )
        db.add(db_item)
    
    db.commit()
    DASHBOARDS_CREATED_TOTAL.inc()
    return {"id": dashboard.id, "status": "created"}

@router.get("/internal/dashboards")
def list_dashboards(
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    include_archived: bool = Query(False),
    db: Session = Depends(get_db)
):
    query = db.query(Dashboard).filter(Dashboard.tenant_id == tenant_id)
    if not include_archived:
        query = query.filter(Dashboard.archived == False)
    
    dashboards = query.all()
    # Filter by visibility
    result = []
    for d in dashboards:
        if d.owner_user_id == user_id or d.visibility == "tenant_viewers":
            result.append({
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "visibility": d.visibility,
                "archived": d.archived,
                "filters": d.filters,
                "owner_user_id": d.owner_user_id,
                "created_at": d.created_at,
                "last_refreshed_at": d.last_refreshed_at
            })
    return result

@router.get("/internal/dashboards/{dashboard_id}")
def get_dashboard(
    dashboard_id: str,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    is_admin: bool = Query(False),
    source_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    verify_dashboard_access(dashboard, tenant_id, user_id, is_admin)

    items = db.query(DashboardItem).filter(DashboardItem.dashboard_id == dashboard_id).order_by(DashboardItem.order).all()
    items_data = []
    for item in items:
        # Prioritize payload snapshot
        payload = item.payload_snapshot or {}
        
        # Fallback to message payload for older items
        if not payload:
            msg = db.query(Message).filter(Message.id == item.source_message_id).first()
            if msg:
                payload = msg.payload or {}
                payload["source_id"] = msg.conversation.source_id
                payload["execution_date"] = msg.created_at.isoformat() if msg.created_at else None
                payload["semantic_context"] = payload.get("semantic_plan")
        
        # Enforce source isolation if a specific source_id is requested
        item_source_id = payload.get("source_id")
        if item_source_id and source_id and item_source_id != source_id:
            continue
            
        items_data.append({
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "notes": item.notes,
            "order": item.order,
            "display_config": item.display_config,
            "source_message_id": item.source_message_id,
            "results": payload.get("results"),
            "chart_spec": payload.get("chart_spec"),
            "sql_query": payload.get("sql_query"),
            "source_id": item_source_id,
            "execution_date": payload.get("execution_date"),
            "semantic_context": payload.get("semantic_context")
        })

    return {
        "id": dashboard.id,
        "name": dashboard.name,
        "description": dashboard.description,
        "visibility": dashboard.visibility,
        "archived": dashboard.archived,
        "filters": dashboard.filters,
        "owner_user_id": dashboard.owner_user_id,
        "created_at": dashboard.created_at,
        "last_refreshed_at": dashboard.last_refreshed_at,
        "items": items_data
    }

@router.patch("/internal/dashboards/{dashboard_id}")
def update_dashboard(
    dashboard_id: str,
    body: DashboardUpdate,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    is_admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    verify_dashboard_modify(dashboard, tenant_id, user_id, is_admin)

    if body.name is not None:
        dashboard.name = body.name
    if body.description is not None:
        dashboard.description = body.description
    if body.visibility is not None:
        if body.visibility not in VALID_VISIBILITIES:
            raise HTTPException(status_code=422, detail="Invalid dashboard visibility")
        dashboard.visibility = body.visibility
    if body.archived is not None:
        dashboard.archived = body.archived
    if body.filters is not None:
        dashboard.filters = body.filters
        
    db.commit()
    return {"status": "updated"}

@router.post("/internal/dashboards/{dashboard_id}/duplicate")
def duplicate_dashboard(
    dashboard_id: str,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    is_admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    verify_dashboard_access(dashboard, tenant_id, user_id, is_admin)

    new_dashboard = Dashboard(
        tenant_id=tenant_id,
        owner_user_id=user_id,
        name=f"Copie de {dashboard.name}",
        description=dashboard.description,
        visibility="private", # copies are private by default
        archived=False,
        filters=dashboard.filters
    )
    db.add(new_dashboard)
    db.flush()

    items = db.query(DashboardItem).filter(DashboardItem.dashboard_id == dashboard_id).all()
    for item in items:
        new_item = DashboardItem(
            dashboard_id=new_dashboard.id,
            source_message_id=item.source_message_id,
            title=item.title,
            description=item.description,
            notes=item.notes,
            order=item.order,
            display_config=item.display_config,
            payload_snapshot=item.payload_snapshot
        )
        db.add(new_item)
        
    db.commit()
    DASHBOARDS_CREATED_TOTAL.inc()
    return {"id": new_dashboard.id, "status": "duplicated"}


@router.delete("/internal/dashboards/{dashboard_id}")
def delete_dashboard(
    dashboard_id: str,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    is_admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        return {"status": "ok"} # idempotent
    
    verify_dashboard_modify(dashboard, tenant_id, user_id, is_admin)
    db.delete(dashboard)
    db.commit()
    return {"status": "deleted"}

@router.post("/internal/dashboards/{dashboard_id}/items")
def add_dashboard_item(
    dashboard_id: str,
    body: DashboardItemCreate,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    is_admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    verify_dashboard_modify(dashboard, tenant_id, user_id, is_admin)
    
    msg = db.query(Message).filter(Message.id == body.source_message_id).first()
    if not msg or msg.conversation.tenant_id != tenant_id:
        raise HTTPException(status_code=400, detail="Invalid source message")

    duplicate = db.query(DashboardItem).filter(
        DashboardItem.dashboard_id == dashboard.id,
        DashboardItem.source_message_id == body.source_message_id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This result is already saved in the dashboard")

    payload_snapshot = {
        "results": (msg.payload or {}).get("results"),
        "chart_spec": (msg.payload or {}).get("chart_spec"),
        "sql_query": (msg.payload or {}).get("sql_query"),
        "semantic_context": (msg.payload or {}).get("semantic_plan"),
        "execution_date": msg.created_at.isoformat() if msg.created_at else None,
        "source_id": msg.conversation.source_id
    }

    item = DashboardItem(
        dashboard_id=dashboard.id,
        source_message_id=body.source_message_id,
        title=body.title,
        description=body.description,
        notes=body.notes,
        order=body.order,
        display_config=body.display_config,
        payload_snapshot=payload_snapshot
    )
    db.add(item)
    db.commit()
    return {"id": item.id, "status": "created"}

@router.patch("/internal/dashboards/{dashboard_id}/items/{item_id}")
def update_dashboard_item(
    dashboard_id: str,
    item_id: str,
    body: DashboardItemUpdate,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    is_admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
        
    verify_dashboard_modify(dashboard, tenant_id, user_id, is_admin)
    
    item = db.query(DashboardItem).filter(DashboardItem.id == item_id, DashboardItem.dashboard_id == dashboard_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Dashboard item not found")

    if body.title is not None:
        item.title = body.title
    if body.description is not None:
        item.description = body.description
    if body.notes is not None:
        item.notes = body.notes
    if body.order is not None:
        item.order = body.order
    if body.display_config is not None:
        item.display_config = body.display_config
        
    db.commit()
    return {"status": "updated"}

@router.delete("/internal/dashboards/{dashboard_id}/items/{item_id}")
def delete_dashboard_item(
    dashboard_id: str,
    item_id: str,
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    is_admin: bool = Query(False),
    db: Session = Depends(get_db)
):
    dashboard = db.query(Dashboard).filter(Dashboard.id == dashboard_id).first()
    if not dashboard:
        raise HTTPException(status_code=404, detail="Dashboard not found")
        
    verify_dashboard_modify(dashboard, tenant_id, user_id, is_admin)
    
    item = db.query(DashboardItem).filter(DashboardItem.id == item_id, DashboardItem.dashboard_id == dashboard_id).first()
    if item:
        db.delete(item)
        db.commit()
    return {"status": "deleted"}

# --- Export Endpoint ---

def sanitize_csv_cell(value):
    if value is None:
        return ""
    val_str = str(value)
    if val_str.startswith(("=", "+", "-", "@")):
        return "'" + val_str
    return val_str

@router.get("/internal/results/{message_id}/export")
def export_results(
    message_id: str,
    format: str = Query("csv"),
    tenant_id: str = Query(...),
    user_id: str = Query(...),
    source_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    if format != "csv":
        raise HTTPException(status_code=400, detail="Unsupported format")
        
    msg = db.query(Message).filter(Message.id == message_id).first()
    
    is_forbidden = not msg or msg.conversation.tenant_id != tenant_id
    if msg and source_id and msg.conversation.source_id != source_id:
        is_forbidden = True
        
    if is_forbidden:
        audit = ExportAudit(tenant_id=tenant_id, user_id=user_id, source_message_id=message_id, format=format, status="denied")
        db.add(audit)
        db.commit()
        CSV_EXPORTS_TOTAL.labels(status="denied", format=format).inc()
        raise HTTPException(status_code=404, detail="Result not found or forbidden")
        
    payload = msg.payload or {}
    results = payload.get("results", [])
    
    if not results or not isinstance(results, list):
        raise HTTPException(status_code=400, detail="No tabular results available for export")
        
    # Apply limit
    MAX_ROWS = 10000
    if len(results) > MAX_ROWS:
        results = results[:MAX_ROWS]
        
    # Generate CSV
    output = io.StringIO()
    if len(results) > 0:
        # we assume results is a list of dicts
        fieldnames = results[0].keys()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            sanitized_row = {k: sanitize_csv_cell(v) for k, v in row.items()}
            writer.writerow(sanitized_row)
            
    audit = ExportAudit(tenant_id=tenant_id, user_id=user_id, source_message_id=message_id, format=format, status="success", row_count=len(results))
    db.add(audit)
    db.commit()
    CSV_EXPORTS_TOTAL.labels(status="success", format=format).inc()

    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename=export_{message_id}.csv"
    return response

@router.get("/internal/audit/export")
def get_export_audits(
    tenant_id: str = Query(...),
    db: Session = Depends(get_db)
):
    audits = db.query(ExportAudit).filter(ExportAudit.tenant_id == tenant_id).order_by(ExportAudit.timestamp.desc()).limit(100).all()
    results = []
    for a in audits:
        results.append({
            "id": a.id,
            "timestamp": a.timestamp,
            "user_id": a.user_id,
            "source_message_id": a.source_message_id,
            "format": a.format,
            "status": a.status,
            "row_count": a.row_count
        })
    return {"audits": results}
