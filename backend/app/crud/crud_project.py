from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

async def get(db: AsyncSession, id: UUID) -> Optional[Project]:
    result = await db.execute(select(Project).where(Project.id == id))
    return result.scalars().first()

async def get_by_name(db: AsyncSession, name: str) -> Optional[Project]:
    result = await db.execute(select(Project).where(Project.name == name))
    return result.scalars().first()

async def get_multi(
    db: AsyncSession, *, skip: int = 0, limit: int = 100
) -> List[Project]:
    query = select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def create(db: AsyncSession, *, obj_in: ProjectCreate, owner_id: Optional[UUID] = None) -> Project:
    db_obj = Project(
        name=obj_in.name,
        description=obj_in.description,
        owner_id=owner_id
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def update(
    db: AsyncSession, *, db_obj: Project, obj_in: ProjectUpdate
) -> Project:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def remove(db: AsyncSession, *, id: UUID) -> Project:
    result = await db.execute(select(Project).where(Project.id == id))
    obj = result.scalars().first()
    await db.delete(obj)
    await db.commit()
    return obj
