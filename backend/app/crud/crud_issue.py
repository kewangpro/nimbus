from typing import List, Optional
from uuid import UUID
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.issue import Issue
from app.schemas.issue import IssueCreate, IssueUpdate
from app.core import ai
from app.crud import crud_embedding, crud_project, crud_label

from sqlalchemy.orm import joinedload, selectinload

def get_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

async def get(db: AsyncSession, id: UUID) -> Optional[Issue]:
    result = await db.execute(
        select(Issue).options(
            joinedload(Issue.project),
            joinedload(Issue.assignee),
            selectinload(Issue.labels),
        ).where(Issue.id == id)
    )
    return result.scalars().first()

async def get_multi(
    db: AsyncSession, *, skip: int = 0, limit: int = 100, owner_id: Optional[UUID] = None, project_id: Optional[UUID] = None, assignee_id: Optional[UUID] = None
) -> List[Issue]:
    query = select(Issue).options(
        joinedload(Issue.project),
        joinedload(Issue.assignee),
        selectinload(Issue.labels)
    ).offset(skip).limit(limit)
    
    if owner_id:
        query = query.where(Issue.owner_id == owner_id)
    if project_id:
        query = query.where(Issue.project_id == project_id)
    if assignee_id:
        query = query.where(Issue.assignee_id == assignee_id)
        
    result = await db.execute(query)
    return result.scalars().all()

async def create(db: AsyncSession, *, obj_in: IssueCreate, owner_id: UUID) -> Issue:
    # Handle Default Project
    project_id = obj_in.project_id
    if not project_id:
        general_project = await crud_project.get_by_name(db, name="General")
        if general_project:
            project_id = general_project.id
        else:
            # Fallback
            from app.schemas.project import ProjectCreate
            new_proj = await crud_project.create(db, obj_in=ProjectCreate(name="General", description="Default project"))
            project_id = new_proj.id

    db_obj = Issue(
        title=obj_in.title,
        description=obj_in.description,
        status=obj_in.status,
        priority=obj_in.priority,
        assignee_id=obj_in.assignee_id,
        due_date=obj_in.due_date,
        owner_id=owner_id,
        project_id=project_id
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)

    if obj_in.labels:
        await crud_label.set_issue_labels(db, db_obj.id, obj_in.labels)
    # Generate Embedding
    full_text = f"{db_obj.title} {db_obj.description or ''}"
    content_hash = get_content_hash(full_text)
    embedding = await ai.generate_embedding(full_text)
    
    if embedding:
        await crud_embedding.create_or_update(
            db, issue_id=db_obj.id, embedding=embedding, content_hash=content_hash
        )

    # Return refreshed object with relationships
    return await get(db, db_obj.id)

async def update(
    db: AsyncSession, *, db_obj: Issue, obj_in: IssueUpdate
) -> Issue:
    update_data = obj_in.model_dump(exclude_unset=True)
    labels = update_data.pop("labels", None)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    await db.commit()
    # No refresh here, we do full reload below
    
    # Update Embedding if content changed
    if "title" in update_data or "description" in update_data:
        full_text = f"{db_obj.title} {db_obj.description or ''}"
        content_hash = get_content_hash(full_text)
        embedding = await ai.generate_embedding(full_text)
        if embedding:
            await crud_embedding.create_or_update(
                db, issue_id=db_obj.id, embedding=embedding, content_hash=content_hash
            )

    if labels is not None:
        await crud_label.set_issue_labels(db, db_obj.id, labels)

    # Return refreshed object with relationships
    return await get(db, db_obj.id)

async def remove(db: AsyncSession, *, id: UUID) -> Issue:
    result = await db.execute(select(Issue).where(Issue.id == id))
    obj = result.scalars().first()
    await db.delete(obj)
    await db.commit()
    return obj
