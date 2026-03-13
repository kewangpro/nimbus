import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud import crud_project
from app.schemas.project import ProjectCreate, ProjectUpdate
import uuid

@pytest.mark.asyncio
async def test_create_project(db: AsyncSession) -> None:
    name = f"Test Project {uuid.uuid4()}"
    description = "Test Description"
    project_in = ProjectCreate(name=name, description=description)
    project = await crud_project.create(db, obj_in=project_in)
    
    assert project.name == name
    assert project.description == description
    assert project.id is not None

@pytest.mark.asyncio
async def test_get_project(db: AsyncSession) -> None:
    name = f"Test Project {uuid.uuid4()}"
    project_in = ProjectCreate(name=name)
    project = await crud_project.create(db, obj_in=project_in)
    
    project_2 = await crud_project.get(db, id=project.id)
    assert project_2 is not None
    assert project.id == project_2.id
    assert project.name == project_2.name

@pytest.mark.asyncio
async def test_get_project_by_name(db: AsyncSession) -> None:
    name = f"Test Project {uuid.uuid4()}"
    project_in = ProjectCreate(name=name)
    project = await crud_project.create(db, obj_in=project_in)
    
    project_2 = await crud_project.get_by_name(db, name=project.name)
    assert project_2 is not None
    assert project.id == project_2.id
    assert project.name == project_2.name

@pytest.mark.asyncio
async def test_get_multi_projects(db: AsyncSession) -> None:
    name = f"Test Project {uuid.uuid4()}"
    project_in = ProjectCreate(name=name)
    await crud_project.create(db, obj_in=project_in)
    
    projects = await crud_project.get_multi(db, skip=0, limit=10)
    assert len(projects) >= 1
    assert any(p.name == name for p in projects)

@pytest.mark.asyncio
async def test_update_project(db: AsyncSession) -> None:
    name = f"Test Project {uuid.uuid4()}"
    project_in = ProjectCreate(name=name)
    project = await crud_project.create(db, obj_in=project_in)
    
    new_name = f"Updated Project {uuid.uuid4()}"
    new_description = "Updated Description"
    project_update = ProjectUpdate(name=new_name, description=new_description)
    project_2 = await crud_project.update(db, db_obj=project, obj_in=project_update)
    
    assert project_2.id == project.id
    assert project_2.name == new_name
    assert project_2.description == new_description

@pytest.mark.asyncio
async def test_remove_project(db: AsyncSession) -> None:
    name = f"Test Project {uuid.uuid4()}"
    project_in = ProjectCreate(name=name)
    project = await crud_project.create(db, obj_in=project_in)
    
    project_2 = await crud_project.remove(db, id=project.id)
    assert project_2.id == project.id
    
    project_3 = await crud_project.get(db, id=project.id)
    assert project_3 is None
