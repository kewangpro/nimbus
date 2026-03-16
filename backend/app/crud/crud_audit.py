from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.audit_log import AuditLog
from typing import Any, Dict, List, Optional
import uuid

async def log_action(
    db: AsyncSession,
    action: str,
    user_id: Optional[uuid.UUID] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Helper to consistently log user or system actions."""
    db_obj = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {}
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_audit_logs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
) -> List[AuditLog]:
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
