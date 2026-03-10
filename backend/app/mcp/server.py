import asyncio
import os
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select, and_

from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.issue import Issue
from app.models.user import User
from app.crud import crud_issue, crud_project
from app.schemas.issue import IssueCreate, IssueUpdate

# Initialize FastMCP server
mcp = FastMCP("Nimbus Calendar")

async def get_default_user_id() -> UUID:
    """Gets the ID of the primary user."""
    async with AsyncSessionLocal() as db:
        # Try to find user by email from env or default
        email = os.getenv("NIMBUS_USER_EMAIL", "winkywk@hotmail.com")
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalars().first()
        if not user:
            # Fallback to first user
            res = await db.execute(select(User).limit(1))
            user = res.scalars().first()
        
        if not user:
            raise Exception("No users found in database")
        return user.id

@mcp.tool()
async def list_calendar_events(days: int = 7) -> str:
    """
    List all tasks that have a due date within the specified number of days.
    """
    user_id = await get_default_user_id()
    async with AsyncSessionLocal() as db:
        # Fetch issues with due_date
        query = select(Issue).where(
            and_(
                Issue.owner_id == user_id,
                Issue.due_date.isnot(None)
            )
        ).order_by(Issue.due_date)
        
        result = await db.execute(query)
        issues = result.scalars().all()
        
        if not issues:
            return "No tasks found on the calendar."
        
        lines = ["# Calendar Tasks:"]
        for issue in issues:
            due_str = issue.due_date.strftime("%Y-%m-%d %H:%M") if issue.due_date else "N/A"
            lines.append(f"- [{issue.status}] {issue.title} (Due: {due_str}) ID: {issue.id}")
        
        return "\n".join(lines)

@mcp.tool()
async def get_task_details(task_id: str) -> str:
    """
    Get full details of a specific task by its ID.
    """
    try:
        task_uuid = UUID(task_id)
    except ValueError:
        return f"Error: '{task_id}' is not a valid UUID."

    async with AsyncSessionLocal() as db:
        issue = await crud_issue.get(db, id=task_uuid)
        if not issue:
            return f"Task with ID {task_id} not found."
        
        details = [
            f"Title: {issue.title}",
            f"Status: {issue.status}",
            f"Priority: {issue.priority}",
            f"Due Date: {issue.due_date.strftime('%Y-%m-%d %H:%M') if issue.due_date else 'None'}",
            f"Description: {issue.description or 'No description'}",
            f"Project ID: {issue.project_id}",
            f"ID: {issue.id}"
        ]
        return "\n".join(details)

@mcp.tool()
async def schedule_task(task_id: str, due_date_iso: str) -> str:
    """
    Update the due date of an existing task.
    due_date_iso should be in ISO format (e.g., '2026-03-15T09:00:00Z').
    """
    try:
        task_uuid = UUID(task_id)
        due_date = datetime.fromisoformat(due_date_iso.replace('Z', '+00:00'))
    except ValueError as e:
        return f"Error: {str(e)}"

    async with AsyncSessionLocal() as db:
        issue = await crud_issue.get(db, id=task_uuid)
        if not issue:
            return f"Task with ID {task_id} not found."
        
        update_data = IssueUpdate(due_date=due_date)
        await crud_issue.update(db, db_obj=issue, obj_in=update_data)
        await db.commit()
        
        return f"Successfully scheduled '{issue.title}' for {due_date_iso}."

@mcp.tool()
async def create_calendar_task(title: str, description: str = "", due_date_iso: Optional[str] = None) -> str:
    """
    Create a new task with an optional due date.
    due_date_iso should be in ISO format (e.g., '2026-03-15T09:00:00Z').
    """
    user_id = await get_default_user_id()
    due_date = None
    if due_date_iso:
        try:
            due_date = datetime.fromisoformat(due_date_iso.replace('Z', '+00:00'))
        except ValueError as e:
            return f"Error parsing date: {str(e)}"

    async with AsyncSessionLocal() as db:
        # Find "General" project
        res = await db.execute(select(Project).where(and_(Project.owner_id == user_id, Project.name == "General")))
        project = res.scalars().first()
        if not project:
            return "Error: 'General' project not found for user."

        issue_in = IssueCreate(
            title=title,
            description=description,
            project_id=project.id,
            due_date=due_date,
            assignee_id=user_id
        )
        
        issue = await crud_issue.create(db, obj_in=issue_in, owner_id=user_id)
        await db.commit()
        
        return f"Created task '{title}' with ID: {issue.id}"

if __name__ == "__main__":
    mcp.run()
