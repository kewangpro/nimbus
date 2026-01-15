from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate

async def get_multi(
    db: AsyncSession, *, skip: int = 0, limit: int = 100
) -> List[User]:
    query = select(User).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_by_email(db: AsyncSession, *, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def create(db: AsyncSession, *, obj_in: UserCreate) -> User:
    db_obj = User(
        email=obj_in.email,
        hashed_password=get_password_hash(obj_in.password),
        full_name=obj_in.full_name,
        is_superuser=obj_in.is_superuser,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def authenticate(
    db: AsyncSession, *, email: str, password: str
) -> Optional[User]:
    user = await get_by_email(db, email=email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
