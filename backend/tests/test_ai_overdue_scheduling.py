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
async def test_ai_schedule_skips_overdue_tasks(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    """Verify that overdue tasks are NOT included in the AI scheduling pool."""
    # 1. Setup data
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    # Create project
    p_in = ProjectCreate(name="Overdue Test Project")
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)
    
    # Yesterday's date (UTC)
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    # Ensure it's clearly yesterday by setting to midnight
    yesterday = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)
    
    # Issue: Overdue (Yesterday)
    issue_overdue = await crud_issue.create(
        db, 
        obj_in=IssueCreate(
            title="Overdue Task", 
            project_id=project.id,
            due_date=yesterday,
            assignee_id=user.id
        ), 
        owner_id=user.id
    )
    
    # Issue: Unscheduled
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
    # Since overdue is excluded, only the unscheduled task should be passed to AI.
    mock_response = json.dumps([
        {"index": 0, "day_number": 1}
    ])
    
    with patch("app.core.ai.generate_completion", return_value=mock_response) as mock_ai:
        r = await client.post(
            "/api/v1/ai/schedule", 
            headers=normal_user_token_headers
        )
        
        assert r.status_code == 200
        
        await db.refresh(issue_overdue)
        await db.refresh(issue_unscheduled)
        
        # Verify overdue task was NOT moved
        assert issue_overdue.due_date.date() == yesterday.date(), "Overdue task should not have been rescheduled"
        
        # Verify unscheduled task WAS moved
        assert issue_unscheduled.due_date is not None, "Unscheduled task should have been rescheduled"
        
        # Verify only the unscheduled task was sent to AI
        prompt = mock_ai.call_args[0][0]
        assert "Overdue Task" not in prompt, "Overdue task should not be sent to AI"
        assert "Unscheduled Task" in prompt, "Unscheduled task should be sent to AI"
