from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta, date, time, timezone

from app.api import deps
from app.core import ai
from app.crud import crud_embedding, crud_issue, crud_issue_summary, crud_project, crud_user, crud_issue_link
from app.schemas.issue import Issue, IssuePriority, IssueStatus

router = APIRouter()

class SearchRequest(BaseModel):
    query: str
    limit: int = 5

class TriageRequest(BaseModel):
    title: str
    description: str
    issue_id: Optional[UUID] = None

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
    due_date: Optional[str] = None

class ScheduleResponse(BaseModel):
    scheduled_count: int
    message: str

class SimilarRequest(BaseModel):
    title: str
    description: Optional[str] = None
    limit: int = 5
    project_id: Optional[str] = None
    exclude_issue_id: Optional[str] = None

class SummaryRequest(BaseModel):
    issue_id: UUID
    force: bool = False

class SummaryResponse(BaseModel):
    issue_id: UUID
    summary: str
    next_steps: List[str]

class QueryRequest(BaseModel):
    text: str
    project_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None

class QueryResponse(BaseModel):
    project_id: Optional[UUID] = None
    assignee_id: Optional[UUID] = None
    status: Optional[IssueStatus] = None
    priority: Optional[IssuePriority] = None
    overdue: Optional[bool] = None
    unscheduled: Optional[bool] = None

class ClientUpdateRequest(BaseModel):
    project_id: Optional[UUID] = None

class ClientUpdateResponse(BaseModel):
    project_id: Optional[UUID] = None
    update_text: str

class DependencyRequest(BaseModel):
    issue_id: UUID
    project_id: Optional[UUID] = None
    limit: int = 30

