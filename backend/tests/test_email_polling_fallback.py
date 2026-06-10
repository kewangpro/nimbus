import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.future import select
from app.core.email_polling import poll_emails
from app.models.user import User
from app.models.project import Project
from app.models.issue import Issue
from app.models.audit_log import AuditLog

def make_search_response(msg_ids):
    resp = MagicMock()
    resp.result = "OK"
    # Mocking lines to be bytes objects as expected by the search_resp parsing in email_polling.py
    resp.lines = [f"* SEARCH {' '.join(msg_ids)}".encode()]
    return resp

@pytest.mark.asyncio
async def test_poll_emails_fallback_on_ai_failure(db):
    # 1. Setup User
    from datetime import datetime, timedelta, timezone
    user = User(
        email="fallback@example.com",
        is_active=True,
        email_automation_enabled=True,
        oauth_access_token="dummy",
        oauth_provider="google",
        oauth_token_expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    user_id = user.id

    # 2. Setup "General" Project
    project = Project(
        name="General",
        owner_id=user_id
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # 3. Mock IMAP Protocol
    mock_imap = MagicMock()
    mock_imap.wait_hello_from_server = AsyncMock()
    mock_imap.protocol = MagicMock()
    mock_imap.protocol.new_tag = MagicMock(return_value="A1")
    mock_imap.protocol.execute = AsyncMock(side_effect=[
        MagicMock(result="OK"),                       # AUTHENTICATE
        make_search_response(["3"]),                  # SEARCH
    ])
    mock_imap.select = AsyncMock()
    mock_imap.fetch = AsyncMock(return_value=("OK", [None, b"Subject: Fallback Test\n\nFallback Body"]))
    mock_imap.store = AsyncMock()
    mock_imap.logout = AsyncMock()

    # Mock extract_task to return None (simulating AI failure)
    with patch("aioimaplib.IMAP4_SSL", return_value=mock_imap), \
         patch("app.core.email_processor.email_processor.extract_task", AsyncMock(return_value=None)):

        await poll_emails(db)

    # 4. Verify that a task was still created
    res = await db.execute(select(Issue).where(Issue.owner_id == user_id))
    issue = res.scalars().first()
    assert issue is not None
    assert "Auto-Task: Fallback Test" in issue.title
    assert "Fallback Body" in issue.description

    # 5. Verify audit log entry for success (not failure)
    res = await db.execute(select(AuditLog).where(AuditLog.user_id == user_id).where(AuditLog.action == "email.task_created"))
    log_entry = res.scalars().first()
    assert log_entry is not None
    assert log_entry.details.get("title") == issue.title
