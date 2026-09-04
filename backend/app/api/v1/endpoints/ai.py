from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta, date, time, timezone

import logging
import json
import re
from uuid import UUID

from app.api import deps
from app.core import ai
from app.crud import crud_embedding, crud_audit, crud_issue, crud_issue_summary, crud_project, crud_user, crud_issue_link
from app.schemas.issue import Issue, IssuePriority, IssueStatus, IssueUpdate

router = APIRouter()
logger = logging.getLogger(__name__)

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
    search_query: Optional[str] = None

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
    logger.info(f"User {current_user.id} requested auto-scheduling")
    # 1. Fetch open issues (scoped by role)
    # For regular users and tests, always filter by current user
    owner_id = current_user.id
    assignee_id = None

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
    logger.info(f"Found {len(open_issues)} open issues total")

    # Schedule issues that are:
    # 1. Unscheduled (no due_date)
    # 2. Scheduled for today or in the future
    # We explicitly EXCLUDE overdue tasks (due before today) to avoid moving them automatically.
    user_tz = getattr(current_user, "timezone", "UTC")
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = timezone.utc

    now_in_tz = datetime.now(tz)
    # Start of today for horizon comparison (timezone aware)
    today_dt = now_in_tz.replace(hour=0, minute=0, second=0, microsecond=0)
    today = today_dt.date()
    
    schedulable_issues: list[Issue] = []
    for issue in open_issues:
        if issue.due_date is None:
            schedulable_issues.append(issue)
            continue
        try:
            due_dt = issue.due_date
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=timezone.utc)
            
            # Convert to user's timezone for comparison
            due_in_tz = due_dt.astimezone(tz)
            
            # Skip overdue tasks (due before today)
            if due_in_tz.date() < today:
                logger.info(f"Skipping overdue task: {issue.title} (due {due_in_tz.date()})")
                continue

            schedulable_issues.append(issue)
        except Exception:
            schedulable_issues.append(issue)
    
    if not schedulable_issues:
        logger.info("No issues require rescheduling.")
        return {"scheduled_count": 0, "message": "No issues require rescheduling."}

    logger.info(f"Redistributing {len(schedulable_issues)} issues for total sprint balance")

    # Priority mapping for numerical sorting
    priority_map = {
        "urgent": 0,
        "high": 1,
        "medium": 2,
        "low": 3
    }

    # Sort criteria for processing:
    # 1. Priority (URGENT -> LOW) - Ensure important tasks get first pick of earlier days
    # 2. Created date (Older first)
    schedulable_issues.sort(key=lambda x: (
        priority_map.get(str(x.priority).lower(), 9),
        x.created_at or datetime.min.replace(tzinfo=timezone.utc)
    ))
    
    # Generate next 10 weekdays in user's timezone
    next_10_weekdays = []
    # today variable is already defined as now_in_tz.date()
    current_date = today
    while len(next_10_weekdays) < 10:
        if current_date.weekday() < 5: # 0-4 are Mon-Fri
            next_10_weekdays.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)

    # 2. Process in batches with Enforced Balancing
    batch_size = 20
    total_updated = 0
    
    # Track task counts per day for global balancing (Day 1-10)
    day_counts = {str(i+1): 0 for i in range(10)}
    
    # Map Day 1-10 to dates
    day_map = {str(i+1): d for i, d in enumerate(next_10_weekdays)}
    
    # Strict quota: No day should have significantly more than average
    ideal_per_day = len(schedulable_issues) // 10
    max_hard_limit = ideal_per_day + 3 # Allow slight flexibility for priorities

    for i in range(0, len(schedulable_issues), batch_size):
        batch = schedulable_issues[i:i+batch_size]
        logger.info(f"Balancing batch {i//batch_size + 1} ({len(batch)} tasks)")
        
        batch_id_map = {str(idx): str(task.id) for idx, task in enumerate(batch)}
        batch_issues_text = "\n".join([f"- Index: {idx}, Title: {task.title}, Priority: {task.priority}" for idx, task in enumerate(batch)])
        
        counts_summary = ", ".join([f"Day {d}: {c} tasks" for d, c in day_counts.items()])
        
        prompt = f"""
        You are an expert productivity scheduler. Today is {today.strftime("%Y-%m-%d")}.
        Your goal is to bucket the following {len(batch)} tasks into EXACTLY 5 DAYS.
        
        ### CURRENT WORKLOAD ###
        {counts_summary}
        (Target: ~{ideal_per_day} per day)
        
        ### THE ONLY 10 ALLOWED BUCKETS ###
        1 ({next_10_weekdays[0]})
        2 ({next_10_weekdays[1]})
        3 ({next_10_weekdays[2]})
        4 ({next_10_weekdays[3]})
        5 ({next_10_weekdays[4]})
        6 ({next_10_weekdays[5]})
        7 ({next_10_weekdays[6]})
        8 ({next_10_weekdays[7]})
        9 ({next_10_weekdays[8]})
        10 ({next_10_weekdays[9]})
        
        ### INSTRUCTIONS ###
        1. FILL LIGHT DAYS: Day 1-10 must be roughly equal. Fill the days with fewer tasks first.
        2. NO OVERLOADING: Do not put tasks on a day that already has {max_hard_limit} tasks if possible.
        3. PRIORITY: 'URGENT' tasks MUST go in Day 1 or 2.
        
        ### TASK LIST ###
        {batch_issues_text}
        
        ### OUTPUT FORMAT ###
        Respond ONLY with a JSON array: [{{"index": 0, "day_number": 1}}, ...]
        """
        
        system_message = "You are a task balancer. Distribute tasks across buckets 1-10 to ensure even workload."
        response = await ai.generate_completion(prompt, system_prompt=system_message)
        
        batch_data = []
        if response:
            try:
                matches = re.findall(r'\{[^{}]*\}', response)
                for m in matches:
                    try:
                        item = json.loads(m)
                        if "index" in item and "day_number" in item:
                            batch_data.append(item)
                    except Exception: continue
            except Exception: pass

        # Create a set of processed indices in this batch to handle missing AI responses
        processed_indices = set()

        for item in batch_data:
            idx_val = str(item.get("index"))
            day_num_raw = item.get("day_number")
            
            if idx_val not in batch_id_map: continue
            processed_indices.add(idx_val)

            # Deterministic Fallback: If AI suggests an overloaded day, find the truly least busy day
            try:
                d_int = int(day_num_raw)
                if d_int < 1: d_int = 1
                if d_int > 10: d_int = 10
                day_num = str(d_int)
            except (ValueError, TypeError):
                day_num = "1"

            # SAFETY LAYER: If the chosen day is already over the average, 
            # and there's a day with significantly fewer tasks, override the AI.
            current_day_load = day_counts[day_num]
            min_day = min(day_counts, key=day_counts.get)
            if current_day_load > day_counts[min_day] + 2:
                day_num = min_day

            issue_id_str = batch_id_map.get(idx_val)
            date_str = day_map.get(day_num)

            try:
                issue_id = UUID(issue_id_str)
                due_day = datetime.strptime(date_str, "%Y-%m-%d").date()
                due_date = datetime.combine(due_day, time.min, tzinfo=tz)

                issue_obj = await crud_issue.get(db, id=issue_id)
                if issue_obj:
                    if issue_obj.due_date != due_date:
                        await crud_issue.update(db, db_obj=issue_obj, obj_in=IssueUpdate(due_date=due_date))
                        await crud_audit.log_action(
                            db,
                            action="issue.update",
                            user_id=current_user.id,
                            entity_type="issue",
                            entity_id=issue_obj.id,
                            details={
                                "title": issue_obj.title,
                                "changes": ["due_date"],
                                "via": "ai_scheduler",
                            },
                        )
                    day_counts[day_num] += 1
                    total_updated += 1
            except Exception: continue

        # Ensure 100% Coverage: If AI missed any tasks in the batch, round-robin them
        for idx, task in batch_id_map.items():
            if idx not in processed_indices:
                # Find least busy day
                day_num = min(day_counts, key=day_counts.get)
                date_str = day_map[day_num]
                try:
                    issue_id = UUID(task)
                    due_day = datetime.strptime(date_str, "%Y-%m-%d").date()
                    due_date = datetime.combine(due_day, time.min, tzinfo=tz)
                    issue_obj = await crud_issue.get(db, id=issue_id)
                    if issue_obj:
                        if issue_obj.due_date != due_date:
                            await crud_issue.update(db, db_obj=issue_obj, obj_in=IssueUpdate(due_date=due_date))
                            await crud_audit.log_action(
                                db,
                                action="issue.update",
                                user_id=current_user.id,
                                entity_type="issue",
                                entity_id=issue_obj.id,
                                details={
                                    "title": issue_obj.title,
                                    "changes": ["due_date"],
                                    "via": "ai_scheduler",
                                },
                            )
                        day_counts[day_num] += 1
                        total_updated += 1
                except Exception: continue
        
        await db.commit()

    logger.info(f"Successfully balanced {total_updated} issues across the sprint.")
    return {"scheduled_count": total_updated, "message": f"Successfully balanced {total_updated} tasks across 10 days."}

