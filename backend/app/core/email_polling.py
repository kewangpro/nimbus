import base64
import aioimaplib
import logging
from email.header import decode_header, make_header
from aioimaplib import Command
import httpx
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.email_processor import email_processor
from app.schemas.issue import IssueCreate
from app.models.issue import Issue
from app.models.project import Project
from app.models.user import User
from app.crud.crud_issue import create as create_issue
from app.crud import crud_audit

logger = logging.getLogger(__name__)

def decode_mime_header(s: Optional[str]) -> str:
    """
    Decodes RFC 2047 MIME encoded-word strings.
    """
    if not s:
        return ""
    try:
        return str(make_header(decode_header(s)))
    except Exception:
        return s

async def poll_emails(db: AsyncSession):
    """
    Background job to poll emails for all SSO users who have automation enabled.
    """
    # 1. Get all users with SSO tokens and automation enabled
    query = select(User).where(
            and_(
                User.oauth_access_token.isnot(None),
                User.oauth_provider.isnot(None),
                User.email_automation_enabled == True
            )
        )
    result = await db.execute(query)
    users = result.scalars().all()
    
    # 2. Process each user
    for user in users:
        await process_email_source(db, user)

async def process_email_source(db: AsyncSession, user: User):
    """
    Connect to IMAP and fetch unseen emails for a specific user.
    """
    email_address = user.email
    provider = user.oauth_provider
    user_id = user.id
    
    try:
        # Refresh token if needed
        token = await refresh_token_v2(db, user)
        if not token:
            return

        # Connect to provider
        host = "imap.gmail.com" if provider == "gmail" else "outlook.office365.com"
        imap = aioimaplib.IMAP4_SSL(host=host)
        await imap.wait_hello_from_server()
        
        # XOAUTH2 Authentication
        auth_string = generate_xoauth2_string(email_address, token)
        response = await imap.protocol.execute(Command("AUTHENTICATE", imap.protocol.new_tag(), "XOAUTH2", auth_string))
        logger.debug(f"AUTHENTICATE result for {email_address}: {response.result}, lines: {response.lines}")
        if response.result == "OK":
            imap.protocol.state = "AUTH"
        else:
            # Log the full server error detail (Outlook often returns a base64 JSON error)
            logger.error(f"XOAUTH2 AUTHENTICATE failed for {email_address}: result={response.result} lines={response.lines}")
            # Don't call logout() — connection is still in NONAUTH, that would throw
            # Try forcing a token refresh in case the token was silently revoked
            logger.info(f"Forcing token refresh for {email_address} due to auth failure...")
            user.oauth_token_expires_at = None  # invalidate so refresh_token_v2 will attempt refresh
            await db.commit()
            return

        await imap.select("INBOX")

        
        # Search for UNSEEN emails from last 3 days
        # Use protocol.execute directly to avoid aioimaplib injecting UTF-8 charset
        # which causes Outlook to respond with BADCHARSET error.
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        date_str = f"{three_days_ago.day:02d}-{months[three_days_ago.month-1]}-{three_days_ago.year}"
        
        search_resp = await imap.protocol.execute(Command("SEARCH", imap.protocol.new_tag(), f"UNSEEN SINCE {date_str}"))
        if search_resp.result != "OK":
            # Fallback: try just UNSEEN
            search_resp = await imap.protocol.execute(Command("SEARCH", imap.protocol.new_tag(), "UNSEEN"))
        
        # Parse message IDs from response lines (e.g. b'* SEARCH 101 102 103')
        msg_ids = []
        for line in search_resp.lines:
            if isinstance(line, bytes) and line.strip():
                parts = line.split()
                for part in parts:
                    val = part.decode(errors='ignore')
                    if val.isdigit():
                        msg_ids.append(val)

        
        if msg_ids:
            from email import message_from_bytes
            for msg_id in msg_ids:
                try:
                    # Use BODY.PEEK[] to fetch without marking as Seen
                    _, data = await imap.fetch(msg_id, "BODY.PEEK[]")
                    if not data or len(data) < 2:
                        continue
                        
                    raw_email_bytes = data[1] if isinstance(data[1], (bytes, bytearray)) else data[1].encode(errors='replace')
                    msg = message_from_bytes(raw_email_bytes)

                    subject = decode_mime_header(msg["Subject"] or "(No Subject)")
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
                                break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)

                    # Process with AI
                    extracted_tasks = await email_processor.extract_task(subject, body)
                    if extracted_tasks is None:
                        logger.warning(f"AI extraction failed for email '{subject}' (msg_id {msg_id}). Falling back to raw task creation.")
                        # Fallback: create a single task from the email subject/body
                        tasks = [{
                            "title": f"Auto-Task: {subject}",
                            "description": body,
                            "priority": "medium",
                            "due_date": None
                        }]
                    else:
                        if isinstance(extracted_tasks, dict):
                            tasks = [extracted_tasks]
                        elif isinstance(extracted_tasks, list):
                            tasks = [extracted_tasks[0]] if extracted_tasks else []
                        else:
                            logger.warning(f"Invalid format returned by AI extraction for msg_id {msg_id}. Falling back.")
                            tasks = [{
                                "title": f"Auto-Task: {subject}",
                                "description": body,
                                "priority": "medium",
                                "due_date": None
                            }]

                    created_issues = []
                    seen_titles = set()
                    for task_data in tasks:
                        # Sanitize task_data
                        title_val = task_data.get("title", subject)
                        if isinstance(title_val, list):
                            title_val = " ".join(str(item) for item in title_val)
                        elif title_val is not None:
                            title_val = str(title_val)
                        if not title_val or not title_val.strip():
                            title_val = subject
                        
                        title_val = title_val.strip()

                        # 1. Local de-duplication (within the same email)
                        if title_val.lower() in seen_titles:
                            logger.info(f"Skipping duplicate task title in same email: {title_val}")
                            continue
                        seen_titles.add(title_val.lower())

                        # 2. Database de-duplication (check if title already exists for this user)
                        existing_query = select(Issue).where(
                            and_(
                                Issue.owner_id == user_id,
                                Issue.title == title_val
                            )
                        )
                        existing_res = await db.execute(existing_query)
                        if existing_res.scalars().first():
                            logger.info(f"Skipping task creation, title already exists in DB: {title_val}")
                            continue

                        ai_desc = task_data.get("description")
                        if isinstance(ai_desc, list):
                            ai_desc = "\n".join(str(item) for item in ai_desc)
                        elif ai_desc is not None:
                            ai_desc = str(ai_desc)
                            
                        if ai_desc:
                            desc_val = f"{ai_desc}\n\n---\n**Original Email Content:**\n{body}"
                        else:
                            desc_val = body

                        priority_val = task_data.get("priority", "medium")
                        if isinstance(priority_val, str):
                            priority_val = priority_val.strip().lower()
                        else:
                            priority_val = "medium"
                        if priority_val not in ["low", "medium", "high", "urgent"]:
                            priority_val = "medium"

                        due_date_val = task_data.get("due_date")
                        parsed_due_date = None
                        if due_date_val:
                            if isinstance(due_date_val, list):
                                due_date_val = str(due_date_val[0]) if due_date_val else None
                            if isinstance(due_date_val, str):
                                due_date_val = due_date_val.strip()
                                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                                    try:
                                        parsed_due_date = datetime.strptime(due_date_val, fmt)
                                        parsed_due_date = parsed_due_date.replace(tzinfo=timezone.utc)
                                        break
                                    except ValueError:
                                        continue

                        # Find user's "General" project
                        res = await db.execute(select(Project).where(and_(Project.owner_id == user_id, Project.name == "General")))
                        proj = res.scalars().first()

                        if not proj:
                            raise ValueError(f"Default 'General' project not found for user {email_address}")

                        issue_in = IssueCreate(
                            title=title_val,
                            description=desc_val,
                            priority=priority_val,
                            due_date=parsed_due_date,
                            project_id=proj.id,
                            assignee_id=user_id
                        )

                        issue = await create_issue(db, obj_in=issue_in, owner_id=user_id)
                        created_issues.append(issue)
                    
                    # Explicitly mark as seen only after DB commit of all issues
                    await imap.store(msg_id, "+FLAGS", "(\\Seen)")
                    
                    # Audit log for each automated email task creation
                    for issue in created_issues:
                        await crud_audit.log_action(
                            db, 
                            "email.task_created", 
                            user_id, 
                            "issue", 
                            issue.id,
                            details={"title": issue.title, "email_subject": subject, "source": "automation"}
                        )
                        logger.info(f"SUCCESS: Created auto-task from email for {email_address}: {issue.title}")

                except Exception as email_err:
                    logger.error(f"Failed to process email msg_id {msg_id} for user {email_address}: {email_err}", exc_info=True)
                    # Rollback db session to clean up any failed transaction
                    await db.rollback()
                    try:
                        # Log audit event for failure in a clean transaction
                        await crud_audit.log_action(
                            db,
                            "email.task_creation_failed",
                            user_id=user_id,
                            details={"msg_id": msg_id, "error": str(email_err)}
                        )
                    except Exception as audit_err:
                        logger.error(f"Failed to write failure audit log for {email_address}: {audit_err}")
                        await db.rollback()
                    
                    try:
                        # Ensure we mark the email as Seen to prevent it from blocking the queue
                        await imap.store(msg_id, "+FLAGS", "(\\Seen)")
                        logger.info(f"Marked email msg_id {msg_id} as seen to prevent queue lockup.")
                    except Exception as imap_err:
                        logger.error(f"Failed to mark email msg_id {msg_id} as seen: {imap_err}")

        await imap.logout()

    except Exception as e:
        logger.exception(f"Error processing emails for {email_address}")

