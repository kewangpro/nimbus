import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
import json

from app.crud import crud_issue, crud_project
from app.schemas.project import ProjectCreate
from app.schemas.issue import IssueCreate

@pytest.mark.asyncio
async def test_ai_schedule_includes_today_tasks(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """Verify that tasks due today are included in the AI scheduling pool and correctly updated."""
    # 1. Setup data
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    # Create project
    p_in = ProjectCreate(name="Scheduling Balance Test")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)
    
    # Today's date (UTC)
    now = datetime.now(timezone.utc)
    
    # Issue A: Due TODAY (Should be included in rescheduling)
    issue_today = await crud_issue.create(
        db, 
        obj_in=IssueCreate(
            title="Due Today Task", 
            project_id=project.id,
            due_date=now,
            assignee_id=user.id
        ), 
        owner_id=user.id
    )
    
    # Issue B: Unscheduled (Should always be included)
    issue_unscheduled = await crud_issue.create(
        db, 
        obj_in=IssueCreate(
            title="Unscheduled Task", 
            project_id=project.id,
            due_date=None,
            assignee_id=user.id
        ), 
        owner_id=user.id
    )

    # 2. Mock AI Completion
    # Both tasks should be in the schedulable list.
    mock_response = json.dumps([
        {"index": 0, "day_number": 2},
        {"index": 1, "day_number": 3}
    ])
    
    with patch("app.core.ai.generate_completion", return_value=mock_response):
        r = await client.post(
            "/api/v1/ai/schedule", 
            headers=normal_user_token_headers
        )
        
        assert r.status_code == 200
        data = r.json()
        
        # Both tasks should now be scheduled.
        assert data["scheduled_count"] == 2
        
        await db.refresh(issue_today)
        await db.refresh(issue_unscheduled)
        
        assert issue_unscheduled.due_date is not None
        assert issue_today.due_date is not None
        # Verify they moved to different days (Day 2 and Day 3)
        assert issue_today.due_date.date() != now.date()


@pytest.mark.asyncio
async def test_ai_schedule_redistributes_far_future_tasks(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """Verify that tasks scheduled far in the future (e.g. 55 days out) are prioritized and pulled into the 10-day sprint."""
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")

    p_in = ProjectCreate(name="Far Future Test Project")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)

    now = datetime.now(timezone.utc)
    future_55_days = now + timedelta(days=55)

    issue_far_future = await crud_issue.create(
        db,
        obj_in=IssueCreate(
            title="Zelda 40th Anniversary - Outlier Task",
            project_id=project.id,
            due_date=future_55_days,
            priority="medium",
            assignee_id=user.id
        ),
        owner_id=user.id
    )

    mock_response = json.dumps([
        {"index": 0, "day_number": 5}
    ])

    with patch("app.core.ai.generate_completion", return_value=mock_response):
        r = await client.post(
            "/api/v1/ai/schedule",
            headers=normal_user_token_headers
        )

        assert r.status_code == 200
        await db.refresh(issue_far_future)

        # Verify the far-future task was rescheduled within the 10-day (~14 calendar day) sprint
        assert issue_far_future.due_date is not None
        assert issue_far_future.due_date.date() < (now + timedelta(days=16)).date()
        assert issue_far_future.due_date.date() != future_55_days.date()


@pytest.mark.asyncio
async def test_ai_schedule_deduplicates_ai_batch_response(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """Verify that duplicate index items in AI completion output do not cause double counting or inflated day counts."""
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")

    p_in = ProjectCreate(name="Deduplication Test Project")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)

    issue_single = await crud_issue.create(
        db,
        obj_in=IssueCreate(
            title="Single Deduplication Task",
            project_id=project.id,
            due_date=None,
            priority="high",
            assignee_id=user.id
        ),
        owner_id=user.id
    )

    # AI returns the same task index twice with different day suggestions
    mock_response = json.dumps([
        {"index": 0, "day_number": 1},
        {"index": 0, "day_number": 2}
    ])

    with patch("app.core.ai.generate_completion", return_value=mock_response):
        r = await client.post(
            "/api/v1/ai/schedule",
            headers=normal_user_token_headers
        )

        assert r.status_code == 200
        data = r.json()
        # Scheduled count should be exactly 1, not 2
        assert data["scheduled_count"] == 1


