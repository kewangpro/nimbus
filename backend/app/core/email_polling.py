import asyncio
import base64
import ssl
import aioimaplib
import logging
from email.header import decode_header, make_header
from aioimaplib import Command, AioImapException, CommandTimeout
import httpx
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.email_processor import email_processor
from app.core.email_utils import extract_email_body_from_message
from app.schemas.issue import IssueCreate
from app.models.issue import Issue
from app.models.project import Project
from app.models.user import User
from app.models.audit_log import AuditLog
from app.crud.crud_issue import create as create_issue
from app.crud import crud_audit, crud_issue, crud_issue_summary

logger = logging.getLogger(__name__)

# Enhance aioimaplib.IMAP4_SSL to track the connection task, fast-fail on TLS/TCP handshake errors
# (e.g. SSLError WRONG_VERSION_NUMBER), and prevent unretrieved task exceptions in asyncio/uvloop.
def _nimbus_create_client(self, host: str, port: int, loop: asyncio.AbstractEventLoop = None,
                          conn_lost_cb = None, ssl_context = None) -> None:
    if ssl_context is None:
        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    local_loop = loop if loop is not None else asyncio.get_running_loop()
    self.protocol = aioimaplib.IMAP4ClientProtocol(local_loop, conn_lost_cb)
    self._connect_task = local_loop.create_task(
        local_loop.create_connection(lambda: self.protocol, host, port, ssl=ssl_context)
    )

async def _nimbus_wait_hello_from_server(self) -> None:
    if hasattr(self, "_connect_task"):
        hello_waiter = asyncio.create_task(self.protocol.wait('AUTH|NONAUTH'))
        try:
            # 1. Fast-fail if TCP connection or SSL handshake fails
            try:
                await asyncio.wait_for(asyncio.shield(self._connect_task), timeout=self.timeout)
            except Exception as conn_err:
                hello_waiter.cancel()
                raise conn_err
            # 2. Wait for server greeting
            await asyncio.wait_for(hello_waiter, timeout=self.timeout)
        finally:
            if not hello_waiter.done():
                hello_waiter.cancel()
    else:
        await asyncio.wait_for(self.protocol.wait('AUTH|NONAUTH'), self.timeout)

aioimaplib.IMAP4_SSL.create_client = _nimbus_create_client
aioimaplib.IMAP4_SSL.wait_hello_from_server = _nimbus_wait_hello_from_server

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

