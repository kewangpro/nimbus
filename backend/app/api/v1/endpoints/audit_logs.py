from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.db.session import get_db
from app.api import deps
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.crud import crud_audit
from sqlalchemy import select, func
from app.models.audit_log import AuditLog

router = APIRouter()

@router.get("/", response_model=List[AuditLogResponse])
async def read_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """
    Retrieve audit logs.
    """
    logs = await crud_audit.get_audit_logs(db, skip=skip, limit=limit)
    return logs

@router.get("/stats")
async def get_audit_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Get audit log statistics (e.g., action counts).
    """
    stmt = select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)
    result = await db.execute(stmt)
    counts = result.all()
    
    stats = {
        "action_counts": {row[0]: row[1] for row in counts}
    }
    return stats
