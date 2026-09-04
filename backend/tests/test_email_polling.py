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
    mock_imap.store = AsyncMock()
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


@pytest.mark.asyncio
async def test_poll_emails_sanitizes_lists(db: AsyncSession):
    # 1. Setup User with OAuth Token and Automation Enabled
    user = User(
        email="sanitizer-test@example.com",
        full_name="Sanitizer Tester",
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
    mock_imap.protocol.execute = AsyncMock(side_effect=[
        MagicMock(result="OK"),                       # AUTHENTICATE
        make_search_response(["1"]),                  # SEARCH
    ])
    mock_imap.select = AsyncMock()
    mock_imap.fetch = AsyncMock(return_value=("OK", [None, b"Subject: List test\n\nBody content"]))
    mock_imap.store = AsyncMock()
    mock_imap.logout = AsyncMock()

    # AI returns lists for title and description, and uppercase priority
    mock_extract = AsyncMock(return_value={
        "title": ["SpaceX Starship Launch", "TLDR Newsletter Growth"],
        "description": ["Part 1 of email", "Part 2 of email"],
        "priority": "HIGH",
        "due_date": "2026-06-01"
    })

    with patch("aioimaplib.IMAP4_SSL", return_value=mock_imap), \
         patch("app.core.email_processor.email_processor.extract_task", mock_extract):

        await poll_emails(db)

    # 4. Verify Task Creation and Sanitized Fields
    from sqlalchemy.future import select
    res = await db.execute(select(Issue).where(Issue.owner_id == user.id))
    issue = res.scalars().first()

    assert issue is not None
    assert issue.title == "SpaceX Starship Launch TLDR Newsletter Growth"
    assert issue.description == "Body content"
    assert issue.priority == "high"
    assert issue.due_date is not None
    assert issue.due_date.strftime("%Y-%m-%d") == "2026-06-01"
    mock_imap.store.assert_called_once_with("1", "+FLAGS", "(\\Seen)")

    from app.crud import crud_issue_summary
    issue_summary = await crud_issue_summary.get_by_issue_id(db, issue.id)
    assert issue_summary is not None
    assert issue_summary.summary == "Part 1 of email\nPart 2 of email"


@pytest.mark.asyncio
async def test_poll_emails_exception_marks_seen(db: AsyncSession):
    # 1. Setup User with OAuth Token and Automation Enabled
    user = User(
        email="exception-test@example.com",
        full_name="Exception Tester",
        oauth_provider="gmail",
        oauth_access_token="valid-token",
        oauth_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        email_automation_enabled=True
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
        make_search_response(["2"]),                  # SEARCH
    ])
    mock_imap.select = AsyncMock()
    mock_imap.fetch = AsyncMock(return_value=("OK", [None, b"Subject: Bad email\n\nBad body"]))
    mock_imap.store = AsyncMock()
    mock_imap.logout = AsyncMock()

    mock_extract = AsyncMock(return_value={
        "title": "Bad task",
        "description": "This will fail",
        "priority": "low"
    })

    # Cause create_issue to raise ValueError (simulating DB / validation failure)
    with patch("aioimaplib.IMAP4_SSL", return_value=mock_imap), \
         patch("app.core.email_processor.email_processor.extract_task", mock_extract), \
         patch("app.core.email_polling.create_issue", side_effect=ValueError("Simulated DB failure")):

        await poll_emails(db)

    # 4. Verify that the email is still marked as seen to prevent lockup
    mock_imap.store.assert_called_once_with("2", "+FLAGS", "(\\Seen)")

    # 5. Verify audit log entry for failure
    from app.models.audit_log import AuditLog
    from sqlalchemy.future import select
    res = await db.execute(select(AuditLog).where(AuditLog.user_id == user_id).where(AuditLog.action == "email.task_creation_failed"))
    log_entry = res.scalars().first()
    assert log_entry is not None
    assert "Simulated DB failure" in log_entry.details.get("error", "")


@pytest.mark.asyncio
async def test_poll_emails_aborts_loop_on_command_timeout(db: AsyncSession):
    from aioimaplib import CommandTimeout, Command
    user = User(
        email="timeout-test@example.com",
        full_name="Timeout Tester",
        oauth_provider="gmail",
        oauth_access_token="valid-token",
        oauth_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        email_automation_enabled=True
    )
    db.add(user)
    await db.commit()

    mock_imap = MagicMock()
    mock_imap.wait_hello_from_server = AsyncMock()
    mock_imap.protocol = MagicMock()
    mock_imap.protocol.new_tag = MagicMock(return_value="A1")
    mock_imap.protocol.execute = AsyncMock(side_effect=[
        MagicMock(result="OK"),
        make_search_response(["101", "102", "103", "104"]),
    ])
    mock_imap.select = AsyncMock()
    # Raise CommandTimeout on the first fetch
    cmd = Command("FETCH", "LHCE1", "101", "BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE)]")
    mock_imap.fetch = AsyncMock(side_effect=CommandTimeout(cmd))
    mock_imap.logout = AsyncMock()

    with patch("aioimaplib.IMAP4_SSL", return_value=mock_imap):
        await poll_emails(db)

    # Verify fetch was called only ONCE for "101" and then aborted without calling 102, 103, 104
    assert mock_imap.fetch.call_count == 1
    mock_imap.fetch.assert_called_once_with("101", "BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE)]")

