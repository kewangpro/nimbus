import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.email_polling import poll_emails
from app.models.user import User
from app.models.project import Project
from app.models.issue import Issue
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
async def test_poll_emails_user_flow(db: AsyncSession):
    # 1. Setup User with OAuth Token and Automation Enabled
    user = User(
        email="poll-test@example.com",
        full_name="Poll Tester",
        oauth_provider="gmail",
        oauth_access_token="valid-token",
        oauth_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        email_automation_enabled=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # 2. Setup "General" Project
    project = Project(
        name="General",

        owner_id=user.id
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # 3. Mock IMAP Protocol
    mock_imap = MagicMock()
    mock_imap.wait_hello_from_server = AsyncMock()
    mock_imap.protocol = MagicMock()
    mock_imap.protocol.new_tag = MagicMock(return_value="A1")
    # AUTHENTICATE returns OK, SEARCH returns a list of IDs with the right structure
    mock_imap.protocol.execute = AsyncMock(side_effect=[
        MagicMock(result="OK"),                       # AUTHENTICATE
        make_search_response(["1"]),                  # SEARCH UNSEEN SINCE ...
    ])
    mock_imap.select = AsyncMock()
    mock_imap.fetch = AsyncMock(return_value=("OK", [None, b"Subject: Test Task\n\nThis is a task from email."]))
    mock_imap.logout = AsyncMock()

    mock_extract = AsyncMock(return_value={
        "title": "Extracted Task",
        "description": "Extracted Description",
        "priority": "high"
    })

    with patch("aioimaplib.IMAP4_SSL", return_value=mock_imap), \
         patch("app.core.email_processor.email_processor.extract_task", mock_extract):

        await poll_emails(db)

    # 4. Verify Task Creation
    from sqlalchemy.future import select
    res = await db.execute(select(Issue).where(Issue.title == "Extracted Task"))
    issue = res.scalars().first()

    assert issue is not None
    assert issue.project_id == project.id


@pytest.mark.asyncio
async def test_poll_emails_disabled(db: AsyncSession):
    # Setup User with Automation Disabled
    user = User(
        email="disabled-test@example.com",
        oauth_provider="gmail",
        oauth_access_token="valid-token",
        oauth_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        email_automation_enabled=False
    )
    db.add(user)
    await db.commit()

    with patch("aioimaplib.IMAP4_SSL") as mock_imap_class:
        await poll_emails(db)
        # Should not even attempt to connect
        mock_imap_class.assert_not_called()