@pytest.mark.asyncio
async def test_ai_schedule_matches_calendar_assignee_scope(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """Calendar filters by assignee; AI Schedule must move assigned tasks even if someone else owns them."""
    from app.crud.crud_user import get_by_email
    from app.models.user import User

    user = await get_by_email(db, email="user@example.com")
    other = User(
        email="owner@example.com",
        full_name="Other Owner",
        hashed_password="hashed_password",
        is_active=True,
    )
    db.add(other)
    await db.commit()
    await db.refresh(other)

    project = await crud_project.create(db, obj_in=ProjectCreate(name="Assignee Scope Project"), owner_id=other.id)
    now = datetime.now(timezone.utc)
    future_55_days = now + timedelta(days=55)

    assigned_to_me = await crud_issue.create(
        db,
        obj_in=IssueCreate(
            title="Assigned to me, owned by other",
            project_id=project.id,
            due_date=future_55_days,
            assignee_id=user.id,
        ),
        owner_id=other.id,
    )
    owned_unassigned = await crud_issue.create(
        db,
        obj_in=IssueCreate(
            title="Owned by me, unassigned",
            project_id=project.id,
            due_date=future_55_days,
            assignee_id=None,
        ),
        owner_id=user.id,
    )

    mock_response = json.dumps([{"index": 0, "day_number": 3}])
    with patch("app.core.ai.generate_completion", return_value=mock_response):
        r = await client.post("/api/v1/ai/schedule", headers=normal_user_token_headers)

    assert r.status_code == 200
    await db.refresh(assigned_to_me)
    await db.refresh(owned_unassigned)

    assert assigned_to_me.due_date.date() != future_55_days.date()
    assert assigned_to_me.due_date.date() < (now + timedelta(days=16)).date()
    assert owned_unassigned.due_date.date() == future_55_days.date()


@pytest.mark.asyncio
async def test_ai_schedule_no_schedulable_issues(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """When user has no open tasks needing scheduling, return early with count 0 and status done."""
    from app.crud.crud_user import get_by_email
    from app.models.issue import IssueStatus
    user = await get_by_email(db, email="user@example.com")

    p_in = ProjectCreate(name="No Tasks Project")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)

    # Completed task should be ignored
    await crud_issue.create(
        db,
        obj_in=IssueCreate(
            title="Done Task",
            project_id=project.id,
            status=IssueStatus.DONE,
            due_date=datetime.now(timezone.utc),
            assignee_id=user.id,
        ),
        owner_id=user.id,
    )

    r = await client.post("/api/v1/ai/schedule", headers=normal_user_token_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["scheduled_count"] == 0
    assert "No issues require rescheduling" in data["message"]

    progress_res = await client.get("/api/v1/ai/schedule/progress", headers=normal_user_token_headers)
    assert progress_res.status_code == 200
    progress_data = progress_res.json()
    assert progress_data["status"] == "done"
    assert progress_data["total"] == 0


@pytest.mark.asyncio
async def test_ai_schedule_round_robin_fallback_on_incomplete_ai_response(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """If the AI skips tasks or returns empty response, the 100% coverage fallback round-robins all tasks."""
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")

    p_in = ProjectCreate(name="Incomplete AI Response Project")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)

    task1 = await crud_issue.create(
        db,
        obj_in=IssueCreate(title="Task 1", project_id=project.id, due_date=None, assignee_id=user.id),
        owner_id=user.id,
    )
    task2 = await crud_issue.create(
        db,
        obj_in=IssueCreate(title="Task 2", project_id=project.id, due_date=None, assignee_id=user.id),
        owner_id=user.id,
    )

    # AI returns empty response []
    with patch("app.core.ai.generate_completion", return_value="[]"):
        r = await client.post("/api/v1/ai/schedule", headers=normal_user_token_headers)

    assert r.status_code == 200
    data = r.json()
    assert data["scheduled_count"] == 2

    await db.refresh(task1)
    await db.refresh(task2)
    assert task1.due_date is not None
    assert task2.due_date is not None


@pytest.mark.asyncio
async def test_ai_schedule_overloaded_day_safety_override(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """When the AI tries to dump all tasks onto the same day, the safety layer redistributes to least busy days."""
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")

    p_in = ProjectCreate(name="Overloaded Day Safety Project")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)

    tasks = []
    for i in range(5):
        t = await crud_issue.create(
            db,
            obj_in=IssueCreate(title=f"Bulk Task {i}", project_id=project.id, due_date=None, assignee_id=user.id),
            owner_id=user.id,
        )
        tasks.append(t)

    # AI suggests Day 1 for all 5 tasks
    all_day_1 = json.dumps([{"index": i, "day_number": 1} for i in range(5)])

    with patch("app.core.ai.generate_completion", return_value=all_day_1):
        r = await client.post("/api/v1/ai/schedule", headers=normal_user_token_headers)

    assert r.status_code == 200
    for t in tasks:
        await db.refresh(t)

    assigned_days = {t.due_date.date() for t in tasks}
    # Safety override ensures tasks are spread across more than 1 day
    assert len(assigned_days) > 1
