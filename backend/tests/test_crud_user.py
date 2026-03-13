import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_user
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import verify_password
import uuid

@pytest.mark.asyncio
async def test_create_user(db: AsyncSession) -> None:
    email = f"test_{uuid.uuid4()}@example.com"
    password = "testpassword"
    user_in = UserCreate(email=email, password=password, full_name="Test User")
    user = await crud_user.create(db, obj_in=user_in)
    
    assert user.email == email
    assert hasattr(user, "hashed_password")
    assert user.full_name == "Test User"
    assert verify_password(password, user.hashed_password)

@pytest.mark.asyncio
async def test_authenticate_user(db: AsyncSession) -> None:
    email = f"auth_{uuid.uuid4()}@example.com"
    password = "authpassword"
    user_in = UserCreate(email=email, password=password)
    user = await crud_user.create(db, obj_in=user_in)
    
    authenticated_user = await crud_user.authenticate(db, email=email, password=password)
    assert authenticated_user is not None
    assert authenticated_user.email == email

@pytest.mark.asyncio
async def test_not_authenticate_user_wrong_password(db: AsyncSession) -> None:
    email = f"auth_{uuid.uuid4()}@example.com"
    password = "authpassword"
    user_in = UserCreate(email=email, password=password)
    await crud_user.create(db, obj_in=user_in)
    
    user = await crud_user.authenticate(db, email=email, password="wrongpassword")
    assert user is None

@pytest.mark.asyncio
async def test_not_authenticate_user_not_exist(db: AsyncSession) -> None:
    user = await crud_user.authenticate(db, email="notexist@example.com", password="password")
    assert user is None

@pytest.mark.asyncio
async def test_get_user_by_email(db: AsyncSession) -> None:
    email = f"get_{uuid.uuid4()}@example.com"
    password = "getpassword"
    user_in = UserCreate(email=email, password=password)
    user = await crud_user.create(db, obj_in=user_in)
    
    user_2 = await crud_user.get_by_email(db, email=email)
    assert user_2 is not None
    assert user.id == user_2.id
    assert user.email == user_2.email

@pytest.mark.asyncio
async def test_update_user(db: AsyncSession) -> None:
    email = f"update_{uuid.uuid4()}@example.com"
    password = "updatepassword"
    user_in = UserCreate(email=email, password=password)
    user = await crud_user.create(db, obj_in=user_in)
    
    new_full_name = "Updated User"
    new_password = "newpassword"
    user_update = UserUpdate(full_name=new_full_name, password=new_password)
    user_2 = await crud_user.update(db, db_obj=user, obj_in=user_update)
    
    assert user_2.full_name == new_full_name
    assert verify_password(new_password, user_2.hashed_password)
    
@pytest.mark.asyncio
async def test_create_or_update_oauth(db: AsyncSession) -> None:
    email = f"oauth_{uuid.uuid4()}@example.com"
    full_name = "OAuth User"
    provider = "google"
    oauth_id = "12345"
    access_token = "tok_123"
    
    # Create new
    user = await crud_user.create_or_update_oauth(
        db, email=email, full_name=full_name, provider=provider, 
        oauth_id=oauth_id, access_token=access_token
    )
    assert user.email == email
    assert user.oauth_provider == provider
    assert user.oauth_access_token == access_token
    assert user.full_name == full_name
    
    # Update existing
    new_access_token = "tok_456"
    user_2 = await crud_user.create_or_update_oauth(
        db, email=email, full_name=full_name, provider="microsoft", 
        oauth_id="54321", access_token=new_access_token
    )
    assert user_2.id == user.id
    assert user_2.oauth_access_token == new_access_token
    assert user_2.oauth_provider == "microsoft"

@pytest.mark.asyncio
async def test_get_multi_users(db: AsyncSession) -> None:
    # Ensure there's at least one user
    email = f"multi_{uuid.uuid4()}@example.com"
    user_in = UserCreate(email=email, password="password")
    await crud_user.create(db, obj_in=user_in)
    
    users = await crud_user.get_multi(db, skip=0, limit=10)
    assert len(users) >= 1
    assert any(u.email == email for u in users)
