import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_user
from app.schemas.user import UserCreate
from datetime import datetime, timedelta

@pytest.mark.asyncio
async def test_create_or_update_oauth_user(db: AsyncSession):
    email = "oauth-test@example.com"
    full_name = "OAuth Tester"
    provider = "gmail"
    oauth_id = "google-123"
    access_token = "atk-123"
    expires_at = datetime.utcnow() + timedelta(hours=1)

    # 1. Create new user via OAuth
    user = await crud_user.create_or_update_oauth(
        db,
        email=email,
        full_name=full_name,
        provider=provider,
        oauth_id=oauth_id,
        access_token=access_token,
        expires_at=expires_at
    )

    assert user.email == email
    assert user.oauth_provider == provider
    assert user.oauth_id == oauth_id
    assert user.oauth_access_token == access_token
    assert user.is_active is True

    # 2. Update existing user via OAuth
    new_token = "atk-456"
    updated_user = await crud_user.create_or_update_oauth(
        db,
        email=email,
        full_name=full_name,
        provider=provider,
        oauth_id=oauth_id,
        access_token=new_token,
        expires_at=expires_at
    )

    assert updated_user.id == user.id
    assert updated_user.oauth_access_token == new_token