async def process_email_source(db: AsyncSession, user: User, retry: bool = True):
    """
    Connect to IMAP and fetch unseen emails for a specific user.
    """
    email_address = user.email
    provider = user.oauth_provider
    user_id = user.id
    host = "imap.gmail.com" if provider == "gmail" else "outlook.office365.com"
    
    try:
        # Refresh token if needed
        token = await refresh_token_v2(db, user)
        if not token:
            return

        # Connect to provider with increased timeout (60 seconds)
        imap = aioimaplib.IMAP4_SSL(host=host, timeout=60.0)
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
            try:
                one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
                recent_log = await db.execute(
                    select(AuditLog).where(
                        and_(
                            AuditLog.user_id == user_id,
                            AuditLog.action == "email.auth_failed",
                            AuditLog.created_at >= one_hour_ago
                        )
                    ).limit(1)
                )
                if not recent_log.scalars().first():
                    await crud_audit.log_action(
                        db,
                        "email.auth_failed",
                        user_id=user_id,
                        entity_type="user",
                        entity_id=user_id,
                        details={
                            "email": email_address,
                            "provider": provider,
                            "reason": f"IMAP XOAUTH2 authentication failed: {response.result}",
                            "error_class": "permanent",
                            "is_transient": False,
                        }
                    )
            except Exception as audit_err:
                logger.error(f"Failed to write email.auth_failed audit log for {email_address}: {audit_err}")
                await db.rollback()
            return

        await imap.select("INBOX")

        # Get all processed email Message-IDs from the last 14 days to prevent boundary duplicates
        fourteen_days_ago = datetime.now(timezone.utc) - timedelta(days=14)
        log_query = select(AuditLog).where(
            and_(
                AuditLog.action.like("email.%"),
                AuditLog.created_at >= fourteen_days_ago
            )
        )
        log_result = await db.execute(log_query)
        processed_logs = log_result.scalars().all()
        
        processed_ids = set()
        for log in processed_logs:
            details = log.details or {}
            m_id = details.get("message_id")
            if m_id:
                processed_ids.add(m_id)

        # Search for UNSEEN emails from last 7 days.
        # Boundary duplicates are prevented by processed_ids (which tracks 14 days).
        # Use protocol.execute directly to avoid aioimaplib injecting UTF-8 charset
        # which causes Outlook to respond with BADCHARSET error.
        search_window = datetime.now(timezone.utc) - timedelta(days=7)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        date_str = f"{search_window.day:02d}-{months[search_window.month-1]}-{search_window.year}"
        
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

        # Cap batch to at most 20 emails per poll cycle to prevent IMAP timeouts
        if len(msg_ids) > 20:
            msg_ids = msg_ids[-20:]

        if msg_ids:
            from email import message_from_bytes
            for msg_id in msg_ids:
                message_id = None
                try:
                    # Fetch only headers first to check if already processed
                    fetch_res, header_data = await imap.fetch(msg_id, "BODY.PEEK[HEADER.FIELDS (MESSAGE-ID SUBJECT DATE)]")
                    if fetch_res != "OK" or not header_data or len(header_data) < 2:
                        continue
                    header_bytes = header_data[1] if isinstance(header_data[1], (bytes, bytearray)) else header_data[1].encode(errors='replace')
                    header_msg = message_from_bytes(header_bytes)
                    
                    subject = decode_mime_header(header_msg["Subject"] or "(No Subject)")
                    message_id = header_msg["Message-ID"]
                    if not message_id:
                        message_id = f"fallback:{subject}:{header_msg['Date']}"
                    else:
                        message_id = str(message_id).strip()

                    if message_id in processed_ids:
                        logger.debug(f"Email '{subject}' (Message-ID: {message_id}) already processed by Nimbus, skipping.")
                        continue

                    # Fetch full body since it is a new email
                    _, data = await imap.fetch(msg_id, "BODY.PEEK[]")
                    if not data or len(data) < 2:
                        continue
                        
                    raw_email_bytes = data[1] if isinstance(data[1], (bytes, bytearray)) else data[1].encode(errors='replace')
                    msg = message_from_bytes(raw_email_bytes)

                    body = extract_email_body_from_message(msg)

                    # Process with AI
                    task_data = await email_processor.extract_task(subject, body)
                    if task_data is None:
                        logger.warning(f"AI extraction failed for email '{subject}' (msg_id {msg_id}). Falling back to raw task creation.")
                        # Fallback: create a single task from the email subject/body
                        task_data = {
                            "title": f"Auto-Task: {subject}",
                            "summary": f"Auto-created task from email: {subject}",
                            "priority": "medium",
                            "due_date": None
                        }
                    elif not task_data:
                        # Ad/newsletter filtering (AI returned empty list or dict)
                        try:
                            await imap.store(msg_id, "+FLAGS", "(\\Seen)")
                        except Exception:
                            pass
                        await crud_audit.log_action(
                            db,
                            "email.ignored",
                            user_id=user_id,
                            details={"email_subject": subject, "message_id": message_id, "reason": "ad_or_newsletter"}
                        )
                        processed_ids.add(message_id)
                        continue

                    # Sanitize task_data
                    title_val = task_data.get("title", subject)
                    if isinstance(title_val, list):
                        title_val = " ".join(str(item) for item in title_val)
                    elif title_val is not None:
                        title_val = str(title_val)
                    if not title_val or not title_val.strip():
                        title_val = subject
                    
                    title_val = title_val.strip()

                    # Summary from AI
                    raw_summary = task_data.get("summary")
                    if not raw_summary and task_data.get("description"):
                        candidate = task_data.get("description")
                        if isinstance(candidate, list):
                            raw_summary = candidate
                        elif isinstance(candidate, str) and candidate.strip() != body.strip():
                            raw_summary = candidate
                        elif not raw_summary:
                            raw_summary = f"Auto-created task from email: {subject}"
                    if isinstance(raw_summary, list):
                        summary_val = "\n".join(str(item) for item in raw_summary)
                    elif raw_summary is not None:
                        summary_val = str(raw_summary).strip()
                    else:
                        summary_val = None

                    # Description should be the original email body
                    desc_val = body.strip() if (body and body.strip()) else (summary_val or "")

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
                                    user_tz_str = getattr(user, "timezone", "UTC")
                                    try:
                                        from zoneinfo import ZoneInfo
                                        tz = ZoneInfo(user_tz_str)
                                    except Exception:
                                        tz = timezone.utc
                                    parsed_due_date = parsed_due_date.replace(tzinfo=tz)
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

                    # Store AI summary in IssueSummary if available
                    if summary_val:
                        content_hash = crud_issue.get_content_hash(f"{issue.title} {issue.description or ''}")
                        raw_next_steps = task_data.get("next_steps", [])
                        if isinstance(raw_next_steps, list):
                            next_steps_str = "\n".join(str(s) for s in raw_next_steps if str(s).strip())
                        elif raw_next_steps:
                            next_steps_str = str(raw_next_steps).strip()
                        else:
                            next_steps_str = ""
                        await crud_issue_summary.upsert(
                            db,
                            issue_id=issue.id,
                            summary=summary_val,
                            next_steps=next_steps_str,
                            content_hash=content_hash,
                        )
                    
                    # Audit log for automated email task creation
                    await crud_audit.log_action(
                        db, 
                        "email.task_created", 
                        user_id, 
                        "issue", 
                        issue.id,
                        details={
                            "title": issue.title, 
                            "email_subject": subject, 
                            "source": "automation",
                            "message_id": message_id
                        }
                    )
                    
                    try:
                        await imap.store(msg_id, "+FLAGS", "(\\Seen)")
                    except Exception as seen_err:
                        logger.error(f"Failed to mark msg_id {msg_id} as seen: {seen_err}")

                    logger.info(f"SUCCESS: Created auto-task from email for {email_address}: {issue.title}")
                    processed_ids.add(message_id)

                except Exception as email_err:
                    is_network_err = isinstance(email_err, (AioImapException, CommandTimeout, asyncio.TimeoutError, TimeoutError, ConnectionError, OSError))
                    logger.error(f"Failed to process email msg_id {msg_id} for user {email_address}: {email_err}", exc_info=True)
                    # Rollback db session to clean up any failed transaction
                    await db.rollback()
                    
                    if not is_network_err:
                        # Non-network error (e.g. malformed data or permanent failure): mark seen and log so it does not loop forever
                        try:
                            await imap.store(msg_id, "+FLAGS", "(\\Seen)")
                        except Exception:
                            pass
                        try:
                            await crud_audit.log_action(
                                db,
                                "email.task_creation_failed",
                                user_id=user_id,
                                details={
                                    "msg_id": msg_id,
                                    "message_id": message_id,
                                    "error": str(email_err),
                                    "error_class": "permanent",
                                    "is_transient": False,
                                }
                            )
                        except Exception as audit_err:
                            logger.error(f"Failed to write failure audit log for {email_address}: {audit_err}")
                            await db.rollback()
                        
                        if message_id:
                            processed_ids.add(message_id)
                    else:
                        # Network error: abort remaining batch so this and subsequent emails remain UNSEEN and will be retried
                        logger.warning(f"IMAP connection/timeout failure ({email_err}) for user {email_address}. Aborting remaining batch email poll to retry later.")
                        break

        try:
            await asyncio.wait_for(imap.logout(), timeout=5.0)
        except Exception as logout_err:
            logger.warning(f"IMAP logout timed out or failed: {logout_err}")

    except (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError, ssl.SSLError, AioImapException, CommandTimeout) as transient_err:
        err_label = str(transient_err).strip() or type(transient_err).__name__
        if retry:
            logger.warning(f"Transient IMAP connection error for {email_address}: {err_label}. Retrying in 3 seconds...")
            await asyncio.sleep(3)
            return await process_email_source(db, user, retry=False)

        logger.exception(f"Error processing emails for {email_address} after retry")
        try:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_log = await db.execute(
                select(AuditLog).where(
                    and_(
                        AuditLog.user_id == user_id,
                        AuditLog.action == "email.connection_failed",
                        AuditLog.created_at >= one_hour_ago
                    )
                ).limit(1)
            )
            if not recent_log.scalars().first():
                err_type = type(transient_err).__name__
                err_desc = str(transient_err).strip()
                if not err_desc:
                    if "timeout" in err_type.lower():
                        err_desc = f"Connection to {host} timed out after 60s. The mail server may be slow or temporarily throttling requests."
                    else:
                        err_desc = f"{err_type} while connecting to {host}."
                await crud_audit.log_action(
                    db,
                    "email.connection_failed",
                    user_id=user_id,
                    entity_type="user",
                    entity_id=user_id,
                    details={
                        "email": email_address,
                        "provider": provider,
                        "error": err_type,
                        "error_description": err_desc[:250],
                        "error_class": "transient",
                        "is_transient": True,
                    }
                )
        except Exception as audit_err:
            logger.error(f"Failed to write connection_failed audit log: {audit_err}")
            await db.rollback()
    except Exception as e:
        logger.exception(f"Error processing emails for {email_address}")
        try:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_log = await db.execute(
                select(AuditLog).where(
                    and_(
                        AuditLog.user_id == user_id,
                        AuditLog.action == "email.connection_failed",
                        AuditLog.created_at >= one_hour_ago
                    )
                ).limit(1)
            )
            if not recent_log.scalars().first():
                err_type = type(e).__name__
                err_desc = str(e).strip()
                if not err_desc:
                    if "timeout" in err_type.lower():
                        err_desc = f"Connection to {host} timed out after 60s. The mail server may be slow or temporarily throttling requests."
                    else:
                        err_desc = f"{err_type} while connecting to {host}."
                is_trans = (
                    isinstance(e, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError, ssl.SSLError, AioImapException, CommandTimeout))
                    or "timeout" in err_type.lower()
                    or "connection" in err_type.lower()
                    or "ssl" in err_type.lower()
                    or "timeout" in err_desc.lower()
                )
                await crud_audit.log_action(
                    db,
                    "email.connection_failed",
                    user_id=user_id,
                    entity_type="user",
                    entity_id=user_id,
                    details={
                        "email": email_address,
                        "provider": provider,
                        "error": err_type,
                        "error_description": err_desc[:250],
                        "error_class": "transient" if is_trans else "permanent",
                        "is_transient": is_trans,
                    }
                )
        except Exception as audit_err:
            logger.error(f"Failed to write connection_failed audit log: {audit_err}")
            await db.rollback()

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
        try:
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_log = await db.execute(
                select(AuditLog).where(
                    and_(
                        AuditLog.user_id == user.id,
                        AuditLog.action == "email.token_refresh_failed",
                        AuditLog.created_at >= one_hour_ago
                    )
                ).limit(1)
            )
            if not recent_log.scalars().first():
                await crud_audit.log_action(
                    db,
                    "email.token_refresh_failed",
                    user_id=user.id,
                    entity_type="user",
                    entity_id=user.id,
                    details={
                        "email": user.email,
                        "provider": user.oauth_provider,
                        "error": "missing_refresh_token",
                        "error_description": "No refresh token stored — user must re-login via SSO to restore automation.",
                        "error_class": "permanent",
                        "is_transient": False,
                    }
                )
        except Exception as audit_err:
            logger.error(f"Failed to write missing_refresh_token audit log for {user.email}: {audit_err}")
            await db.rollback()
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
                try:
                    err_data = response.json()
                except Exception:
                    err_data = {}
                err_desc = (err_data.get("error_description") if isinstance(err_data, dict) else None) or response.text
                err_name = (err_data.get("error") if isinstance(err_data, dict) else None) or "token_refresh_failed"
                is_trans = response.status_code in (500, 502, 503, 504)
                try:
                    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
                    recent_log = await db.execute(
                        select(AuditLog).where(
                            and_(
                                AuditLog.user_id == user.id,
                                AuditLog.action == "email.token_refresh_failed",
                                AuditLog.created_at >= one_hour_ago
                            )
                        ).limit(1)
                    )
                    if not recent_log.scalars().first():
                        await crud_audit.log_action(
                            db,
                            "email.token_refresh_failed",
                            user_id=user.id,
                            entity_type="user",
                            entity_id=user.id,
                            details={
                                "email": user.email,
                                "provider": provider,
                                "status_code": response.status_code,
                                "error": err_name,
                                "error_description": str(err_desc)[:250],
                                "error_class": "transient" if is_trans else "permanent",
                                "is_transient": is_trans,
                            }
                        )
                except Exception as audit_err:
                    logger.error(f"Failed to write token_refresh_failed audit log for {user.email}: {audit_err}")
                    await db.rollback()
        except Exception as e:
            logger.error(f"Token refresh error for {user.email}: {e}")
            is_trans = isinstance(e, (httpx.TimeoutException, httpx.NetworkError, ConnectionError, OSError, asyncio.TimeoutError))
            try:
                one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
                recent_log = await db.execute(
                    select(AuditLog).where(
                        and_(
                            AuditLog.user_id == user.id,
                            AuditLog.action == "email.token_refresh_failed",
                            AuditLog.created_at >= one_hour_ago
                        )
                    ).limit(1)
                )
                if not recent_log.scalars().first():
                    await crud_audit.log_action(
                        db,
                        "email.token_refresh_failed",
                        user_id=user.id,
                        entity_type="user",
                        entity_id=user.id,
                        details={
                            "email": user.email,
                            "provider": provider,
                            "error": type(e).__name__,
                            "error_description": str(e)[:250],
                            "error_class": "transient" if is_trans else "permanent",
                            "is_transient": is_trans,
                        }
                    )
            except Exception as audit_err:
                logger.error(f"Failed to write exception audit log for {user.email}: {audit_err}")
                await db.rollback()
            
    return None


def generate_xoauth2_string(user: str, token: str) -> str:
    """
    Generates the XOAUTH2 authentication string for IMAP.
    """
    auth_string = f"user={user}\x01auth=Bearer {token}\x01\x01"
    return base64.b64encode(auth_string.encode()).decode()
