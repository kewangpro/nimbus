import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_user, crud_project
from app.schemas.project import ProjectCreate
from app.models.project import Project
from sqlalchemy import select, and_
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_get_inbox_no_oauth(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    # By default the test user does not have oauth_access_token set
    r = await client.get("/api/v1/email-oauth/inbox", headers=normal_user_token_headers)
    assert r.status_code == 400
    assert r.json()["detail"] == "No SSO account connected"

@pytest.mark.asyncio
@patch("app.core.email_polling.refresh_token_v2", new_callable=AsyncMock)
@patch("aioimaplib.IMAP4_SSL", new_callable=MagicMock)
async def test_get_inbox_success(
    mock_imap_class, mock_refresh_token, 
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    # Give user an oauth token to bypass the first check
    user.oauth_access_token = "fake_token"
    user.oauth_provider = "google"
    await db.commit()

    mock_refresh_token.return_value = "refreshed_fake_token"
    
    # Mock IMAP interactions
    mock_imap_instance = AsyncMock()
    mock_imap_class.return_value = mock_imap_instance
    
    # Mock authenticate response
    mock_auth_resp = MagicMock()
    mock_auth_resp.result = "OK"
    
    # Mock search response
    mock_search_resp = MagicMock()
    mock_search_resp.result = "OK"
    mock_search_resp.lines = [b'1 2']
    
    mock_imap_instance.protocol.execute.side_effect = [mock_auth_resp, mock_search_resp]
    
    # Mock fetch response for ID '1' and '2'
    raw_email_bytes = b"From: test@test.com\r\nSubject: Test Subject\r\nDate: Mon, 1 Jan 2024 10:00:00 +0000\r\n\r\nTest Body"
    mock_imap_instance.fetch.return_value = (None, [None, raw_email_bytes])

    r = await client.get("/api/v1/email-oauth/inbox", headers=normal_user_token_headers)
    
    # Revert user state if needed for other tests, or it can stay
    user.oauth_access_token = None
    await db.commit()
    
    assert r.status_code == 200
    expected_data = r.json()
    assert isinstance(expected_data, list)
    assert len(expected_data) == 2
    assert expected_data[0]["subject"] == "Test Subject"
    assert "Test Body" in expected_data[0]["snippet"]

@pytest.mark.asyncio
@patch("app.core.email_processor.email_processor.extract_task", new_callable=AsyncMock)
async def test_create_task_from_email(
    mock_extract_task,
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    # Ensure "General" project exists
    res = await db.execute(select(Project).where(
        and_(Project.owner_id == user.id, Project.name == "General")
    ))
    proj = res.scalars().first()
    if not proj:
        p_in = ProjectCreate(name="General")
        await crud_project.create(db, obj_in=p_in, owner_id=user.id)
        
    mock_extract_task.return_value = {
        "title": "Extracted Task Title",
        "description": "Extracted Description",
        "priority": "high",
        "due_date": None
    }
    
    email_data = {
        "subject": "Original Subject",
        "snippet": "Original Snippet"
    }
    
    r = await client.post(
        "/api/v1/email-oauth/create-task-from-email", 
        headers=normal_user_token_headers, 
        json=email_data
    )
    
    assert r.status_code == 200
    resp_data = r.json()
    assert resp_data["status"] == "success"
    assert "issue_id" in resp_data
