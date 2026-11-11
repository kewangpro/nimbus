"""Shared sprint placement for new email tasks and AI Schedule."""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import crud_issue

SPRINT_WEEKDAYS = 10

# Keyword-anchored deadlines only — ignore bare newsletter/publication dates.
_DEADLINE_PATTERNS = [
    re.compile(
        r"(?:due|deadline|submit\s+by|needed\s+by|complete\s+by|deliver\s+by|by)"
        r"\s*:?\s*(?:on\s+|the\s+)?"
        r"(\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:due|deadline|submit\s+by|needed\s+by|complete\s+by|deliver\s+by|by)"
        r"\s*:?\s*(?:on\s+|the\s+)?"
        r"([A-Za-z]{3,9}\s+\d{1,2}(?:,?\s*\d{4})?)",
        re.IGNORECASE,
    ),
]

# Time-sensitive content without an explicit "due by" — place early, don't pin
# bare calendar/publication dates as hard deadlines.
_TIME_SENSITIVE_RE = re.compile(
    r"\b("
    r"upcoming|earnings|expires?|expir(?:e|ing)|asap|"
    r"today|tomorrow|this\s+week|end\s+of\s+(?:day|week)|eod|eow|"
    r"reminder|rsvp|time[- ]sensitive"
    r")\b",
    re.IGNORECASE,
)

# Bare MM/DD or MM/DD/YYYY event dates (earnings calendars, release lists).
_EVENT_MDY_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")

_MONTH_DAY_FORMATS = (
    "%B %d, %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%B %d",
    "%b %d",
)


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


def truncate_for_schedule(text: Optional[str], max_chars: int = 400) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


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


def _parse_month_day(raw: str, today: date) -> Optional[date]:
    text = " ".join(raw.split())
    for fmt in _MONTH_DAY_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            year = parsed.year if "%Y" in fmt else today.year
            candidate = date(year, parsed.month, parsed.day)
            if "%Y" not in fmt and candidate < today:
                candidate = date(year + 1, parsed.month, parsed.day)
            return candidate
        except ValueError:
            continue
    return None


def extract_deadline_hint(text: Optional[str], today: date) -> Optional[date]:
    """Return an explicit actionable deadline from title/description, if any."""
    if not text:
        return None
    for pattern in _DEADLINE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(1).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            try:
                return datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                continue
        parsed = _parse_month_day(raw, today)
        if parsed:
            return parsed
    return None


def _parse_event_mdy(month: int, day: int, year: Optional[int], today: date) -> Optional[date]:
    try:
        if year is None:
            candidate = date(today.year, month, day)
            # Yearless dates more than ~1 month in the past likely belong to the next year
            # only when they are far ahead; for earnings lists, past/near dates mean ASAP.
            return candidate
        if year < 100:
            year += 2000
        return date(year, month, day)
    except ValueError:
        return None


def content_prefers_early(text: Optional[str], today: date) -> bool:
    """
    True when content is time-sensitive but has no keyword deadline to pin.
    Examples: upcoming earnings calendars, reminders, ASAP asks.
    """
    if not text:
        return False
    if _TIME_SENSITIVE_RE.search(text):
        return True
    # Event dates at or before the end of this week → review soon, not day 10.
    week_end = today + timedelta(days=(4 - today.weekday()) % 7)
    for match in _EVENT_MDY_RE.finditer(text):
        month = int(match.group(1))
        day = int(match.group(2))
        year_raw = match.group(3)
        year = int(year_raw) if year_raw else None
        event = _parse_event_mdy(month, day, year, today)
        if event is None:
            continue
        if event <= week_end:
            return True
    return False


def day_number_for_deadline(
    deadline: date,
    weekday_dates: list[date],
) -> Optional[str]:
    """Map a deadline to a 1-based day bucket (exact or last weekday on/before)."""
    if not weekday_dates:
        return None
    if deadline < weekday_dates[0] or deadline > weekday_dates[-1]:
        return None
    for i, d in enumerate(weekday_dates):
        if d == deadline:
            return str(i + 1)
    for i in range(len(weekday_dates) - 1, -1, -1):
        if weekday_dates[i] <= deadline:
            return str(i + 1)
    return None


