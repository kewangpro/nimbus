from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.label import Label
from app.models.issue import Issue


def _normalize_label(name: str) -> str:
    return name.strip().lower()


async def get_by_name(db: AsyncSession, name: str) -> Optional[Label]:
    normalized = _normalize_label(name)
    result = await db.execute(select(Label).where(Label.name == normalized))
    return result.scalars().first()


async def get_or_create(db: AsyncSession, name: str) -> Label:
    normalized = _normalize_label(name)
    result = await db.execute(select(Label).where(Label.name == normalized))
    label = result.scalars().first()
    if label:
        return label
    label = Label(name=normalized)
    db.add(label)
    await db.commit()
    await db.refresh(label)
    return label


async def set_issue_labels(db: AsyncSession, issue_id: UUID, labels: Iterable[str]) -> Optional[Issue]:
    label_names = [_normalize_label(name) for name in labels if name and _normalize_label(name)]
    label_names = list(dict.fromkeys(label_names))  # de-dup while preserving order

    result = await db.execute(
        select(Issue).options(selectinload(Issue.labels)).where(Issue.id == issue_id)
    )
    issue = result.scalars().first()
    if not issue:
        return None

    label_objs: List[Label] = []
    for name in label_names:
        label_objs.append(await get_or_create(db, name))

    issue.labels = label_objs
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return issue
