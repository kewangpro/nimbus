from typing import Optional
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.models.issue import IssueStatus, IssuePriority

class IssueBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[IssueStatus] = IssueStatus.TODO
    priority: Optional[IssuePriority] = IssuePriority.MEDIUM
    assignee_id: Optional[UUID] = None
    due_date: Optional[datetime] = None

class IssueCreate(IssueBase):
    pass

class IssueUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[IssueStatus] = None
    priority: Optional[IssuePriority] = None
    assignee_id: Optional[UUID] = None
    due_date: Optional[datetime] = None

class IssueInDBBase(IssueBase):
    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Issue(IssueInDBBase):
    pass
