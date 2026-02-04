from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_user
from app.schemas.user import User, UserCreate, UserCreatePublic, UserSelfUpdate

router = APIRouter()

@router.get("/", response_model=List[User])
async def read_users(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve users.
    """
    users = await crud_user.get_multi(db, skip=skip, limit=limit)
    return users

@router.post("/", response_model=User)
async def create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreatePublic,
) -> Any:
    """
    Create new user.
    """
    user = await crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )
    user = await crud_user.create(
        db,
        obj_in=UserCreate(
            email=user_in.email,
            password=user_in.password,
            full_name=user_in.full_name,
            is_superuser=False,
            role="member",
            is_active=True,
            timezone=user_in.timezone or "UTC",
        ),
    )
    return user

@router.get("/me", response_model=User)
async def read_user_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current user.
    """
    return current_user

@router.patch("/me", response_model=User)
async def update_user_me(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserSelfUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update own user.
    """
    update_data = user_in.dict(exclude_unset=True)
    # Check if we need to verify email uniqueness if email is being updated (omitted for brevity unless needed)
    user = await crud_user.update(db, db_obj=current_user, obj_in=update_data)
    return user
