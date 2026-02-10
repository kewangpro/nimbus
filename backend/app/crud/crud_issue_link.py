from typing import Iterable, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from app.models.issue import Issue
from app.models.issue_link import IssueLink


async def get_dependencies(db: AsyncSession, issue_id: UUID) -> List[Issue]:
    stmt = (
        select(Issue)
        .join(IssueLink, IssueLink.depends_on_id == Issue.id)
        .where(IssueLink.issue_id == issue_id)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def set_dependencies(db: AsyncSession, issue_id: UUID, depends_on_ids: Iterable[UUID]) -> None:
    await db.execute(delete(IssueLink).where(IssueLink.issue_id == issue_id))
    for dep_id in depends_on_ids:
        db.add(IssueLink(issue_id=issue_id, depends_on_id=dep_id))
    await db.commit()
