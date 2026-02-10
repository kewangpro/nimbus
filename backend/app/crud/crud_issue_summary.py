from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.issue_summary import IssueSummary


async def get_by_issue_id(db: AsyncSession, issue_id: UUID) -> Optional[IssueSummary]:
    result = await db.execute(select(IssueSummary).where(IssueSummary.issue_id == issue_id))
    return result.scalars().first()


async def upsert(
    db: AsyncSession,
    *,
    issue_id: UUID,
    summary: str,
    next_steps: str,
    content_hash: str,
) -> IssueSummary:
    existing = await get_by_issue_id(db, issue_id)
    if existing:
        existing.summary = summary
        existing.next_steps = next_steps
        existing.content_hash = content_hash
        db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    obj = IssueSummary(
        issue_id=issue_id,
        summary=summary,
        next_steps=next_steps,
        content_hash=content_hash,
    )
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj
