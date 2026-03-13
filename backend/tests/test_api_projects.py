import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_project
from app.schemas.project import ProjectCreate
import uuid

@pytest.mark.asyncio
async def test_read_projects(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    # Get current user id from headers - normal user is created in conftest
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    # Create an extra project explicitly
    name = f"API Project {uuid.uuid4()}"
    p_in = ProjectCreate(name=name)
    await crud_project.create(db, obj_in=p_in, owner_id=user.id)

    r = await client.get("/api/v1/projects/", headers=normal_user_token_headers)
    assert r.status_code == 200
    projects = r.json()
    assert isinstance(projects, list)
    # The endpoint auto-creates "General", plus our explicit project
    assert len(projects) >= 2 
    assert any(p["name"] == name for p in projects)
    assert any(p["name"] == "General" for p in projects)

@pytest.mark.asyncio
async def test_create_project(
    client: AsyncClient, normal_user_token_headers: dict
) -> None:
    name = f"New API Project {uuid.uuid4()}"
    description = "New Description"
    data = {"name": name, "description": description}
    
    r = await client.post(
        "/api/v1/projects/", headers=normal_user_token_headers, json=data
    )
    assert r.status_code == 200
    project = r.json()
    assert project["name"] == name
    assert project["description"] == description

@pytest.mark.asyncio
async def test_read_project(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    name = f"API Project {uuid.uuid4()}"
    p_in = ProjectCreate(name=name)
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)
    
    r = await client.get(
        f"/api/v1/projects/{project.id}", headers=normal_user_token_headers
    )
    assert r.status_code == 200
    p2 = r.json()
    assert p2["id"] == str(project.id)
    assert p2["name"] == name

@pytest.mark.asyncio
async def test_update_project(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    name = f"API Project {uuid.uuid4()}"
    p_in = ProjectCreate(name=name)
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)
    
    new_name = f"Updated API Project {uuid.uuid4()}"
    data = {"name": new_name}
    r = await client.patch(
        f"/api/v1/projects/{project.id}", headers=normal_user_token_headers, json=data
    )
    assert r.status_code == 200
    p2 = r.json()
    assert p2["id"] == str(project.id)
    assert p2["name"] == new_name

@pytest.mark.asyncio
async def test_delete_project(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    
    name = f"API Project {uuid.uuid4()}"
    p_in = ProjectCreate(name=name)
    project = await crud_project.create(db, obj_in=p_in, owner_id=user.id)
    
    r = await client.delete(
        f"/api/v1/projects/{project.id}", headers=normal_user_token_headers
    )
    assert r.status_code == 200
    p2 = r.json()
    assert p2["id"] == str(project.id)
    
    # Verify it's actually deleted
    r2 = await client.get(
        f"/api/v1/projects/{project.id}", headers=normal_user_token_headers
    )
    assert r2.status_code == 404
