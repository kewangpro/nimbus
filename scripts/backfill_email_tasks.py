"""
Backfill script for email-generated tasks in Nimbus.

This script performs two operations:
1. Backfills AI summaries: Copies the existing issue.description (which holds the AI summary)
   into the IssueSummary table so it appears in the 'AI Summary' section in Nimbus UI.
2. (Optional with --fetch-bodies): Connects to the user's mailbox over IMAP via OAuth,
   retrieves the original raw email content using the Message-ID or subject from AuditLog,
   and restores the original email content into issue.description.

Usage:
  # 1. Backfill AI summaries into IssueSummary table (Fast, offline, 100% of tasks):
  venv/bin/python scripts/backfill_email_tasks.py --summaries-only

  # 2. Test restoring original email bodies for 5 tasks:
  venv/bin/python scripts/backfill_email_tasks.py --fetch-bodies --limit 5

  # 3. Full backfill (summaries + original bodies from IMAP):
  venv/bin/python scripts/backfill_email_tasks.py --fetch-bodies
"""

import sys
import os
import argparse
import asyncio
import logging
import re
from typing import Optional, Dict, Any
from email import message_from_bytes
from datetime import datetime, timezone

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(backend_dir, ".env"))

from sqlalchemy import select, and_
from aioimaplib import IMAP4_SSL, Command

from app.db.session import AsyncSessionLocal
from app.models.issue import Issue
from app.models.issue_summary import IssueSummary
from app.models.audit_log import AuditLog
from app.models.user import User
from app.crud import crud_issue, crud_issue_summary
from app.core.email_polling import refresh_token_v2, generate_xoauth2_string

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill")


