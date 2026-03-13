import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_issue, crud_project
from app.schemas.project import ProjectCreate
import uuid

# Helper to ensure project exists for issue creation
async def get_test_project(db: AsyncSession, owner_id: uuid.UUID):
    name = f"API Issue Project {uuid.uuid4()}"
    p_in = ProjectCreate(name=name)
    return await crud_project.create(db, obj_in=p_in, owner_id=owner_id)

@pytest.mark.asyncio
async def test_create_issue(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    project = await get_test_project(db, user.id)
    
    title = f"API Issue {uuid.uuid4()}"
    description = "API Description"
    data = {
        "title": title,
        "description": description,
        "project_id": str(project.id)
    }
    
    r = await client.post(
        "/api/v1/issues/", headers=normal_user_token_headers, json=data
    )
    assert r.status_code == 200
    issue = r.json()
    assert issue["title"] == title
    assert issue["description"] == description
    assert issue["project_id"] == str(project.id)

@pytest.mark.asyncio
async def test_read_issues(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    project = await get_test_project(db, user.id)
    
    title = f"API Issue {uuid.uuid4()}"
    client_response = await client.post(
        "/api/v1/issues/", 
        headers=normal_user_token_headers, 
        json={"title": title, "project_id": str(project.id)}
    )
    assert client_response.status_code == 200
    
    r = await client.get("/api/v1/issues/", headers=normal_user_token_headers)
    assert r.status_code == 200
    issues = r.json()
    assert isinstance(issues, list)
    assert len(issues) >= 1
    assert any(i["title"] == title for i in issues)

@pytest.mark.asyncio
async def test_read_issue(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    project = await get_test_project(db, user.id)
    
    title = f"API Issue {uuid.uuid4()}"
    create_r = await client.post(
        "/api/v1/issues/", 
        headers=normal_user_token_headers, 
        json={"title": title, "project_id": str(project.id)}
    )
    issue_id = create_r.json()["id"]
    
    r = await client.get(
        f"/api/v1/issues/{issue_id}", headers=normal_user_token_headers
    )
    assert r.status_code == 200
    issue = r.json()
    assert issue["id"] == issue_id
    assert issue["title"] == title

@pytest.mark.asyncio
async def test_update_issue(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    project = await get_test_project(db, user.id)
    
    title = f"API Issue {uuid.uuid4()}"
    create_r = await client.post(
        "/api/v1/issues/", 
        headers=normal_user_token_headers, 
        json={"title": title, "project_id": str(project.id)}
    )
    issue_id = create_r.json()["id"]
    
    new_title = f"Updated API Issue {uuid.uuid4()}"
    data = {"title": new_title}
    r = await client.patch(
        f"/api/v1/issues/{issue_id}", headers=normal_user_token_headers, json=data
    )
    assert r.status_code == 200
    issue = r.json()
    assert issue["id"] == issue_id
    assert issue["title"] == new_title

@pytest.mark.asyncio
async def test_delete_issue(
    client: AsyncClient, normal_user_token_headers: dict, db: AsyncSession
) -> None:
    from app.crud.crud_user import get_by_email
    user = await get_by_email(db, email="user@example.com")
    project = await get_test_project(db, user.id)
    
    title = f"API Issue {uuid.uuid4()}"
    create_r = await client.post(
        "/api/v1/issues/", 
        headers=normal_user_token_headers, 
        json={"title": title, "project_id": str(project.id)}
    )
    issue_id = create_r.json()["id"]
    
    r = await client.delete(
        f"/api/v1/issues/{issue_id}", headers=normal_user_token_headers
    )
    assert r.status_code == 200
    
    verify_r = await client.get(
        f"/api/v1/issues/{issue_id}", headers=normal_user_token_headers
    )
    assert verify_r.status_code == 404
