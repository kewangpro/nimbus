from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any, Dict
from uuid import UUID

class AuditLogCreate(BaseModel):
    user_id: Optional[UUID] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[UUID] = None
    details: Optional[Dict[str, Any]] = None

class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[UUID]
    details: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