def strip_html(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_email_body(msg) -> str:
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
                    raw_html = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
                    body = strip_html(raw_html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            raw_payload = (payload.decode(errors='replace') if isinstance(payload, (bytes, bytearray)) else payload)
            body = raw_payload if msg.get_content_type() == "text/plain" else strip_html(raw_payload)
    return body.strip()


async def get_imap_connection(user: User, token: str) -> Optional[IMAP4_SSL]:
    provider = user.oauth_provider
    host = "imap.gmail.com" if provider == "gmail" else "outlook.office365.com"
    try:
        imap = IMAP4_SSL(host=host, timeout=30.0)
        await imap.wait_hello_from_server()
        auth_string = generate_xoauth2_string(user.email, token)
        resp = await imap.protocol.execute(Command("AUTHENTICATE", imap.protocol.new_tag(), "XOAUTH2", auth_string))
        if resp.result != "OK":
            logger.error(f"IMAP Auth failed for {user.email}: {resp.result}")
            return None
        imap.protocol.state = "AUTH"
        await imap.select("INBOX")
        return imap
    except Exception as e:
        logger.error(f"Error connecting to IMAP: {e}")
        return None


async def fetch_body_for_task(imap: IMAP4_SSL, message_id: Optional[str], subject: Optional[str]) -> Optional[str]:
    msg_num = None

    # 1. Search by Message-ID if present
    if message_id:
        try:
            search_cmd = f'HEADER Message-ID {message_id}'
            resp = await imap.protocol.execute(Command("SEARCH", imap.protocol.new_tag(), search_cmd))
            if resp.result == "OK":
                for line in resp.lines:
                    if isinstance(line, bytes) and line.strip():
                        parts = line.split()
                        for part in parts:
                            val = part.decode(errors='ignore')
                            if val.isdigit():
                                msg_num = val
                                break
                    if msg_num:
                        break
        except Exception as e:
            logger.warning(f"Error searching by Message-ID: {e}")

    # 2. Fallback: Search by Subject if Message-ID search failed
    if not msg_num and subject:
        try:
            # Clean subject for IMAP search query (strip quotes)
            clean_subj = subject.replace('"', '').replace('\\', '').strip()
            if clean_subj:
                search_cmd = f'SUBJECT "{clean_subj[:50]}"'
                resp = await imap.protocol.execute(Command("SEARCH", imap.protocol.new_tag(), search_cmd))
                if resp.result == "OK":
                    for line in resp.lines:
                        if isinstance(line, bytes) and line.strip():
                            parts = line.split()
                            for part in parts:
                                val = part.decode(errors='ignore')
                                if val.isdigit():
                                    msg_num = val
                                    break
                        if msg_num:
                            break
        except Exception as e:
            logger.warning(f"Error searching by Subject: {e}")

    if not msg_num:
        return None

    # Fetch full message body
    try:
        fetch_res, data = await imap.fetch(msg_num, "BODY.PEEK[]")
        if fetch_res != "OK" or not data or len(data) < 2:
            return None
        raw_email_bytes = data[1] if isinstance(data[1], (bytes, bytearray)) else data[1].encode(errors='replace')
        msg = message_from_bytes(raw_email_bytes)
        body = extract_email_body(msg)
        return body if body else None
    except Exception as e:
        logger.warning(f"Error fetching msg {msg_num}: {e}")
        return None


async def backfill(summaries_only: bool, fetch_bodies: bool, limit: Optional[int], dry_run: bool):
    async with AsyncSessionLocal() as session:
        # 1. Fetch all email tasks and their audit logs
        logger.info("Finding email-generated tasks in database...")
        query = (
            select(Issue, AuditLog.details, AuditLog.user_id)
            .join(AuditLog, AuditLog.entity_id == Issue.id)
            .where(AuditLog.action.like("email.task_created%"))
            .order_by(Issue.created_at.desc())
        )
        if limit:
            query = query.limit(limit)

        result = await session.execute(query)
        records = result.all()
        logger.info(f"Found {len(records)} email-created tasks to process.")

        if not records:
            logger.info("No tasks found to backfill.")
            return

        # Prepare IMAP connection if needed
        imap_clients: Dict[str, IMAP4_SSL] = {}
        if fetch_bodies:
            logger.info("Initializing IMAP connections for user(s)...")
            users_query = await session.execute(select(User).where(User.oauth_access_token.isnot(None)))
            users = users_query.scalars().all()
            for u in users:
                token = await refresh_token_v2(session, u)
                if token:
                    imap = await get_imap_connection(u, token)
                    if imap:
                        imap_clients[str(u.id)] = imap
                        logger.info(f"Connected to IMAP for user {u.email}")

        summaries_created = 0
        bodies_restored = 0
        skipped = 0

        for idx, (issue, audit_details, user_id) in enumerate(records, 1):
            details = audit_details or {}
            message_id = details.get("message_id")
            email_subject = details.get("email_subject")
            current_desc = issue.description or ""

            # Check existing summary
            existing_summary = await crud_issue_summary.get_by_issue_id(session, issue.id)

            # 1. Ensure IssueSummary exists with the AI summary
            if not existing_summary and current_desc:
                if not dry_run:
                    content_hash = crud_issue.get_content_hash(f"{issue.title} {current_desc}")
                    await crud_issue_summary.upsert(
                        session,
                        issue_id=issue.id,
                        summary=current_desc,
                        next_steps="",
                        content_hash=content_hash,
                    )
                summaries_created += 1

            # 2. If fetch_bodies requested, try retrieving original body
            if fetch_bodies and not summaries_only:
                imap = imap_clients.get(str(user_id))
                if imap:
                    logger.info(f"[{idx}/{len(records)}] Fetching email body for '{issue.title[:40]}'...")
                    body = await fetch_body_for_task(imap, message_id, email_subject)
                    if body:
                        if not dry_run:
                            issue.description = body
                            # Update content hash on summary so it remains in sync
                            summary_text = existing_summary.summary if existing_summary else current_desc
                            new_content_hash = crud_issue.get_content_hash(f"{issue.title} {body}")
                            await crud_issue_summary.upsert(
                                session,
                                issue_id=issue.id,
                                summary=summary_text,
                                next_steps="",
                                content_hash=new_content_hash,
                            )
                        bodies_restored += 1
                        logger.info(f" -> Restored original body ({len(body)} chars)")
                    else:
                        logger.warning(f" -> Could not locate email in mailbox for '{issue.title[:40]}'")
                else:
                    logger.warning(f"No IMAP client available for user_id={user_id}")

            # Periodic commit
            if not dry_run and idx % 25 == 0:
                await session.commit()
                logger.info(f"Committed progress ({idx}/{len(records)})...")

            # Small delay between IMAP fetches to be courteous to email servers
            if fetch_bodies:
                await asyncio.sleep(0.1)

        if not dry_run:
            await session.commit()

        # Close any open IMAP connections
        for client in imap_clients.values():
            try:
                await client.logout()
            except Exception:
                pass

        logger.info("=" * 60)
        logger.info("Backfill complete summary:")
        logger.info(f"  Total tasks processed: {len(records)}")
        logger.info(f"  AI summaries populated into IssueSummary: {summaries_created}")
        if fetch_bodies:
            logger.info(f"  Original email bodies restored into description: {bodies_restored}")
        if dry_run:
            logger.info("  (Dry run mode - no database changes were committed)")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Backfill existing email tasks in Nimbus.")
    parser.add_argument("--summaries-only", action="store_true", help="Only backfill IssueSummary from existing description")
    parser.add_argument("--fetch-bodies", action="store_true", help="Connect to IMAP and fetch original email bodies into description")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tasks to process")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing changes")

    args = parser.parse_args()

    # Default to summaries-only if fetch-bodies is not explicitly set
    if not args.fetch_bodies and not args.summaries_only:
        args.summaries_only = True

    asyncio.run(backfill(args.summaries_only, args.fetch_bodies, args.limit, args.dry_run))


if __name__ == "__main__":
    main()
