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