@router.post("/plan", response_model=List[PlannedIssue])
async def plan_tasks(
    *,
    request: PlanRequest,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Break down a natural language plan into structured issues.
    """
    user_tz = getattr(current_user, "timezone", "UTC")
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(user_tz)
    except Exception:
        tz = timezone.utc

    now_in_tz = datetime.now(tz)
    today = now_in_tz.date()
    
    # Generate next 10 weekdays for context
    next_10_weekdays = []
    current_date = today
    while len(next_10_weekdays) < 10:
        if current_date.weekday() < 5: # 0-4 are Mon-Fri
            next_10_weekdays.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    
    days_str = ", ".join(next_10_weekdays)

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
    import re
    
    # Robust parsing: Extract individual JSON objects {...} from the response.
    data = []
    matches = re.findall(r'\{[^{}]*\}', response)
    for m in matches:
        try:
            item = json.loads(m)
            if "title" in item:
                data.append(item)
        except Exception:
            continue

    if not data:
        try:
            # cleanup markdown
            clean_json = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            if isinstance(data, dict):
                data = [data]
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

    try:
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

def fallback_parse_summary(text: str) -> dict:
    if not text:
        return {"summary": "No summary available.", "next_steps": ["Review issue details."]}
        
    lines = [line.strip() for line in text.split("\n")]
    summary_lines = []
    next_steps = []
    
    in_next_steps = False
    
    for line in lines:
        if not line:
            continue
        
        lower_line = line.lower()
        if any(keyword in lower_line for keyword in ("next step", "action item", "actions", "todo")):
            in_next_steps = True
            continue
        elif (line.startswith("#") or line.startswith("**")) and in_next_steps:
            if any(keyword in lower_line for keyword in ("key takeaway", "summary", "context")):
                in_next_steps = False
        
        # Parse list items (e.g. 1. Deployment or - Deployment or * Deployment)
        is_list_item = False
        match = re.match(r'^(?:\d+\.|\*|-)\s+(.*)', line)
        if match:
            item_text = match.group(1).strip()
            # Clean bold text wrapper at starting if any e.g. **Deployment:** -> Deployment:
            item_text = re.sub(r'^\*\*(.*?)\*\*\s*(?::|-)?\s*', r'\1: ', item_text)
            item_text = re.sub(r'\s+', ' ', item_text).strip()
            next_steps.append(item_text)
            is_list_item = True
            
        if not is_list_item and not in_next_steps:
            # Regular text paragraph is summary content, skip titles
            if not (line.startswith("#") or (line.startswith("**") and line.endswith("**"))):
                summary_lines.append(line)
                
    summary = " ".join(summary_lines).strip()
    if not summary:
        # Fallback: find first non-empty line
        non_empty = [l for l in lines if l and not l.startswith("#")]
        summary = non_empty[0] if non_empty else "No summary available."
        
    # If no next steps were gathered because we were not in_next_steps, collect any list items in the text
    if not next_steps:
        for line in lines:
            match = re.match(r'^(?:\d+\.|\*|-)\s+(.*)', line)
            if match:
                item_text = match.group(1).strip()
                item_text = re.sub(r'^\*\*(.*?)\*\*\s*(?::|-)?\s*', r'\1: ', item_text)
                item_text = re.sub(r'\s+', ' ', item_text).strip()
                next_steps.append(item_text)
                
    # Unique non-empty next steps
    seen = set()
    cleaned_steps = []
    for step in next_steps:
        s_clean = step.strip()
        if s_clean and s_clean.lower() not in seen:
            seen.add(s_clean.lower())
            cleaned_steps.append(s_clean)
            
    if not cleaned_steps:
        cleaned_steps = ["Review issue details.", "Determine next implementation steps."]
        
    return {
        "summary": summary,
        "next_steps": cleaned_steps[:5]
    }


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

    parsed = ai.parse_json_robust(response)
    if isinstance(parsed, list) and parsed:
        parsed = parsed[0]
    
    if not isinstance(parsed, dict):
        parsed = fallback_parse_summary(response)

    summary = parsed.get("summary", "").strip()
    next_steps = parsed.get("next_steps", [])
    if not isinstance(next_steps, list):
        next_steps = []
    next_steps = [str(step).strip() for step in next_steps if str(step).strip()]
    if not summary:
        summary = "Summary generated."

    await crud_issue_summary.upsert(
        db,
        issue_id=issue.id,
        summary=summary,
        next_steps="\n".join(next_steps),
        content_hash=content_hash,
    )

    return {"issue_id": issue.id, "summary": summary, "next_steps": next_steps}


@router.get("/summary/{issue_id}", response_model=Optional[SummaryResponse])
async def get_issue_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    issue_id: UUID,
    current_user: Any = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get existing AI summary for an issue if one exists.
    """
    issue = await crud_issue.get(db, id=issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if getattr(current_user, "role", None) == "client" and issue.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    existing = await crud_issue_summary.get_by_issue_id(db, issue.id)
    if not existing:
        return None

    return {
        "issue_id": issue.id,
        "summary": existing.summary,
        "next_steps": [s for s in existing.next_steps.split("\n") if s.strip()],
    }


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
    - search_query: string representing keywords to search for in titles/descriptions, or null. If the user mentions a specific task topic, project keywords, or title, extract it here.

    Examples:
    - "urgent items" -> {{ "priority": "URGENT" }}
    - "high priority overdue" -> {{ "priority": "HIGH", "overdue": true }}
    - "done tasks" -> {{ "status": "DONE" }}
    - "unscheduled work" -> {{ "unscheduled": true }}
    - "urgent for Alice" -> {{ "priority": "URGENT", "assignee_id": "<alice_id>" }}
    - "Jira integration tasks" -> {{ "search_query": "Jira integration" }}
    - "find ChatGPT task" -> {{ "search_query": "ChatGPT" }}

    Projects:
    {projects_text}

    Users:
    {users_text}

    Query: "{request.text}"
    """

    response = await ai.generate_completion(prompt, system_prompt="You output strict JSON only.")
    if not response:
        raise HTTPException(status_code=500, detail="Failed to interpret query")

    data = ai.parse_json_robust(response)
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
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
    search_query = data.get("search_query")

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
        "search_query": search_query,
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
    
    data = ai.parse_json_robust(response)
    if isinstance(data, list) and data:
        data = data[0]
    
    if not isinstance(data, dict):
        return {"priority": IssuePriority.MEDIUM, "labels": []}
        
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
