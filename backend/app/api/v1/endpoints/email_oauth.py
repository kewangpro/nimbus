from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from aioimaplib import Command
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.models.user import User
from app.crud import crud_audit
from app.schemas.issue import IssueCreate
from app.crud.crud_issue import create as create_issue
from app.models.project import Project
from sqlalchemy import select, and_
import re
from email.header import decode_header, make_header

router = APIRouter()

def _decode_header(raw: Optional[str]) -> str:
    """Decode RFC 2047 encoded email headers (e.g. =?utf-8?B?...?=)."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw

def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace for clean snippet display."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


@router.get("/inbox", response_model=List[dict])
async def get_inbox(
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Fetch recent emails from the logged-in user's inbox"""
    if not current_user.oauth_access_token:
        raise HTTPException(status_code=400, detail="No SSO account connected")

    from app.core.email_polling import refresh_token_v2, generate_xoauth2_string
    token = await refresh_token_v2(db, current_user)
    if not token:
        raise HTTPException(status_code=401, detail="Failed to refresh email tokens")

    provider = current_user.oauth_provider
    host = "imap.gmail.com" if provider == "gmail" else "outlook.office365.com"
    
    import aioimaplib
    from email import message_from_string
    
    try:
        imap = aioimaplib.IMAP4_SSL(host=host)
        await imap.wait_hello_from_server()
        auth_string = generate_xoauth2_string(current_user.email, token)
        response = await imap.protocol.execute(Command("AUTHENTICATE", imap.protocol.new_tag(), "XOAUTH2", auth_string))
        if response.result == "OK":
            imap.protocol.state = "AUTH"
        else:
            return []

        
        await imap.select("INBOX")
        
        # Get messages from last 3 days
        three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        date_str = f"{three_days_ago.day:02d}-{months[three_days_ago.month-1]}-{three_days_ago.year}"
        
        search_resp = await imap.protocol.execute(Command("SEARCH", imap.protocol.new_tag(), f"SINCE {date_str}"))

        if search_resp.result != "OK":

            await imap.logout()
            return []
        
        # Parse IDs from the response lines (e.g. b'101 102 103')
        found_ids = []
        for line in search_resp.lines:
            if isinstance(line, bytes) and line.strip() and not line.strip().startswith(b'SEARCH'):
                found_ids.extend(mid.decode() for mid in line.split())

        
        if not found_ids:
            await imap.logout()
            return []

        
        # Newest first, up to 20
        found_ids.reverse()
        recent_ids = found_ids[:20]
        
        results = []
        for msg_id in recent_ids:
            _, data = await imap.fetch(msg_id, "RFC822")

            if not data or len(data) < 2:
                continue
                
            raw_email = data[1].decode() if isinstance(data[1], (bytes, bytearray)) else data[1]
            msg = message_from_string(raw_email)


            
            # Prefer text/plain part; fall back to stripping html
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
                        break
                    elif ct == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = _strip_html(payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    raw_body = payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload
                    body = raw_body if msg.get_content_type() == "text/plain" else _strip_html(raw_body)

            results.append({
                "id": msg_id if isinstance(msg_id, str) else msg_id.decode(),
                "subject": _decode_header(msg["Subject"]) or "(No Subject)",
                "from": _decode_header(msg["From"]),
                "date": msg["Date"],
                "snippet": body[:200]
            })

            
        await imap.logout()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/create-task-from-email")
async def create_task_from_email(
    email_data: dict,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """On-demand task creation from a selected email"""
    from app.core.email_processor import email_processor

    subject = email_data.get("subject", "")
    snippet = email_data.get("snippet", "")
    
    # Process with AI
    task_data = await email_processor.extract_task(subject, snippet)
    
    # Find user's "General" project
    res = await db.execute(select(Project).where(and_(Project.owner_id == current_user.id, Project.name == "General")))
    proj = res.scalars().first()
    
    if not proj:
        # Fallback to any project owned by user
        res = await db.execute(select(Project).where(Project.owner_id == current_user.id))
        proj = res.scalars().first()
        
    if not proj:
        raise HTTPException(status_code=404, detail="No suitable project found to create task")


    issue_in = IssueCreate(
        title=task_data.get("title", subject),
        description=task_data.get("description", snippet),
        priority=task_data.get("priority", "medium"),
        due_date=task_data.get("due_date"),
        project_id=proj.id,
        assignee_id=current_user.id
    )

    
    issue = await create_issue(db, obj_in=issue_in, owner_id=current_user.id)
    
    # Audit log for manual email task creation
    await crud_audit.log_action(
        db, 
        "email.task_created_manual", 
        current_user.id, 
        "issue", 
        issue.id, 
        details={"title": issue.title, "email_subject": subject, "source": "manual"}
    )
    
    return {"status": "success", "issue_id": str(issue.id)}
