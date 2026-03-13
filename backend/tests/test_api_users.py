import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_user
from app.schemas.user import UserCreate
import uuid

@pytest.mark.asyncio
async def test_read_users(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    # Ensure there is at least one other user
    email = f"api_user_{uuid.uuid4()}@example.com"
    user_in = UserCreate(email=email, password="password", full_name="API User")
    await crud_user.create(db, obj_in=user_in)

    r = await client.get("/api/v1/users/", headers=normal_user_token_headers)
    assert r.status_code == 200
    users = r.json()
    assert isinstance(users, list)
    assert len(users) >= 2 # normal_user + the one we just created
    assert any(u["email"] == email for u in users)

@pytest.mark.asyncio
async def test_read_user_me(
    client: AsyncClient, normal_user_token_headers: dict
) -> None:
    r = await client.get("/api/v1/users/me", headers=normal_user_token_headers)
    assert r.status_code == 200
    user = r.json()
    assert user["email"] == "user@example.com" # Default created in conftest
    assert user["full_name"] == "Normal User"

@pytest.mark.asyncio
async def test_update_user_me(
    client: AsyncClient, normal_user_token_headers: dict
) -> None:
    new_full_name = f"Updated API User {uuid.uuid4()}"
    data = {"full_name": new_full_name, "timezone": "Asia/Tokyo"}
    
    r = await client.patch(
        "/api/v1/users/me", headers=normal_user_token_headers, json=data
    )
    assert r.status_code == 200
    user = r.json()
    assert user["full_name"] == new_full_name
    assert user["timezone"] == "Asia/Tokyo"
