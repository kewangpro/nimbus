from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_issue
from app.schemas.issue import Issue, IssueCreate, IssueUpdate
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
    return {"message": "Backfill job queued", "job_id": job_id}

@router.get("/", response_model=List[Issue])
async def read_issues(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    project_id: Optional[UUID] = None,
    assignee_id: Optional[UUID] = None,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve issues.
    """
    owner_id = None
    if current_user.role == "client":
        owner_id = current_user.id
        
    issues = await crud_issue.get_multi(db, skip=skip, limit=limit, owner_id=owner_id, project_id=project_id, assignee_id=assignee_id)
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
    issue = await crud_issue.update(db=db, db_obj=issue, obj_in=issue_in)
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
    issue = await crud_issue.remove(db=db, id=id)
    await manager.broadcast(json.dumps({"type": "ISSUE_DELETED", "data": str(id)}))
    return issue