def snap_deadline_to_sprint_weekday(
    deadline: Optional[date],
    weekdays: list[date],
) -> Optional[date]:
    if deadline is None or not weekdays:
        return None
    pinned = day_number_for_deadline(deadline, weekdays)
    if not pinned:
        return None
    return weekdays[int(pinned) - 1]


def resolve_placement_deadline(
    *,
    today: date,
    weekdays: list[date],
    tz: ZoneInfo,
    content_text: Optional[str] = None,
    extracted_due: Any = None,
) -> Optional[date]:
    """
    Shared deadline resolution for email create and AI Schedule.
    Prefer keyword-anchored dates in content; else LLM/extracted due date.
    """
    hint = extract_deadline_hint(content_text, today)
    if hint is not None:
        snapped = snap_deadline_to_sprint_weekday(hint, weekdays)
        return snapped or hint

    parsed = parse_extracted_due_date(extracted_due, tz)
    if parsed is None:
        return None
    due = parsed.astimezone(tz).date()
    snapped = snap_deadline_to_sprint_weekday(due, weekdays)
    return snapped or due


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
        snapped = snap_deadline_to_sprint_weekday(extracted, weekdays)
        return snapped or extracted
    pool = weekdays[:2] if prefer_early else weekdays
    min_load = min(load_by_day.get(day, 0) for day in pool)
    for day in pool:
        if load_by_day.get(day, 0) == min_load:
            return day
    return weekdays[0]


def place_on_sprint(
    *,
    today: date,
    weekdays: list[date],
    load_by_day: dict[date, int],
    tz: ZoneInfo,
    priority: Any = None,
    content_text: Optional[str] = None,
    extracted_due: Any = None,
) -> date:
    """Single placement path used by email create and AI Schedule."""
    deadline = resolve_placement_deadline(
        today=today,
        weekdays=weekdays,
        tz=tz,
        content_text=content_text,
        extracted_due=extracted_due,
    )
    prefer_early = str(priority or "").lower() in ("urgent", "high")
    if not prefer_early and deadline is None:
        prefer_early = content_prefers_early(content_text, today)
    return choose_sprint_due_date(
        deadline,
        today,
        weekdays,
        load_by_day,
        prefer_early=prefer_early,
    )


async def weekday_loads(
    db: AsyncSession,
    user: Any,
    weekdays: list[date],
    tz: ZoneInfo,
    *,
    exclude_issue_ids: Optional[Iterable[UUID]] = None,
) -> dict[date, int]:
    counts = {day: 0 for day in weekdays}
    exclude = set(exclude_issue_ids or [])
    issues = await crud_issue.get_multi(db, assignee_id=user.id, skip=0, limit=500)
    open_statuses = {"todo", "in_progress"}
    for issue in issues:
        if issue.id in exclude:
            continue
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


async def resolve_task_due_date(
    db: AsyncSession,
    user: Any,
    *,
    priority: Any = None,
    content_text: Optional[str] = None,
    extracted_due: Any = None,
    now: Optional[datetime] = None,
    load_by_day: Optional[dict[date, int]] = None,
    exclude_issue_ids: Optional[Iterable[UUID]] = None,
) -> datetime:
    """
    Shared due-date resolver for new email tasks and AI Schedule.
    """
    tz = zoneinfo_for_user(user)
    now_local = now.astimezone(tz) if now else datetime.now(tz)
    today = now_local.date()
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    loads = load_by_day if load_by_day is not None else await weekday_loads(
        db, user, weekdays, tz, exclude_issue_ids=exclude_issue_ids
    )
    chosen = place_on_sprint(
        today=today,
        weekdays=weekdays,
        load_by_day=loads,
        tz=tz,
        priority=priority,
        content_text=content_text,
        extracted_due=extracted_due,
    )
    return datetime.combine(chosen, time.min, tzinfo=tz)


# Backward-compatible alias used by email paths / older tests
async def resolve_email_task_due_date(
    db: AsyncSession,
    user: Any,
    extracted_due: Any = None,
    priority: Any = None,
    now: Optional[datetime] = None,
    content_text: Optional[str] = None,
) -> datetime:
    return await resolve_task_due_date(
        db,
        user,
        priority=priority,
        content_text=content_text,
        extracted_due=extracted_due,
        now=now,
    )