@router.post("/schedule", response_model=ScheduleResponse)
async def auto_schedule(
    db: AsyncSession = Depends(deps.get_db),
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Auto-schedule open issues using AI.
    """
    # 1. Fetch open issues (scoped by role)
    owner_id = None
    assignee_id = None
    if getattr(current_user, "role", None) == "client":
        owner_id = current_user.id
    elif getattr(current_user, "role", None) == "member":
        assignee_id = current_user.id

    issues: list[Issue] = []
    page_size = 200
    skip = 0
    while True:
        batch = await crud_issue.get_multi(
            db,
            skip=skip,
            limit=page_size,
            owner_id=owner_id,
            assignee_id=assignee_id,
        )
        if not batch:
            break
        issues.extend(batch)
        if len(batch) < page_size:
            break
        skip += page_size
    open_issues = [i for i in issues if i.status != IssueStatus.DONE and i.status != IssueStatus.CANCELED]

    # Only schedule issues with no due_date or past due
    now_utc = datetime.now(timezone.utc)
    schedulable_issues: list[Issue] = []
    for issue in open_issues:
        if issue.due_date is None:
            schedulable_issues.append(issue)
            continue
        try:
            due_dt = issue.due_date
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=timezone.utc)
            if due_dt < now_utc:
                schedulable_issues.append(issue)
        except Exception:
            # If due_date is malformed, treat as unscheduled
            schedulable_issues.append(issue)
    
    if not schedulable_issues:
        return {"scheduled_count": 0, "message": "No unscheduled or overdue issues to schedule."}

    # 2. Prepare prompt
    issues_text = "\n".join([f"- ID: {i.id}, Title: {i.title}, Priority: {i.priority}" for i in schedulable_issues])
    today = datetime.now(timezone.utc).date()
    
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

        allowed_ids = {str(i.id) for i in schedulable_issues}
        allowed_dates = set(next_5_weekdays)

        for item in schedule_data:
            issue_id_str = item.get("id")
            date_str = item.get("date")

            if not issue_id_str or not date_str:
                continue
            if issue_id_str not in allowed_ids:
                continue
            if date_str not in allowed_dates:
                continue

            try:
                issue_id = UUID(issue_id_str)
                due_day = datetime.strptime(date_str, "%Y-%m-%d").date()
                due_date = datetime.combine(due_day, time.min, tzinfo=timezone.utc)

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
    today = datetime.now()
    
    # Generate next 5 weekdays for context
    next_5_weekdays = []
    current_date = today
    while len(next_5_weekdays) < 5:
        if current_date.weekday() < 5: # 0-4 are Mon-Fri
            next_5_weekdays.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    
    days_str = ", ".join(next_5_weekdays)

    prompt = f"""
    You are an expert Project Manager. Break down the following user input into distinct, actionable software tasks.
    
    Today is {today.strftime("%Y-%m-%d")}.
    Available work days: {days_str}
    
    User Input: "{request.text}"
    
    For each task, infer:
    - title: A clear, concise summary.
    - description: A detailed explanation of what needs to be done.
    - priority: LOW, MEDIUM, HIGH, or URGENT (based on urgency/importance).
    - status: TODO, IN_PROGRESS, or DONE (context dependent, default to TODO).
    - due_date: YYYY-MM-DD (Suggest a balanced due date from the available work days list. Avoid weekends. High priority earlier).
    
    Output STRICTLY a JSON array of objects. No markdown, no conversational text.
    Example: [{{ "title": "...", "description": "...", "priority": "HIGH", "status": "TODO", "due_date": "2023-10-27" }}]
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
            
            # Validate due date
            due_date = item.get("due_date")
            if due_date:
                try:
                    # Validate format only
                    datetime.strptime(due_date, "%Y-%m-%d")
                except ValueError:
                    due_date = None

            results.append(PlannedIssue(
                title=item.get("title", "Untitled Task"),
                description=item.get("description", ""),
                priority=IssuePriority[p],
                status=IssueStatus[s],
                due_date=due_date
            ))
            
        return results
    except Exception as e:
        print(f"Plan parse error: {e}")
        # Fallback: Treat the whole text as one task if parsing fails
        return [PlannedIssue(
            title="Task from plan", 
            description=request.text, 
            priority=IssuePriority.MEDIUM, 
            status=IssueStatus.TODO,
            due_date=today.strftime("%Y-%m-%d")
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
    
    fetch_limit = max(10, request.limit * 5)
    similar_embeddings = await crud_embedding.search_similar(
        db, embedding=embedding, limit=fetch_limit
    )

    issues = []
    for emb in similar_embeddings:
        issue = await crud_issue.get(db, id=emb.issue_id)
        if not issue:
            continue
        if getattr(current_user, "role", None) == "client" and issue.owner_id != current_user.id:
            continue
        issues.append(issue)
        if len(issues) >= request.limit:
            break

    return issues

@router.post("/similar", response_model=List[Issue])
async def find_similar_issues(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request: SimilarRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Find issues similar to the provided title/description.
    """
    base_text = f"{request.title} {request.description or ''}".strip()
    if not base_text:
        raise HTTPException(status_code=400, detail="Title or description required")

    embedding = await ai.generate_embedding(base_text)
    if not embedding:
        raise HTTPException(status_code=500, detail="Failed to generate embedding")

    fetch_limit = max(10, request.limit * 5)
    similar_embeddings = await crud_embedding.search_similar(
        db, embedding=embedding, limit=fetch_limit
    )

    issues: list[Issue] = []
    for emb in similar_embeddings:
        issue = await crud_issue.get(db, id=emb.issue_id)
        if not issue:
            continue
        if request.exclude_issue_id and str(issue.id) == request.exclude_issue_id:
            continue
        if request.project_id and str(issue.project_id) != request.project_id:
            continue
        if getattr(current_user, "role", None) == "client" and issue.owner_id != current_user.id:
            continue
        issues.append(issue)
        if len(issues) >= request.limit:
            break

    return issues

@router.post("/summary", response_model=SummaryResponse)
async def summarize_issue(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request: SummaryRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Generate or return an AI summary for an issue.
    """
    issue = await crud_issue.get(db, id=request.issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if getattr(current_user, "role", None) == "client" and issue.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    full_text = f"{issue.title} {issue.description or ''}"
    content_hash = crud_issue.get_content_hash(full_text)

    existing = await crud_issue_summary.get_by_issue_id(db, issue.id)
    if existing and existing.content_hash == content_hash and not request.force:
        return {
            "issue_id": issue.id,
            "summary": existing.summary,
            "next_steps": [s for s in existing.next_steps.split("\n") if s.strip()],
        }

    prompt = f"""
    Summarize this issue for a teammate. Provide a short summary and 3-5 concrete next steps.
    Return STRICT JSON only:
    {{ "summary": "...", "next_steps": ["...", "..."] }}

    Title: {issue.title}
    Description: {issue.description or ""}
    """

    response = await ai.generate_completion(prompt, system_prompt="You are a concise project assistant. JSON only.")
    if not response:
        raise HTTPException(status_code=500, detail="Failed to generate summary")

    import json
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        summary = data.get("summary", "").strip()
        next_steps = data.get("next_steps", [])
        if not isinstance(next_steps, list):
            next_steps = []
        next_steps = [str(step).strip() for step in next_steps if str(step).strip()]
        if not summary:
            raise ValueError("Empty summary")
    except Exception as e:
        print(f"Summary parse error: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse summary")

    await crud_issue_summary.upsert(
        db,
        issue_id=issue.id,
        summary=summary,
        next_steps="\n".join(next_steps),
        content_hash=content_hash,
    )

    return {"issue_id": issue.id, "summary": summary, "next_steps": next_steps}

@router.post("/query", response_model=QueryResponse)
async def ai_query_to_filters(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request: QueryRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Convert natural language into structured issue filters.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    projects = await crud_project.get_multi(db, limit=200)
    users = await crud_user.get_multi(db, limit=200)

    projects_text = "\n".join([f"- {p.id}: {p.name}" for p in projects])
    users_text = "\n".join([f"- {u.id}: {u.full_name} ({u.email})" for u in users])

    prompt = f"""
    Convert the user query into JSON filters for issues.
    Output JSON only. Allowed fields:
    - project_id (uuid) from list or null
    - assignee_id (uuid) from list or null
    - status: one of TODO, IN_PROGRESS, DONE, CANCELED or null
    - priority: one of LOW, MEDIUM, HIGH, URGENT or null
    - overdue: true/false or null
    - unscheduled: true/false or null

    Examples:
    - "urgent items" -> {{ "priority": "URGENT" }}
    - "high priority overdue" -> {{ "priority": "HIGH", "overdue": true }}
    - "done tasks" -> {{ "status": "DONE" }}
    - "unscheduled work" -> {{ "unscheduled": true }}
    - "urgent for Alice" -> {{ "priority": "URGENT", "assignee_id": "<alice_id>" }}

    Projects:
    {projects_text}

    Users:
    {users_text}

    Query: "{request.text}"
    """

    response = await ai.generate_completion(prompt, system_prompt="You output strict JSON only.")
    if not response:
        raise HTTPException(status_code=500, detail="Failed to interpret query")

    import json
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
    except Exception as e:
        print(f"Query parse error: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse query")

    def _normalize_enum(value: Optional[str], enum_cls):
        if not value:
            return None
        value = value.upper()
        return enum_cls[value] if value in enum_cls.__members__ else None

    project_id = data.get("project_id") or request.project_id
    assignee_id = data.get("assignee_id") or request.assignee_id
    status = _normalize_enum(data.get("status"), IssueStatus)
    priority = _normalize_enum(data.get("priority"), IssuePriority)
    overdue = data.get("overdue")
    unscheduled = data.get("unscheduled")

    if status in [IssueStatus.DONE, IssueStatus.CANCELED]:
        overdue = None
        unscheduled = None

    if getattr(current_user, "role", None) == "client":
        assignee_id = None

    return {
        "project_id": project_id,
        "assignee_id": assignee_id,
        "status": status,
        "priority": priority,
        "overdue": overdue if isinstance(overdue, bool) else None,
        "unscheduled": unscheduled if isinstance(unscheduled, bool) else None,
    }

@router.post("/client-update", response_model=ClientUpdateResponse)
async def client_update_draft(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request: ClientUpdateRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Draft a client-friendly weekly update for a project.
    """
    project_id = request.project_id
    issues = await crud_issue.get_multi(db, limit=1000, project_id=project_id)

    if getattr(current_user, "role", None) == "client":
        issues = [i for i in issues if i.owner_id == current_user.id]

    issues_text = "\n".join([
        f"- {i.title} | status={i.status} | priority={i.priority} | due={i.due_date}"
        for i in issues
    ])

    prompt = f"""
    Draft a concise weekly client update based on the issues below.
    Keep it under 8 bullet points. Use plain language.
    Include sections: Summary, Completed, In Progress, Risks/Blockers.
    Output plain text.

    Issues:
    {issues_text}
    """

    response = await ai.generate_completion(prompt, system_prompt="You write crisp client updates.")
    if not response:
        raise HTTPException(status_code=500, detail="Failed to generate update")

    return {"project_id": project_id, "update_text": response.strip()}

@router.post("/dependencies", response_model=List[Issue])
async def detect_dependencies(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request: DependencyRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Detect likely dependency issues for a given issue.
    """
    issue = await crud_issue.get(db, id=request.issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if getattr(current_user, "role", None) == "client" and issue.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    candidates = await crud_issue.get_multi(
        db,
        limit=request.limit,
        project_id=request.project_id or issue.project_id,
    )
    candidates = [c for c in candidates if c.id != issue.id]

    candidate_text = "\n".join([f"- {c.id}: {c.title}" for c in candidates])
    prompt = f"""
    Identify which of these issues the target issue depends on.
    Return STRICT JSON only: {{ "depends_on": ["uuid", ...] }}

    Target Issue:
    {issue.title}
    {issue.description or ""}

    Candidate Issues:
    {candidate_text}
    """

    response = await ai.generate_completion(prompt, system_prompt="You output strict JSON only.")
    if not response:
        raise HTTPException(status_code=500, detail="Failed to detect dependencies")

    import json
    try:
        clean_json = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        depends_on = data.get("depends_on", [])
        if not isinstance(depends_on, list):
            depends_on = []
    except Exception as e:
        print(f"Dependency parse error: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse dependencies")

    allowed_ids = {str(c.id) for c in candidates}
    filtered_ids = [UUID(dep_id) for dep_id in depends_on if str(dep_id) in allowed_ids]
    await crud_issue_link.set_dependencies(db, issue.id, filtered_ids)

    deps_issues = await crud_issue_link.get_dependencies(db, issue.id)
    return deps_issues

@router.post("/triage", response_model=TriageResponse)
async def auto_triage(
    *,
    db: AsyncSession = Depends(deps.get_db),
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
            
        labels = data.get("labels", [])

        if request.issue_id and labels:
            from app.crud import crud_label
            await crud_label.set_issue_labels(db, request.issue_id, labels)

        return {
            "priority": IssuePriority[priority],
            "labels": labels
        }
    except Exception as e:
        print(f"Triage parse error: {e}")
        return {"priority": IssuePriority.MEDIUM, "labels": []}
