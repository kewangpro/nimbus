from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.db.session import get_db
from app.api import deps
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse
from app.crud import crud_audit
from sqlalchemy import select, func, and_, cast
from sqlalchemy.dialects.postgresql import JSONB
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
    # Query 1: Regular action counts
    stmt = select(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action)
    result = await db.execute(stmt)
    counts = result.all()
    
    action_counts = {row[0]: row[1] for row in counts}

    # Query 2: Specifically count AI Scheduler updates
    # We use a dialect-aware query to handle JSONB vs JSON differences
    is_postgres = db.bind.dialect.name == "postgresql"
    
    if is_postgres:
        ai_stmt = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.action == "issue.update",
                cast(AuditLog.details, JSONB)["via"].astext == "ai_scheduler"
            )
        )
    else:
        ai_stmt = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.action == "issue.update",
                AuditLog.details["via"] == "ai_scheduler"
            )
        )
    
    ai_result = await db.execute(ai_stmt)
    ai_count = ai_result.scalar() or 0

    if ai_count > 0:
        # Subtract from regular issue.update and add virtual "ai_schedule" action
        if "issue.update" in action_counts:
            action_counts["issue.update"] -= ai_count
            if action_counts["issue.update"] <= 0:
                del action_counts["issue.update"]
        
        action_counts["ai_schedule"] = ai_count

    stats = {
        "action_counts": action_counts
    }
    return stats
