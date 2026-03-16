import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
from unittest.mock import MagicMock

# Mock mcp if not installed to allow tests to run
try:
    import mcp
except ImportError:
    mcp_mock = MagicMock()
    sys.modules["mcp"] = mcp_mock
    sys.modules["mcp.server"] = mcp_mock
    sys.modules["mcp.server.fastmcp"] = mcp_mock

from app.main import app
from app.api.deps import get_db
from app.db.base import Base
# Import models to ensure they are registered with Base
from app.models.user import User
from app.models.project import Project
from app.models.issue import Issue
from app.models.audit_log import AuditLog

# Use SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, class_=AsyncSession, expire_on_commit=False
)



@pytest_asyncio.fixture(scope="function")
async def db_engine():


    async with engine.begin() as conn:
        # We need to skip models that use pgvector if we use SQLite
        # For now, let's try to create all and see if it fails
        try:
            await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(f"Warning: Could not create some tables: {e}")
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:

    async with TestingSessionLocal() as session:
        yield session
        # Rollback everything after test
        await session.rollback()

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        yield ac
    app.dependency_overrides.clear()
@pytest_asyncio.fixture
async def normal_user_token_headers(db: AsyncSession) -> dict:
    from app.core.security import create_access_token
    # Create test user
    user = User(
        email="user@example.com",
        full_name="Normal User",
        hashed_password="hashed_password",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    token = create_access_token(user.email)
    return {"Authorization": f"Bearer {token}"}
