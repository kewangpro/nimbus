import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.crud import crud_issue, crud_user, crud_project
from app.crud import crud_issue_summary, crud_issue_link
from app.schemas.user import UserCreate
from app.schemas.project import ProjectCreate
from app.schemas.issue import IssueCreate
from app.schemas.issue_summary import IssueSummary as IssueSummarySchema
from app.models.issue_summary import IssueSummary as IssueSummaryModel

# Helper to create prerequisite entities
async def create_prerequisites(db: AsyncSession):
    user_in = UserCreate(email=f"summary_test_{uuid.uuid4()}@example.com", password="password", full_name="Summary Tester")
    user = await crud_user.create(db, obj_in=user_in)
    
    project_in = ProjectCreate(name=f"Summary Project {uuid.uuid4()}")
    project = await crud_project.create(db, obj_in=project_in, owner_id=user.id)
    
    return user, project

@pytest.mark.asyncio
async def test_issue_summary_crud_and_schema(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    # 1. Create issue
    issue_in = IssueCreate(title=f"Issue with Summary {uuid.uuid4()}", project_id=project.id)
    issue = await crud_issue.create(db, obj_in=issue_in, owner_id=user.id)
    
    # 2. Get by issue_id (should be None initially)
    summary_before = await crud_issue_summary.get_by_issue_id(db, issue_id=issue.id)
    assert summary_before is None
    
    # 3. Upsert first time (create)
    summary_text = "This is a detailed issue summary."
    next_steps_text = "1. First step\n2. Second step"
    content_hash = "abc123hash"
    
    summary_obj = await crud_issue_summary.upsert(
        db,
        issue_id=issue.id,
        summary=summary_text,
        next_steps=next_steps_text,
        content_hash=content_hash,
    )
    
    assert summary_obj.issue_id == issue.id
    assert summary_obj.summary == summary_text
    assert summary_obj.next_steps == next_steps_text
    assert summary_obj.content_hash == content_hash
    
    # 4. Get by issue_id (should find it)
    summary_after = await crud_issue_summary.get_by_issue_id(db, issue_id=issue.id)
    assert summary_after is not None
    assert summary_after.summary == summary_text
    
    # 5. Upsert second time (update)
    new_summary_text = "Updated detailed issue summary."
    new_next_steps_text = "1. Updated step"
    new_hash = "updatedhash456"
    
    summary_updated = await crud_issue_summary.upsert(
        db,
        issue_id=issue.id,
        summary=new_summary_text,
        next_steps=new_next_steps_text,
        content_hash=new_hash,
    )
    
    assert summary_updated.issue_id == issue.id
    assert summary_updated.summary == new_summary_text
    assert summary_updated.next_steps == new_next_steps_text
    assert summary_updated.content_hash == new_hash
    
    # 6. Test Pydantic Schema validation (app/schemas/issue_summary.py)
    # The database stores next_steps as a single string, but the schema converts/expects list[str]
    schema_obj = IssueSummarySchema(
        issue_id=issue.id,
        summary=new_summary_text,
        next_steps=["1. Updated step"]
    )
    assert schema_obj.issue_id == issue.id
    assert schema_obj.summary == new_summary_text
    assert schema_obj.next_steps == ["1. Updated step"]

    # Also test from_attributes behavior
    class MockDBObj:
        issue_id = issue.id
        summary = new_summary_text
        next_steps = ["Step 1", "Step 2"]
    
    validated = IssueSummarySchema.model_validate(MockDBObj())
    assert validated.issue_id == issue.id
    assert validated.next_steps == ["Step 1", "Step 2"]


@pytest.mark.asyncio
async def test_issue_dependencies_crud(db: AsyncSession) -> None:
    user, project = await create_prerequisites(db)
    
    # Create parent issue and two dependency issues
    parent_in = IssueCreate(title=f"Parent Issue {uuid.uuid4()}", project_id=project.id)
    parent = await crud_issue.create(db, obj_in=parent_in, owner_id=user.id)
    
    dep1_in = IssueCreate(title=f"Dep 1 {uuid.uuid4()}", project_id=project.id)
    dep1 = await crud_issue.create(db, obj_in=dep1_in, owner_id=user.id)
    
    dep2_in = IssueCreate(title=f"Dep 2 {uuid.uuid4()}", project_id=project.id)
    dep2 = await crud_issue.create(db, obj_in=dep2_in, owner_id=user.id)
    
    # Get dependencies initially (should be empty)
    deps_before = await crud_issue_link.get_dependencies(db, issue_id=parent.id)
    assert len(deps_before) == 0
    
    # Set dependencies to dep1 and dep2
    await crud_issue_link.set_dependencies(db, issue_id=parent.id, depends_on_ids=[dep1.id, dep2.id])
    
    # Get dependencies and assert
    deps_after = await crud_issue_link.get_dependencies(db, issue_id=parent.id)
    assert len(deps_after) == 2
    dep_ids = {d.id for d in deps_after}
    assert dep1.id in dep_ids
    assert dep2.id in dep_ids
    
    # Update/Reduce dependencies to only dep2
    await crud_issue_link.set_dependencies(db, issue_id=parent.id, depends_on_ids=[dep2.id])
    
    deps_updated = await crud_issue_link.get_dependencies(db, issue_id=parent.id)
    assert len(deps_updated) == 1
    assert deps_updated[0].id == dep2.id
    
    # Clear all dependencies
    await crud_issue_link.set_dependencies(db, issue_id=parent.id, depends_on_ids=[])
    deps_cleared = await crud_issue_link.get_dependencies(db, issue_id=parent.id)
    assert len(deps_cleared) == 0
