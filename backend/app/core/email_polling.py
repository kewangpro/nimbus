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
        
        # Parse message IDs from response lines (decode bytes -> str for fetch())
        msg_ids = []
        for line in search_resp.lines:
            if isinstance(line, bytes) and line.strip() and not line.strip().startswith(b'SEARCH'):
                msg_ids.extend(mid.decode() for mid in line.split())

        
        if msg_ids:
            from email import message_from_string
            for msg_id in msg_ids:

                # Use BODY.PEEK[] to fetch without marking as Seen
                _, data = await imap.fetch(msg_id, "BODY.PEEK[]")
                if not data or len(data) < 2:
                    continue
                    
                raw_email = data[1].decode() if isinstance(data[1], (bytes, bytearray)) else data[1]
                msg = message_from_string(raw_email)

                
                
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
                task_data = await email_processor.extract_task(subject, body)
                if task_data:
                    # Find user's "General" project
                    res = await db.execute(select(Project).where(and_(Project.owner_id == user.id, Project.name == "General")))
                    proj = res.scalars().first()

                    
                    if proj:
                        issue_in = IssueCreate(
                            title=task_data.get("title", subject),
                            description=task_data.get("description", body),
                            priority=task_data.get("priority", "medium"),
                            due_date=task_data.get("due_date"),
                            project_id=proj.id,
                            assignee_id=user.id
                        )

                        issue = await create_issue(db, obj_in=issue_in, owner_id=user.id)
                        
                        # Explicitly mark as seen only after DB commit
                        await imap.store(msg_id, "+FLAGS", "(\\Seen)")
                        
                        # Audit log for automated email task creation
                        await crud_audit.log_action(
                            db, 
                            "email.task_created", 
                            user.id, 
                            "issue", 
                            issue.id,
                            details={"title": issue.title, "email_subject": subject, "source": "automation"}
                        )
                        
                        logger.info(f"SUCCESS: Created auto-task from email for {user.email}: {issue_in.title}")

        await imap.logout()

    except Exception as e:
        logger.exception(f"Error processing emails for {user.email}")

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
