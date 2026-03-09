from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_project
from app.schemas.project import Project, ProjectCreate, ProjectUpdate
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[Project])
async def read_projects(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve projects for the current user. Ensures 'General' and 'Email' exist.
    """
    from sqlalchemy import select
    from app.models.project import Project as ProjectModel
    
    # 1. Ensure "General" and "Email" projects exist for this user
    async def ensure_project(name: str):
        p_query = select(ProjectModel).where(ProjectModel.owner_id == current_user.id, ProjectModel.name == name)
        p_result = await db.execute(p_query)
        p = p_result.scalars().first()
        if not p:
            print(f"INFO: Creating missing {name} project for user {current_user.email}")
            p_in = ProjectCreate(name=name, description=f"Your {name.lower()} workspace")
            p = await crud_project.create(db, obj_in=p_in, owner_id=current_user.id)
        return p

    await ensure_project("General")
    await ensure_project("Email")

    # 2. Fetch all projects for this user
    query = select(ProjectModel).where(ProjectModel.owner_id == current_user.id).offset(skip).limit(limit)
    result = await db.execute(query)
    projects = result.scalars().all()
    return projects


@router.post("/", response_model=Project)
async def create_project(
    *,
    db: AsyncSession = Depends(deps.get_db),
    project_in: ProjectCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create new project.
    """
    project = await crud_project.create(db=db, obj_in=project_in, owner_id=current_user.id)
    return project

@router.get("/{id}", response_model=Project)
async def read_project(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get project by ID.
    """
    project = await crud_project.get(db=db, id=id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.patch("/{id}", response_model=Project)
async def update_project(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    project_in: ProjectUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update a project.
    """
    project = await crud_project.get(db=db, id=id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project = await crud_project.update(db=db, db_obj=project, obj_in=project_in)
    return project

@router.delete("/{id}", response_model=Project)
async def delete_project(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Delete a project.
    """
    project = await crud_project.get(db=db, id=id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project = await crud_project.remove(db=db, id=id)
    return project
