from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_issue, crud_issue_link, crud_audit
from app.schemas.issue import Issue, IssueCreate, IssueUpdate, IssueStatus, IssuePriority
from app.models.user import User
from app.core.socket import manager
from app.core import jobs
import json

router = APIRouter()

@router.post("/backfill", response_model=dict)
async def backfill_embeddings(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Backfill embeddings for all issues.
    """
    job_id = await jobs.enqueue_job(jobs.JOB_BACKFILL_EMBEDDINGS, {"requested_by": str(current_user.id)})
    await crud_audit.log_action(db, "issue.backfill", current_user.id, "issue", None, details={"job_id": job_id})
    return {"message": "Backfill job queued", "job_id": job_id}

@router.get("/", response_model=List[Issue])
async def read_issues(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    project_id: Optional[UUID] = None,
    assignee_id: Optional[UUID] = None,
    status: Optional[IssueStatus] = None,
    priority: Optional[IssuePriority] = None,
    overdue: Optional[bool] = None,
    unscheduled: Optional[bool] = None,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve issues.
    """
    owner_id = None
    if current_user.role == "client":
        owner_id = current_user.id
        
    issues = await crud_issue.get_multi(
        db,
        skip=skip,
        limit=limit,
        owner_id=owner_id,
        project_id=project_id,
        assignee_id=assignee_id,
        status=status.value if status else None,
        priority=priority.value if priority else None,
        overdue=overdue,
        unscheduled=unscheduled,
    )
    return issues

@router.post("/", response_model=Issue)
async def create_issue(
    *,
    db: AsyncSession = Depends(deps.get_db),
    issue_in: IssueCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new issue.
    """
    issue = await crud_issue.create(db=db, obj_in=issue_in, owner_id=current_user.id)
    await crud_audit.log_action(
        db, 
        "issue.create", 
        current_user.id, 
        "issue", 
        issue.id,
        details={"title": issue.title}
    )
    await manager.broadcast(json.dumps({"type": "ISSUE_CREATED", "data": str(issue.id)}))
    return issue

@router.get("/{id}", response_model=Issue)
async def read_issue(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get issue by ID.
    """
    issue = await crud_issue.get(db=db, id=id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue

@router.patch("/{id}", response_model=Issue)
async def update_issue(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    issue_in: IssueUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update an issue.
    """
    issue = await crud_issue.get(db=db, id=id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Track changes
    old_data = {
        "title": issue.title,
        "status": issue.status,
        "priority": issue.priority,
        "assignee_id": issue.assignee_id,
        "project_id": issue.project_id,
        "due_date": issue.due_date,
    }
    
    issue = await crud_issue.update(db=db, db_obj=issue, obj_in=issue_in)
    
    changes = []
    for field, old_val in old_data.items():
        new_val = getattr(issue, field)
        if old_val != new_val:
            changes.append(field)

    await crud_audit.log_action(
        db, 
        "issue.update", 
        current_user.id, 
        "issue", 
        issue.id,
        details={"title": issue.title, "changes": changes}
    )
    await manager.broadcast(json.dumps({"type": "ISSUE_UPDATED", "data": str(issue.id)}))
    return issue

@router.delete("/{id}", response_model=Issue)
async def delete_issue(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete an issue.
    """
    issue = await crud_issue.get(db=db, id=id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    issue_title = issue.title
    issue = await crud_issue.remove(db=db, id=id)
    await crud_audit.log_action(
        db, 
        "issue.delete", 
        current_user.id, 
        "issue", 
        issue.id,
        details={"title": issue_title}
    )
    await manager.broadcast(json.dumps({"type": "ISSUE_DELETED", "data": str(id)}))
    return issue

@router.get("/{id}/dependencies", response_model=List[Issue])
async def get_issue_dependencies(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    issue = await crud_issue.get(db=db, id=id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if current_user.role == "client" and issue.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    deps_issues = await crud_issue_link.get_dependencies(db, id)
    return deps_issues
