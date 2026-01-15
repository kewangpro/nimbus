from typing import Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.models.issue import IssueStatus, IssuePriority
from app.schemas.project import Project

class IssueBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[IssueStatus] = IssueStatus.TODO
    priority: Optional[IssuePriority] = IssuePriority.MEDIUM
    assignee_id: Optional[UUID] = None
    due_date: Optional[datetime] = None

class IssueCreate(IssueBase):
    project_id: Optional[UUID] = None # Optional for API, default handled by backend if missing

class IssueUpdate(IssueBase):
    title: Optional[str] = None
    status: Optional[IssueStatus] = None
    priority: Optional[IssuePriority] = None
    project_id: Optional[UUID] = None

class IssueInDBBase(IssueBase):
    id: UUID
    owner_id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Issue(IssueInDBBase):
    project: Optional[Project] = None
