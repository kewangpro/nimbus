from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.db.base import Base
import uuid

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True) # Nullable for system actions if any
    action = Column(String, index=True, nullable=False)
    entity_type = Column(String, index=True, nullable=True)
    entity_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    details = Column(JSON().with_variant(JSON, "sqlite"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
