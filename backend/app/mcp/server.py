import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select, and_

from app.db.session import AsyncSessionLocal
from app.models.project import Project
from app.models.issue import Issue, IssueStatus
from app.models.user import User
from app.crud import crud_issue, crud_project, crud_embedding
from app.schemas.issue import IssueCreate, IssueUpdate
from app.core import ai

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
    try:
        user_id = await get_default_user_id()
        async with AsyncSessionLocal() as db:
            # Calculate the cutoff date
            cutoff = datetime.now(timezone.utc) + timedelta(days=days)
            
            # Fetch issues with due_date within the window and not completed
            query = select(Issue).where(
                and_(
                    Issue.owner_id == user_id,
                    Issue.due_date.isnot(None),
                    Issue.due_date <= cutoff,
                    Issue.status != IssueStatus.DONE,
                    Issue.status != IssueStatus.CANCELED
                )
            ).order_by(Issue.due_date.asc(), Issue.created_at.desc())
            
            result = await db.execute(query)
            issues = result.scalars().all()
            
            if not issues:
                return "No tasks found on the calendar."
            
            lines = ["# Calendar Tasks:"]
            for issue in issues:
                due_str = issue.due_date.strftime("%Y-%m-%d %H:%M") if issue.due_date else "N/A"
                lines.append(f"- [{issue.status}] {issue.title} (Due: {due_str}) ID: {issue.id}")
            
            return "\n".join(lines)
    except Exception as e:
        return f"Error listing calendar events: {str(e)}"

@mcp.tool()
async def get_task_details(task_id: str) -> str:
    """
    Get full details of a specific task by its ID.
    """
    try:
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            return f"Error: '{task_id}' is not a valid UUID format."

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
    except Exception as e:
        return f"Error retrieving task details: {str(e)}"

@mcp.tool()
async def schedule_task(task_id: str, due_date_iso: str) -> str:
    """
    Update the due date of an existing task.
    due_date_iso should be in ISO format (e.g., '2026-03-15T09:00:00Z').
    """
    try:
        try:
            task_uuid = UUID(task_id)
            due_date = datetime.fromisoformat(due_date_iso.replace('Z', '+00:00'))
        except ValueError as e:
            return f"Error parsing parameters: {str(e)}"

        async with AsyncSessionLocal() as db:
            issue = await crud_issue.get(db, id=task_uuid)
            if not issue:
                return f"Task with ID {task_id} not found."
            
            update_data = IssueUpdate(due_date=due_date)
            await crud_issue.update(db, db_obj=issue, obj_in=update_data)
            await db.commit()
            
            return f"Successfully scheduled '{issue.title}' for {due_date_iso}."
    except Exception as e:
        return f"Error scheduling task: {str(e)}"

@mcp.tool()
async def create_calendar_task(
    title: str, 
    description: str = "", 
    due_date_iso: Optional[str] = None,
    project_name: str = "General"
) -> str:
    """
    Create a new task with an optional due date and project specification.
    due_date_iso should be in ISO format (e.g., '2026-03-15T09:00:00Z').
    project_name defaults to 'General' if not specified.
    """
    try:
        user_id = await get_default_user_id()
        due_date = None
        if due_date_iso:
            try:
                due_date = datetime.fromisoformat(due_date_iso.replace('Z', '+00:00'))
            except ValueError as e:
                return f"Error parsing date: {str(e)}"

        async with AsyncSessionLocal() as db:
            # Find specific project
            res = await db.execute(select(Project).where(and_(Project.owner_id == user_id, Project.name == project_name)))
            project = res.scalars().first()
            
            if not project:
                # If specific project not found, list available projects to help the user/AI
                res_all = await db.execute(select(Project.name).where(Project.owner_id == user_id))
                available = res_all.scalars().all()
                return f"Error: Project '{project_name}' not found. Available projects: {', '.join(available)}"

            issue_in = IssueCreate(
                title=title,
                description=description,
                project_id=project.id,
                due_date=due_date,
                assignee_id=user_id
            )
            
            issue = await crud_issue.create(db, obj_in=issue_in, owner_id=user_id)
            await db.commit()
            
            return f"Created task '{title}' in project '{project_name}' with ID: {issue.id}"
    except Exception as e:
        return f"Error creating task: {str(e)}"

@mcp.tool()
async def search_tasks(query: str, limit: int = 5) -> str:
    """
    Search for tasks using natural language semantic search.
    Returns the most relevant tasks based on meaning similarity.
    Useful when you don't know the exact ID but know what the task is about.
    """
    try:
        user_id = await get_default_user_id()
        embedding = await ai.generate_embedding(query)
        if not embedding:
            return "Error: Failed to generate embedding for the search query."

        async with AsyncSessionLocal() as db:
            # Fetch a larger pool to filter by user_id
            fetch_limit = max(20, limit * 5)
            similar_embeddings = await crud_embedding.search_similar(
                db, embedding=embedding, limit=fetch_limit
            )

            lines = [f"# Semantic Search Results for '{query}':"]
            count = 0
            for emb in similar_embeddings:
                issue = await crud_issue.get(db, id=emb.issue_id)
                if not issue:
                    continue
                # Ensure user only sees their own tasks
                if issue.owner_id != user_id:
                    continue
                
                due_str = issue.due_date.strftime("%Y-%m-%d") if issue.due_date else "No due date"
                lines.append(f"- [{issue.status}] {issue.title} (Due: {due_str}) ID: {issue.id}")
                count += 1
                if count >= limit:
                    break
            
            if count == 0:
                return f"No relevant tasks found for query: '{query}'"
                
            return "\n".join(lines)
    except Exception as e:
        return f"Error searching tasks: {str(e)}"

if __name__ == "__main__":
    mcp.run()
