from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.embedding import IssueEmbedding
from pgvector.sqlalchemy import Vector

async def get(db: AsyncSession, issue_id: UUID) -> Optional[IssueEmbedding]:
    result = await db.execute(select(IssueEmbedding).where(IssueEmbedding.issue_id == issue_id))
    return result.scalars().first()

async def create_or_update(
    db: AsyncSession, *, issue_id: UUID, embedding: list[float], content_hash: str
) -> IssueEmbedding:
    obj = await get(db, issue_id)
    if obj:
        obj.embedding = embedding
        obj.content_hash = content_hash
    else:
        obj = IssueEmbedding(issue_id=issue_id, embedding=embedding, content_hash=content_hash)
        db.add(obj)
    
    await db.commit()
    await db.refresh(obj)
    return obj

async def search_similar(
    db: AsyncSession, *, embedding: list[float], limit: int = 5
) -> list[IssueEmbedding]:
    # Using cosine distance operator <=>
    stmt = select(IssueEmbedding).order_by(IssueEmbedding.embedding.cosine_distance(embedding)).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
