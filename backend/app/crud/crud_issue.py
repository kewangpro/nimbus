from typing import List, Optional
from uuid import UUID
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.issue import Issue
from app.schemas.issue import IssueCreate, IssueUpdate
from app.core import ai
from app.crud import crud_embedding

def get_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

async def get(db: AsyncSession, id: UUID) -> Optional[Issue]:
    result = await db.execute(select(Issue).where(Issue.id == id))
    return result.scalars().first()

async def get_multi(
    db: AsyncSession, *, skip: int = 0, limit: int = 100, owner_id: Optional[UUID] = None
) -> List[Issue]:
    query = select(Issue).offset(skip).limit(limit)
    if owner_id:
        query = query.where(Issue.owner_id == owner_id)
    result = await db.execute(query)
    return result.scalars().all()

async def create(db: AsyncSession, *, obj_in: IssueCreate, owner_id: UUID) -> Issue:
    db_obj = Issue(
        title=obj_in.title,
        description=obj_in.description,
        status=obj_in.status,
        priority=obj_in.priority,
        assignee_id=obj_in.assignee_id,
        due_date=obj_in.due_date,
        owner_id=owner_id
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)

    # Generate Embedding
    full_text = f"{db_obj.title} {db_obj.description or ''}"
    content_hash = get_content_hash(full_text)
    embedding = await ai.generate_embedding(full_text)
    
    if embedding:
        await crud_embedding.create_or_update(
            db, issue_id=db_obj.id, embedding=embedding, content_hash=content_hash
        )

    return db_obj

async def update(
    db: AsyncSession, *, db_obj: Issue, obj_in: IssueUpdate
) -> Issue:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)

    # Update Embedding if content changed
    if "title" in update_data or "description" in update_data:
        full_text = f"{db_obj.title} {db_obj.description or ''}"
        content_hash = get_content_hash(full_text)
        # Check if hash is new? Optimization: Retrieve existing embedding first.
        # For simplicity, we just regen. RAG pipeline usually checks hash.
        embedding = await ai.generate_embedding(full_text)
        if embedding:
            await crud_embedding.create_or_update(
                db, issue_id=db_obj.id, embedding=embedding, content_hash=content_hash
            )

    return db_obj

async def remove(db: AsyncSession, *, id: UUID) -> Issue:
    result = await db.execute(select(Issue).where(Issue.id == id))
    obj = result.scalars().first()
    await db.delete(obj)
    await db.commit()
    return obj
