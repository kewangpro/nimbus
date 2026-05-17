import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
import json
import uuid

from app.crud import crud_issue, crud_project
from app.schemas.project import ProjectCreate
from app.schemas.issue import IssueCreate, IssuePriority, IssueStatus

@pytest.mark.asyncio
async def test_ai_schedule_endpoint(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    # 1. Setup data
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    # Create project
    p_in = ProjectCreate(name="AI Schedule Test Project")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)
    
    now = datetime.now(timezone.utc)
    
    # Issue A: Overdue
    issue_overdue = await crud_issue.create(
        db, 
        obj_in=IssueCreate(
            title="Overdue Task", 
            project_id=project.id,
            due_date=now - timedelta(days=5),
            assignee_id=user.id
        ), 
        owner_id=user.id
    )
    
    # Issue B: Far Future (240 days)
    issue_future = await crud_issue.create(
        db, 
        obj_in=IssueCreate(
            title="Far Future Task", 
            project_id=project.id,
            due_date=now + timedelta(days=240),
            assignee_id=user.id
        ), 
        owner_id=user.id
    )
    
    # Issue C: Unscheduled
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
    
    # Issue D: Already scheduled in window (should be skipped)
    issue_in_window = await crud_issue.create(
        db, 
        obj_in=IssueCreate(
            title="In Window Task", 
            project_id=project.id,
            due_date=now + timedelta(days=2),
            assignee_id=user.id
        ), 
        owner_id=user.id
    )

    # 2. Mock AI Completion
    # Compute the next 3 weekdays dynamically so the dates stay within allowed_dates.
    def _next_weekdays(n: int) -> list:
        days = []
        d = datetime.now(timezone.utc).date() + timedelta(days=1)
        while len(days) < n:
            if d.weekday() < 5:
                days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return days

    wd1, wd2, wd3 = _next_weekdays(3)
    mock_response = json.dumps([
        {"id": str(issue_overdue.id), "date": wd1},
        {"id": str(issue_future.id), "date": wd2},
        {"id": str(issue_unscheduled.id), "date": wd3}
    ])
    
    with patch("app.core.ai.generate_completion", return_value=mock_response):
        r = await client.post(
            "/api/v1/ai/schedule", 
            headers=normal_user_token_headers
        )
        
        assert r.status_code == 200
        data = r.json()
        # If it returns 2 instead of 3, it might be because one date was considered 'today' 
        # and skipped or something. But these are all in the future.
        assert data["scheduled_count"] == 3
        
        # Verify changes in DB
        await db.refresh(issue_overdue)
        await db.refresh(issue_future)
        await db.refresh(issue_unscheduled)
        await db.refresh(issue_in_window)
        
        # Overdue should now have a future date
        assert issue_overdue.due_date is not None
        # Future task (240 days) should now be rescheduled into the next few days
        assert issue_future.due_date is not None
        future_due = issue_future.due_date.replace(tzinfo=None) if issue_future.due_date.tzinfo else issue_future.due_date
        assert future_due < (now + timedelta(days=10)).replace(tzinfo=None)
        # Unscheduled task should now have a date
        assert issue_unscheduled.due_date is not None
        # In-window task should be UNCHANGED (approx check due to timezone handling)
        assert issue_in_window.due_date.day == (now + timedelta(days=2)).day

@pytest.mark.asyncio
async def test_ai_plan_endpoint(
    client: AsyncClient, normal_user_token_headers: dict
) -> None:
    mock_response = json.dumps([
        {
            "title": "New Task 1",
            "description": "Desc 1",
            "priority": "HIGH",
            "status": "TODO",
            "due_date": "2026-06-01"
        }
    ])
    
    with patch("app.core.ai.generate_completion", return_value=mock_response):
        r = await client.post(
            "/api/v1/ai/plan", 
            headers=normal_user_token_headers,
            json={"text": "Build a rocket"}
        )
        
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["title"] == "New Task 1"
        assert data[0]["priority"].upper() == "HIGH"