async def refresh_token_v2(db: AsyncSession, user: User) -> Optional[str]:
    """
    Refreshes the OAuth token for a user if it's expired or about to expire.
    """
    expires_at = user.oauth_token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at and expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        logger.debug(f"Token for {user.email} is still valid, expires at {expires_at}")
        return user.oauth_access_token

    logger.info(f"Token for {user.email} is expired or expiring soon (expires_at={expires_at}), attempting refresh...")

    if not user.oauth_refresh_token:
        logger.error(f"No refresh token stored for {user.email} — user must re-login via SSO to restore automation.")
        return None

    provider = user.oauth_provider
    if provider == "gmail":
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "refresh_token": user.oauth_refresh_token,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
        }
    elif provider == "outlook":
        token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        data = {
            "refresh_token": user.oauth_refresh_token,
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "client_secret": settings.MICROSOFT_CLIENT_SECRET,
            "grant_type": "refresh_token",
        }
    else:
        logger.error(f"Unknown provider '{provider}' for {user.email}")
        return None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=data)
            if response.status_code == 200:
                tokens = response.json()
                user.oauth_access_token = tokens["access_token"]
                expires_in = tokens.get("expires_in", 3600)
                user.oauth_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                
                db.add(user)
                await db.commit()
                logger.info(f"Token refreshed successfully for {user.email}, expires in {expires_in}s")
                return user.oauth_access_token
            else:
                logger.error(f"Token refresh HTTP {response.status_code} for {user.email}: {response.text[:300]}")
        except Exception as e:
            logger.error(f"Token refresh error for {user.email}: {e}")
            
    return None


def generate_xoauth2_string(user: str, token: str) -> str:
    """
    Generates the XOAUTH2 authentication string for IMAP.
    """
    auth_string = f"user={user}\x01auth=Bearer {token}\x01\x01"
    return base64.b64encode(auth_string.encode()).decode()
