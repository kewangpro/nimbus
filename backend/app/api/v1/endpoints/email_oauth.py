from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from aioimaplib import Command
from sqlalchemy.ext.asyncio import AsyncSession
from app.api import deps
from app.models.user import User
from app.crud import crud_audit, crud_issue, crud_issue_summary
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

from app.core.email_utils import clean_email_html, extract_email_body_from_message

def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace for clean snippet display."""
    return clean_email_html(text)


async def _get_full_email_body(db: AsyncSession, user: User, msg_id: str) -> Optional[str]:
    if not user.oauth_access_token:
        return None
    from app.core.email_polling import refresh_token_v2, generate_xoauth2_string
    token = await refresh_token_v2(db, user)
    if not token:
        return None

    provider = user.oauth_provider
    host = "imap.gmail.com" if provider == "gmail" else "outlook.office365.com"
    
    import aioimaplib
    from email import message_from_string
    from aioimaplib import Command

    try:
        imap = aioimaplib.IMAP4_SSL(host=host, timeout=30.0)
        await imap.wait_hello_from_server()
        auth_string = generate_xoauth2_string(user.email, token)
        response = await imap.protocol.execute(Command("AUTHENTICATE", imap.protocol.new_tag(), "XOAUTH2", auth_string))
        if response.result != "OK":
            return None
        
        imap.protocol.state = "AUTH"

        await imap.select("INBOX")
        _, data = await imap.fetch(msg_id, "RFC822")
        await imap.logout()

        if not data or len(data) < 2:
            return None

        raw_email = data[1].decode() if isinstance(data[1], (bytes, bytearray)) else data[1]
        msg = message_from_string(raw_email)

        return extract_email_body_from_message(msg)
    except Exception:
        return None


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
    from email import message_from_bytes
    
    try:
        imap = aioimaplib.IMAP4_SSL(host=host, timeout=30.0)
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
        
        # Parse IDs from the response lines (e.g. b'* SEARCH 101 102 103')
        found_ids = []
        for line in search_resp.lines:
            if isinstance(line, bytes) and line.strip():
                parts = line.split()
                for part in parts:
                    val = part.decode(errors='ignore')
                    if val.isdigit():
                        found_ids.append(val)

        
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
                
            raw_email_bytes = data[1] if isinstance(data[1], (bytes, bytearray)) else data[1].encode(errors='replace')
            msg = message_from_bytes(raw_email_bytes)


            
            body = extract_email_body_from_message(msg)

            results.append({
                "id": msg_id,
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
    msg_id = email_data.get("id")

    body_to_process = snippet
    if msg_id:
        full_body = await _get_full_email_body(db, current_user, msg_id)
        if full_body:
            body_to_process = full_body
    
    # Process with AI
    task_data_raw = await email_processor.extract_task(subject, body_to_process)
    
    # Extract task data dictionary safely
    if isinstance(task_data_raw, list):
        task_data = task_data_raw[0] if task_data_raw else {}
    elif isinstance(task_data_raw, dict):
        task_data = task_data_raw
    else:
        task_data = {}
    
    # Find user's "General" project
    res = await db.execute(select(Project).where(and_(Project.owner_id == current_user.id, Project.name == "General")))
    proj = res.scalars().first()
    
    if not proj:
        # Fallback to any project owned by user
        res = await db.execute(select(Project).where(Project.owner_id == current_user.id))
        proj = res.scalars().first()
        
    if not proj:
        raise HTTPException(status_code=404, detail="No suitable project found to create task")


    # AI sometimes returns "null" as a string, which breaks Pydantic validation
    due_date_val = task_data.get("due_date")
    if due_date_val == "null":
        due_date_val = None

    raw_summary = task_data.get("summary") or task_data.get("description")
    if isinstance(raw_summary, list):
        summary_val = "\n".join(str(item) for item in raw_summary)
    elif raw_summary is not None:
        summary_val = str(raw_summary).strip()
    else:
        summary_val = None

    desc_val = body_to_process.strip() if (body_to_process and body_to_process.strip()) else (summary_val or "")

    issue_in = IssueCreate(
        title=task_data.get("title", subject),
        description=desc_val,
        priority=task_data.get("priority", "medium"),
        due_date=due_date_val,
        project_id=proj.id,
        assignee_id=current_user.id
    )

    issue = await create_issue(db, obj_in=issue_in, owner_id=current_user.id)

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


@router.post("/create-tasks-bulk")
async def create_tasks_bulk(
    emails_data: List[dict],
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """On-demand task creation from multiple selected emails"""
    from app.core.email_processor import email_processor
    
    # Find user's "General" project
    res = await db.execute(select(Project).where(and_(Project.owner_id == current_user.id, Project.name == "General")))
    proj = res.scalars().first()
    
    if not proj:
        # Fallback to any project owned by user
        res = await db.execute(select(Project).where(Project.owner_id == current_user.id))
        proj = res.scalars().first()
        
    if not proj:
        raise HTTPException(status_code=404, detail="No suitable project found to create tasks")

    created_issues = []
    for email_data in emails_data:
        subject = email_data.get("subject", "")
        snippet = email_data.get("snippet", "")
        msg_id = email_data.get("id")
        
        body_to_process = snippet
        if msg_id:
            full_body = await _get_full_email_body(db, current_user, msg_id)
            if full_body:
                body_to_process = full_body
        
        # Process with AI
        task_data_raw = await email_processor.extract_task(subject, body_to_process)
        
        # Ensure we have a list of task data even if AI returned a single object
        tasks_to_create = []
        if isinstance(task_data_raw, list) and task_data_raw:
            tasks_to_create = [task_data_raw[0]]
        elif isinstance(task_data_raw, dict):
            tasks_to_create = [task_data_raw]
        else:
            # Fallback if AI fails or returns empty list for manually selected email
            tasks_to_create = [{"title": subject, "summary": "Auto-created from email"}]

        for task_data in tasks_to_create:
            # AI sometimes returns "null" as a string, which breaks Pydantic validation
            due_date_val = task_data.get("due_date")
            if due_date_val == "null":
                due_date_val = None

            raw_summary = task_data.get("summary") or task_data.get("description")
            if isinstance(raw_summary, list):
                summary_val = "\n".join(str(item) for item in raw_summary)
            elif raw_summary is not None:
                summary_val = str(raw_summary).strip()
            else:
                summary_val = None

            desc_val = body_to_process.strip() if (body_to_process and body_to_process.strip()) else (summary_val or "")

            issue_in = IssueCreate(
                title=task_data.get("title", subject),
                description=desc_val,
                priority=task_data.get("priority", "medium"),
                due_date=due_date_val,
                project_id=proj.id,
                assignee_id=current_user.id
            )

            issue = await create_issue(db, obj_in=issue_in, owner_id=current_user.id)

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

            created_issues.append(str(issue.id))
            
            # Audit log for manual email task creation
            await crud_audit.log_action(
                db, 
                "email.task_created_manual", 
                current_user.id, 
                "issue", 
                issue.id, 
                details={"title": issue.title, "email_subject": subject, "source": "bulk"}
            )
    
    return {"status": "success", "issue_ids": created_issues}
