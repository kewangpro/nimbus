from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_user, crud_audit
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
    # Track changes
    old_data = {
        "full_name": current_user.full_name,
        "email_automation_enabled": current_user.email_automation_enabled,
        "timezone": current_user.timezone,
    }
    
    user = await crud_user.update(db, db_obj=current_user, obj_in=update_data)
    
    changes = []
    for field, old_val in old_data.items():
        if field in update_data and update_data[field] != old_val:
            changes.append(field)
    if "password" in update_data:
        changes.append("password")

    await crud_audit.log_action(
        db, 
        "user.update_me", 
        current_user.id, 
        "user", 
        user.id,
        details={"changes": changes}
    )
    return user
