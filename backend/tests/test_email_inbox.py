import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy import select
from app.models.user import User
from app.models.project import Project
from datetime import datetime, timedelta, timezone


def make_search_response(ids: list = None):
    """Helper that mimics protocol.execute() returning a SEARCH response."""
    ids = ids or ["1"]
    line = " ".join(str(i) for i in ids).encode()
    mock_resp = MagicMock()
    mock_resp.result = "OK"
    mock_resp.lines = [line, b"SEARCH completed."]
    return mock_resp


@pytest.mark.asyncio
async def test_get_inbox_success(client: AsyncClient, db: AsyncSession, normal_user_token_headers: dict):
    # 1. Update Test User with OAuth Token
    res = await db.execute(select(User).where(User.email == "user@example.com"))
    user = res.scalars().first()
    user.oauth_provider = "outlook"
    user.oauth_access_token = "valid-token"
    user.oauth_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db.add(user)
    await db.commit()

    # 2. Mock IMAP
    mock_imap = MagicMock()
    mock_imap.wait_hello_from_server = AsyncMock()
    mock_imap.protocol = MagicMock()
    mock_imap.protocol.new_tag = MagicMock(return_value="A1")
    # AUTHENTICATE returns OK, SEARCH returns a list of IDs
    mock_imap.protocol.execute = AsyncMock(side_effect=[
        MagicMock(result="OK"),       # AUTHENTICATE
        make_search_response(["1"]),  # SEARCH SINCE ...
    ])
    mock_imap.select = AsyncMock()

    # Corrected email content for parsing
    mock_email_content = b"Subject: Inbox Task\r\nFrom: sender@example.com\r\nDate: Mon, 8 Mar 2026 12:00:00 +0000\r\n\r\nSnippet content"
    mock_imap.fetch = AsyncMock(return_value=("OK", [None, mock_email_content]))
    mock_imap.logout = AsyncMock()

    with patch("aioimaplib.IMAP4_SSL", return_value=mock_imap):
        response = await client.get("/api/v1/email-oauth/inbox", headers=normal_user_token_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["subject"] == "Inbox Task"


@pytest.mark.asyncio
async def test_create_task_from_email(client: AsyncClient, db: AsyncSession, normal_user_token_headers: dict):
    # 1. Setup "Email" Project for the user created by normal_user_token_headers
    res = await db.execute(select(User).where(User.email == "user@example.com"))
    user = res.scalars().first()

    project = Project(name="Email", owner_id=user.id)
    db.add(project)
    await db.commit()

    # 2. Mock AI
    mock_extract = AsyncMock(return_value={
        "title": "AI Task",
        "description": "AI Description",
        "priority": "low"
    })

    payload = {
        "subject": "Email Subject",
        "snippet": "Email Snippet"
    }

    with patch("app.core.email_processor.email_processor.extract_task", mock_extract):
        response = await client.post(
            "/api/v1/email-oauth/create-task-from-email",
            json=payload,
            headers=normal_user_token_headers
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
