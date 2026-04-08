import pytest
from uuid import UUID
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from sqlalchemy import select

from app.mcp.server import (
    list_calendar_events, 
    get_task_details, 
    schedule_task, 
    create_calendar_task,
    get_default_user_id,
    search_tasks
)
from app.models.issue import Issue, IssueStatus
from app.models.project import Project
from app.models.user import User

@pytest.mark.asyncio
async def test_get_default_user_id(db):
    # Setup: ensure a user exists
    user = User(email="test@example.com", full_name="Test User", hashed_password="pw")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None
        
        with patch("os.getenv", return_value="test@example.com"):
            user_id = await get_default_user_id()
            assert user_id == user.id

@pytest.mark.asyncio
async def test_list_calendar_events_empty(db):
    # Mock AsyncSessionLocal to use the test db session
    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        # Create a mock context manager
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None

        # Setup: user
        user = User(email="test@example.com", hashed_password="pw")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        with patch("app.mcp.server.get_default_user_id", return_value=user.id):
            res = await list_calendar_events()
            assert res == "No tasks found on the calendar."

@pytest.mark.asyncio
async def test_create_calendar_task(db):
    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None

        # Setup: user and project
        user = User(email="test@example.com", hashed_password="pw")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        project = Project(name="General", owner_id=user.id)
        db.add(project)
        await db.commit()
        await db.refresh(project)

        with patch("app.mcp.server.get_default_user_id", return_value=user.id):
            res = await create_calendar_task(title="Test Task", description="Test Desc")
            assert "Created task 'Test Task'" in res
            
            # Verify in DB
            result = await db.execute(select(Issue).where(Issue.title == "Test Task"))
            issue = result.scalars().first()
            assert issue is not None
            assert issue.description == "Test Desc"
            assert issue.project_id == project.id

@pytest.mark.asyncio
async def test_schedule_task(db):
    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None

        # Setup: user, project, and issue
        user = User(email="test@example.com", hashed_password="pw")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        project = Project(name="General", owner_id=user.id)
        db.add(project)
        await db.commit()
        await db.refresh(project)

        issue = Issue(title="Original Task", project_id=project.id, owner_id=user.id)
        db.add(issue)
        await db.commit()
        await db.refresh(issue)

        due_date_iso = "2026-12-25T12:00:00Z"
        res = await schedule_task(task_id=str(issue.id), due_date_iso=due_date_iso)
        assert "Successfully scheduled" in res

        # Verify update
        await db.refresh(issue)
        assert issue.due_date is not None
        assert issue.due_date.year == 2026

@pytest.mark.asyncio
async def test_get_task_details(db):
    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None

        user = User(email="test@example.com", hashed_password="pw")
        db.add(user)
        await db.commit()

        project = Project(name="General", owner_id=user.id)
        db.add(project)
        await db.commit()

        issue = Issue(title="Detail Task", description="Fancy Desc", project_id=project.id, owner_id=user.id)
        db.add(issue)
        await db.commit()
        await db.refresh(issue)

        res = await get_task_details(task_id=str(issue.id))
        assert "Title: Detail Task" in res
        assert "Description: Fancy Desc" in res

@pytest.mark.asyncio
async def test_create_task_missing_project(db):
    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None

        user = User(email="test@example.com", hashed_password="pw")
        db.add(user)
        await db.commit()

        with patch("app.mcp.server.get_default_user_id", return_value=user.id):
            res = await create_calendar_task(title="Fail Task", project_name="NonExistent")
            assert "Error: Project 'NonExistent' not found" in res

@pytest.mark.asyncio
async def test_search_tasks(db):
    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None

        user = User(email="test@example.com", hashed_password="pw")
        db.add(user)
        await db.commit()

        project = Project(name="General", owner_id=user.id)
        db.add(project)
        await db.commit()

        issue = Issue(title="Searchable Task", owner_id=user.id, project_id=project.id)
        db.add(issue)
        await db.commit()
        await db.refresh(issue)

        # Mock embedding and search results
        mock_emb = [0.1] * 768
        mock_res = MagicMock(issue_id=issue.id)

        with patch("app.core.ai.generate_embedding", return_value=mock_emb), \
             patch("app.crud.crud_embedding.search_similar", return_value=[mock_res]), \
             patch("app.mcp.server.get_default_user_id", return_value=user.id):
            
            res = await search_tasks(query="finding my task")
            assert "Search Results" in res
            assert "Searchable Task" in res

@pytest.mark.asyncio
async def test_list_calendar_events_ordering_and_filtering(db):
    with patch("app.mcp.server.AsyncSessionLocal") as mock_session_local:
        mock_session_local.return_value.__aenter__.return_value = db
        mock_session_local.return_value.__aexit__.return_value = None

        user = User(email="test@example.com", hashed_password="pw")
        db.add(user)
        await db.commit()

        project = Project(name="General", owner_id=user.id)
        db.add(project)
        await db.commit()

        # Today's reference for filtering
        now = datetime.now(timezone.utc)
        
        # Create tasks:
        # 1. Past due (should be included, assuming they are still relevant)
        early = now - timedelta(days=1)
        # 2. Within 7 days
        mid = now + timedelta(days=3)
        # 3. Exactly on day 7
        border = now + timedelta(days=7)
        # 4. Beyond 7 days
        far = now + timedelta(days=10)
        # 5. Completed task within 7 days (should BE EXCLUDED)
        done = now + timedelta(days=2)
        # 6. Canceled task within 7 days (should BE EXCLUDED)
        canceled = now + timedelta(days=4)

        db.add(Issue(title="Early Task", due_date=early, owner_id=user.id, project_id=project.id))
        db.add(Issue(title="Mid Task", due_date=mid, owner_id=user.id, project_id=project.id))
        db.add(Issue(title="Border Task", due_date=border, owner_id=user.id, project_id=project.id))
        db.add(Issue(title="Far Task", due_date=far, owner_id=user.id, project_id=project.id))
        db.add(Issue(title="Done Task", due_date=done, owner_id=user.id, status=IssueStatus.DONE, project_id=project.id))
        db.add(Issue(title="Canceled Task", due_date=canceled, owner_id=user.id, status=IssueStatus.CANCELED, project_id=project.id))
        await db.commit()

        with patch("app.mcp.server.get_default_user_id", return_value=user.id):
            # Fetch with 7 days filter
            res = await list_calendar_events(days=7)
            
            # Verify order: Early -> Mid -> Border
            lines = [l for l in res.split("\n") if l.startswith("-")]
            assert len(lines) == 3
            assert "Early Task" in lines[0]
            assert "Mid Task" in lines[1]
            assert "Border Task" in lines[2]
            assert "Far Task" not in res
            assert "Done Task" not in res
            assert "Canceled Task" not in res
