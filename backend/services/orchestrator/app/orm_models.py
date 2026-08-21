import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.orm import relationship

try:
    from app.database import Base
except ImportError:
    from backend.services.orchestrator.app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    source_id = Column(String, index=True, nullable=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    runs = relationship("Run", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # 'user' or 'assistant'
    content = Column(String, nullable=False)
    payload = Column(JSON, nullable=True) # To store semantic_plan, data_result, etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")

class Run(Base):
    __tablename__ = "runs"

    id = Column(String, primary_key=True, default=generate_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    tenant_id = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    source_id = Column(String, index=True, nullable=True)
    status = Column(String, nullable=False)
    stage = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    retry_reason = Column(String, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    worker_id = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_heartbeat_at = Column(DateTime, nullable=True)
    final_message_id = Column(String, ForeignKey("messages.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="runs")

class Dashboard(Base):
    __tablename__ = "dashboards"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    owner_user_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    visibility = Column(String, nullable=False, default="private") # 'private' or 'tenant_viewers'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship("DashboardItem", back_populates="dashboard", cascade="all, delete-orphan", order_by="DashboardItem.order")

class DashboardItem(Base):
    __tablename__ = "dashboard_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    dashboard_id = Column(String, ForeignKey("dashboards.id"), nullable=False)
    source_message_id = Column(String, nullable=True) # Message containing the chart spec / data
    title = Column(String, nullable=False)
    order = Column(Integer, nullable=False, default=0)
    display_config = Column(JSON, nullable=True) # E.g., width, height, type override
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    dashboard = relationship("Dashboard", back_populates="items")

class ExportAudit(Base):
    __tablename__ = "export_audits"

    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, index=True, nullable=False)
    user_id = Column(String, index=True, nullable=False)
    source_message_id = Column(String, nullable=False)
    format = Column(String, nullable=False) # e.g. 'csv'
    row_count = Column(Integer, nullable=True)
    status = Column(String, nullable=False) # 'success', 'denied', 'error'
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
