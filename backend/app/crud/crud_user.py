from datetime import datetime
from typing import List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.encoders import jsonable_encoder
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

async def update(
    db: AsyncSession, *, db_obj: User, obj_in: Union[UserCreate, dict]
) -> User:
    obj_data = jsonable_encoder(db_obj)
    if isinstance(obj_in, dict):
        update_data = obj_in
    else:
        update_data = obj_in.dict(exclude_unset=True)
        
    if update_data.get("password"):
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password

    for field in obj_data:
        if field in update_data:
            setattr(db_obj, field, update_data[field])

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

async def create_or_update_oauth(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    provider: str,
    oauth_id: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[datetime] = None
) -> User:
    user = await get_by_email(db, email=email)
    if user:
        user.oauth_provider = provider
        user.oauth_id = oauth_id
        user.oauth_access_token = access_token
        if refresh_token:
            user.oauth_refresh_token = refresh_token
        if expires_at:
            user.oauth_token_expires_at = expires_at
        if not user.full_name:
            user.full_name = full_name
    else:
        user = User(
            email=email,
            full_name=full_name,
            oauth_provider=provider,
            oauth_id=oauth_id,
            oauth_access_token=access_token,
            oauth_refresh_token=refresh_token,
            oauth_token_expires_at=expires_at,
            is_active=True,
        )
        db.add(user)
    
    await db.commit()
    await db.refresh(user)
    return user

