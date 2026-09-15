from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_issue

SPRINT_WEEKDAYS = 10


def zoneinfo_for_user(user: Any) -> ZoneInfo:
    try:
        return ZoneInfo(getattr(user, "timezone", None) or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def next_weekdays(from_date: date, count: int) -> list[date]:
    days: list[date] = []
    current = from_date
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def parse_extracted_due_date(value: Any, tz: ZoneInfo) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=tz)
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() in ("null", "none"):
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=tz)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=tz)
        return parsed
    except ValueError:
        return None


def choose_sprint_due_date(
    extracted: Optional[date],
    today: date,
    weekdays: list[date],
    load_by_day: dict[date, int],
    *,
    prefer_early: bool = False,
) -> date:
    """Keep in-sprint deadlines; otherwise place on the lightest weekday."""
    sprint_end = weekdays[-1]
    if extracted is not None and today <= extracted <= sprint_end:
        return extracted
    pool = weekdays[:2] if prefer_early else weekdays
    min_load = min(load_by_day.get(day, 0) for day in pool)
    for day in pool:
        if load_by_day.get(day, 0) == min_load:
            return day
    return weekdays[0]


async def _weekday_loads(
    db: AsyncSession,
    user: Any,
    weekdays: list[date],
    tz: ZoneInfo,
) -> dict[date, int]:
    counts = {day: 0 for day in weekdays}
    issues = await crud_issue.get_multi(db, assignee_id=user.id, skip=0, limit=200)
    open_statuses = {"todo", "in_progress"}
    for issue in issues:
        if issue.status not in open_statuses:
            continue
        if issue.due_date is None:
            continue
        due_dt = issue.due_date
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        due_day = due_dt.astimezone(tz).date()
        if due_day in counts:
            counts[due_day] += 1
    return counts


async def resolve_email_task_due_date(
    db: AsyncSession,
    user: Any,
    extracted_due: Any = None,
    priority: Any = None,
    now: Optional[datetime] = None,
) -> datetime:
    """Put new email tasks on the current 10-weekday sprint without a full AI Schedule run."""
    tz = zoneinfo_for_user(user)
    now_local = now.astimezone(tz) if now else datetime.now(tz)
    today = now_local.date()
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    parsed = parse_extracted_due_date(extracted_due, tz)
    extracted_date = parsed.astimezone(tz).date() if parsed else None
    loads = await _weekday_loads(db, user, weekdays, tz)
    prefer_early = str(priority or "").lower() in ("urgent", "high")
    chosen = choose_sprint_due_date(
        extracted_date,
        today,
        weekdays,
        loads,
        prefer_early=prefer_early,
    )
    return datetime.combine(chosen, time.min, tzinfo=tz)
