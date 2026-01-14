from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.api import deps
from app.core import ai
from app.crud import crud_embedding, crud_issue
from app.schemas.issue import Issue, IssuePriority, IssueStatus

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class TriageRequest(BaseModel):
    title: str
    description: str

class TriageResponse(BaseModel):
    priority: IssuePriority
    labels: List[str] = []

class PlanRequest(BaseModel):
    text: str

class PlannedIssue(BaseModel):
    title: str
    description: str
    priority: IssuePriority
    status: IssueStatus

class ScheduleResponse(BaseModel):
    scheduled_count: int
    message: str

@router.post("/schedule", response_model=ScheduleResponse)
async def auto_schedule(
    db: AsyncSession = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Auto-schedule open issues using AI.
    """
    # 1. Fetch open issues
    issues = await crud_issue.get_multi(db, limit=100) # Fetch up to 100
    open_issues = [i for i in issues if i.status != IssueStatus.DONE and i.status != IssueStatus.CANCELED]
    
    if not open_issues:
        return {"scheduled_count": 0, "message": "No open issues to schedule."}

    # 2. Prepare prompt
    issues_text = "\n".join([f"- ID: {i.id}, Title: {i.title}, Priority: {i.priority}" for i in open_issues])
    today = datetime.now()
    
    # Generate next 5 weekdays
    next_5_weekdays = []
    current_date = today
    while len(next_5_weekdays) < 5:
        if current_date.weekday() < 5: # 0-4 are Mon-Fri
            next_5_weekdays.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
        
    days_str = ", ".join(next_5_weekdays)
    
    prompt = f"""
    You are an expert productivity scheduler. Today is {today.strftime("%Y-%m-%d")}.
    Your goal is to schedule these open tasks over the next 5 WEEKDAYS ({days_str}) for MAXIMUM productivity.
    
    Rules:
    1. Distribute workload evenly. Do NOT put all tasks on the first day.
    2. High priority tasks should be earlier in the schedule.
    3. Limit to approx 3-5 significant tasks per day to prevent burnout.
    4. STRICTLY use only the provided dates. NO weekends.
    
    Tasks:
    {issues_text}
    
    Output strictly a JSON array of objects: {{ "id": "uuid", "date": "YYYY-MM-DD" }}
    """
    
    response = await ai.generate_completion(prompt, system_prompt="You are a JSON scheduler.")
    
    if not response:
        raise HTTPException(status_code=500, detail="Failed to generate schedule")

    import json
    count = 0
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        schedule_data = json.loads(clean_json)
        
        from uuid import UUID
        from app.schemas.issue import IssueUpdate
        
        for item in schedule_data:
            issue_id_str = item.get("id")
            date_str = item.get("date")
            
            if issue_id_str and date_str:
                try:
                    issue_id = UUID(issue_id_str)
                    due_date = datetime.strptime(date_str, "%Y-%m-%d")
                    
                    # Update issue
                    issue_obj = await crud_issue.get(db, id=issue_id)
                    if issue_obj:
                        await crud_issue.update(db, db_obj=issue_obj, obj_in=IssueUpdate(due_date=due_date))
                        count += 1
                except ValueError:
                    continue
                    
        return {"scheduled_count": count, "message": f"Successfully scheduled {count} tasks."}
        
    except Exception as e:
        print(f"Schedule parse error: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse schedule")

@router.post("/plan", response_model=List[PlannedIssue])
async def plan_tasks(
    *,
    request: PlanRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Break down a natural language plan into structured issues.
    """
    prompt = f"""
    You are an expert Project Manager. Break down the following user input into distinct, actionable software tasks.
    
    User Input: "{request.text}"
    
    For each task, infer:
    - title: A clear, concise summary.
    - description: A detailed explanation of what needs to be done.
    - priority: LOW, MEDIUM, HIGH, or URGENT (based on urgency/importance).
    - status: TODO, IN_PROGRESS, or DONE (context dependent, default to TODO).
    
    Output STRICTLY a JSON array of objects. No markdown, no conversational text.
    Example: [{{ "title": "...", "description": "...", "priority": "HIGH", "status": "TODO" }}]
    """
    
    response = await ai.generate_completion(prompt, system_prompt="You are a strict JSON output machine.")
    
    if not response:
        raise HTTPException(status_code=500, detail="Failed to generate plan")
    
    import json
    
    try:
        # cleanup markdown
        clean_json = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        results = []
        for item in data:
            # Normalize enum values
            p = item.get("priority", "MEDIUM").upper()
            if p not in IssuePriority.__members__: p = "MEDIUM"
            
            s = item.get("status", "TODO").upper()
            if s not in IssueStatus.__members__: s = "TODO"
            
            results.append(PlannedIssue(
                title=item.get("title", "Untitled Task"),
                description=item.get("description", ""),
                priority=IssuePriority[p],
                status=IssueStatus[s]
            ))
            
        return results
    except Exception as e:
        print(f"Plan parse error: {e}")
        # Fallback: Treat the whole text as one task if parsing fails
        return [PlannedIssue(
            title="Task from plan", 
            description=request.text, 
            priority=IssuePriority.MEDIUM, 
            status=IssueStatus.TODO
        )]

@router.post("/search", response_model=List[Issue])
async def semantic_search(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request: SearchRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Search issues using vector similarity.
    """
    embedding = await ai.generate_embedding(request.query)
    if not embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")
    
    similar_embeddings = await crud_embedding.search_similar(
        db, embedding=embedding, limit=request.limit
    )
    
    issues = []
    for emb in similar_embeddings:
        issue = await crud_issue.get(db, id=emb.issue_id)
        if issue:
            issues.append(issue)
            
    return issues

@router.post("/triage", response_model=TriageResponse)
async def auto_triage(
    *,
    request: TriageRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Suggest priority and labels for an issue using LLM.
    """
    prompt = f"""
    Analyze the following software issue and suggest a Priority (LOW, MEDIUM, HIGH, URGENT) and a list of labels.
    
    Title: {request.title}
    Description: {request.description}
    
    Output JSON only: {{ "priority": "...", "labels": [...] }}
    """
    
    response = await ai.generate_completion(prompt, system_prompt="You are a product manager. JSON output only.")
    
    if not response:
        raise HTTPException(status_code=500, detail="Failed to generate triage")
    
    # Simple parsing (robust apps use structured output or Pydantic parsers)
    import json
    import re
    
    try:
        # cleanup markdown code blocks
        clean_json = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        
        # Normalize priority
        priority = data.get("priority", "MEDIUM").upper()
        if priority not in IssuePriority.__members__:
            priority = "MEDIUM"
            
        return {
            "priority": IssuePriority[priority],
            "labels": data.get("labels", [])
        }
    except Exception as e:
        print(f"Triage parse error: {e}")
        return {"priority": IssuePriority.MEDIUM, "labels": []}
