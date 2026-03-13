import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_issue, crud_user, crud_project
from app.schemas.issue import IssueCreate, IssueUpdate
from app.schemas.user import UserCreate
from app.schemas.project import ProjectCreate
import uuid
from datetime import datetime, timezone, timedelta

# Helper to create a user and project for issue ownership
async def create_prerequisites(db: AsyncSession):
    user_in = UserCreate(email=f"issue_owner_{uuid.uuid4()}@example.com", password="password", full_name="Issue Owner")
    user = await crud_user.create(db, obj_in=user_in)
    
    project_in = ProjectCreate(name=f"Issue Project {uuid.uuid4()}")
    project = await crud_project.create(db, obj_in=project_in, owner_id=user.id)
    
    return user, project

@pytest.mark.asyncio
async def test_create_issue(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    title = f"Test Issue {uuid.uuid4()}"
    description = "Test Description"
    issue_in = IssueCreate(title=title, description=description, project_id=project.id)
    
    issue = await crud_issue.create(db, obj_in=issue_in, owner_id=user.id)
    
    assert issue.title == title
    assert issue.description == description
    assert issue.owner_id == user.id
    assert issue.project_id == project.id
    assert issue.id is not None

@pytest.mark.asyncio
async def test_get_issue(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    issue_in = IssueCreate(title=f"Test Issue {uuid.uuid4()}", project_id=project.id)
    issue = await crud_issue.create(db, obj_in=issue_in, owner_id=user.id)
    
    issue_2 = await crud_issue.get(db, id=issue.id)
    assert issue_2 is not None
    assert issue.id == issue_2.id
    assert issue.title == issue_2.title
    assert issue_2.project is not None
    assert issue_2.assignee is None

@pytest.mark.asyncio
async def test_update_issue(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    issue_in = IssueCreate(title=f"Test Issue {uuid.uuid4()}", project_id=project.id)
    issue = await crud_issue.create(db, obj_in=issue_in, owner_id=user.id)
    
    new_title = f"Updated Issue {uuid.uuid4()}"
    new_description = "Updated Description"
    issue_update = IssueUpdate(title=new_title, description=new_description)
    
    issue_2 = await crud_issue.update(db, db_obj=issue, obj_in=issue_update)
    assert issue_2.id == issue.id
    assert issue_2.title == new_title
    assert issue_2.description == new_description

@pytest.mark.asyncio
async def test_get_multi_issues(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    title1 = f"Test Issue 1 {uuid.uuid4()}"
    title2 = f"Test Issue 2 {uuid.uuid4()}"
    
    await crud_issue.create(db, obj_in=IssueCreate(title=title1, project_id=project.id), owner_id=user.id)
    await crud_issue.create(db, obj_in=IssueCreate(title=title2, project_id=project.id), owner_id=user.id)
    
    issues = await crud_issue.get_multi(db, project_id=project.id)
    assert len(issues) >= 2
    titles = [i.title for i in issues]
    assert title1 in titles
    assert title2 in titles

@pytest.mark.asyncio
async def test_get_multi_issues_overdue(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    past_date = datetime.now(timezone.utc) - timedelta(days=2)
    future_date = datetime.now(timezone.utc) + timedelta(days=2)
    
    await crud_issue.create(db, obj_in=IssueCreate(title="Overdue Issue", due_date=past_date, project_id=project.id), owner_id=user.id)
    await crud_issue.create(db, obj_in=IssueCreate(title="Future Issue", due_date=future_date, project_id=project.id), owner_id=user.id)
    
    overdue_issues = await crud_issue.get_multi(db, project_id=project.id, overdue=True)
    assert len(overdue_issues) >= 1
    assert any(i.title == "Overdue Issue" for i in overdue_issues)
    assert not any(i.title == "Future Issue" for i in overdue_issues)

@pytest.mark.asyncio
async def test_remove_issue(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    issue_in = IssueCreate(title=f"Test Issue {uuid.uuid4()}", project_id=project.id)
    issue = await crud_issue.create(db, obj_in=issue_in, owner_id=user.id)
    
    issue_2 = await crud_issue.remove(db, id=issue.id)
    assert issue_2.id == issue.id
    
    issue_3 = await crud_issue.get(db, id=issue.id)
    assert issue_3 is None
