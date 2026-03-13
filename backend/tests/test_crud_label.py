import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_label, crud_issue, crud_user, crud_project
from app.schemas.issue import IssueCreate
from app.schemas.user import UserCreate
from app.schemas.project import ProjectCreate
import uuid

@pytest.mark.asyncio
async def test_get_or_create_label(db: AsyncSession) -> None:
    label_name = f"TestLabel_{uuid.uuid4()}"
    
    # Create
    label1 = await crud_label.get_or_create(db, label_name)
    assert label1 is not None
    assert label1.name == label_name.lower()
    
    # Get existing
    label2 = await crud_label.get_or_create(db, label_name)
    assert label2.id == label1.id

@pytest.mark.asyncio
async def test_get_by_name(db: AsyncSession) -> None:
    label_name = f"FetchLabel_{uuid.uuid4()}"
    
    label_not_found = await crud_label.get_by_name(db, label_name)
    assert label_not_found is None
    
    label_created = await crud_label.get_or_create(db, label_name)
    label_found = await crud_label.get_by_name(db, label_name)
    assert label_found is not None
    assert label_found.id == label_created.id
    
    # Test case insensitivity
    label_upper = await crud_label.get_by_name(db, label_name.upper())
    assert label_upper is not None
    assert label_upper.id == label_created.id

@pytest.mark.asyncio
async def test_set_issue_labels(db: AsyncSession) -> None:
    # Set up issue
    user = await crud_user.create(db, obj_in=UserCreate(email=f"label_{uuid.uuid4()}@example.com", password="pw", full_name="Label"))
    project = await crud_project.create(db, obj_in=ProjectCreate(name=f"Proj_{uuid.uuid4()}"), owner_id=user.id)
    issue = await crud_issue.create(db, obj_in=IssueCreate(title="Test Issue", project_id=project.id), owner_id=user.id)
    
    labels_in = ["Bug", "Urgent", "bug", " "] # Includes duplicates and empty after strip
    await crud_label.set_issue_labels(db, issue.id, labels_in)
    
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.issue import Issue
    res = await db.execute(select(Issue).options(selectinload(Issue.labels)).where(Issue.id == issue.id))
    issue_fetched = res.scalars().first()
    
    assert issue_fetched is not None
    assert len(issue_fetched.labels) == 2
    label_names = [l.name for l in issue_fetched.labels]
    assert "bug" in label_names
    assert "urgent" in label_names
    
    # Test setting empty labels
    await crud_label.set_issue_labels(db, issue.id, [])
    res = await db.execute(select(Issue).options(selectinload(Issue.labels)).where(Issue.id == issue.id))
    issue_empty = res.scalars().first()
    assert len(issue_empty.labels) == 0


@pytest.mark.asyncio
async def test_set_issue_labels_not_found(db: AsyncSession) -> None:
    issue_not_found = await crud_label.set_issue_labels(db, uuid.uuid4(), ["Bug"])
    assert issue_not_found is None
