from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.scheduling import (
    SPRINT_WEEKDAYS,
    choose_sprint_due_date,
    day_number_for_deadline,
    extract_deadline_hint,
    next_weekdays,
    place_on_sprint,
    resolve_placement_deadline,
    truncate_for_schedule,
)


def test_extract_deadline_hint_iso_with_keyword():
    today = date(2026, 10, 10)
    assert extract_deadline_hint("Please submit by 2026-10-15 before EOD.", today) == date(2026, 10, 15)


def test_extract_deadline_hint_ignores_bare_iso_without_keyword():
    today = date(2026, 10, 10)
    assert extract_deadline_hint("Published 2026-09-01 in our weekly digest.", today) is None


def test_extract_deadline_hint_month_day():
    today = date(2026, 10, 10)
    assert extract_deadline_hint("Deadline: October 20, 2026", today) == date(2026, 10, 20)


def test_day_number_for_deadline_exact_and_weekend_snap():
    start = date(2026, 10, 12)
    weekdays = []
    d = start
    while len(weekdays) < 10:
        if d.weekday() < 5:
            weekdays.append(d)
        d += timedelta(days=1)

    assert day_number_for_deadline(date(2026, 10, 14), weekdays) == "3"
    assert day_number_for_deadline(date(2026, 10, 17), weekdays) == "5"
    assert day_number_for_deadline(date(2026, 12, 1), weekdays) is None


def test_place_on_sprint_shared_for_email_and_schedule():
    """Email create and AI Schedule must use the same placement decision."""
    today = date(2026, 10, 12)  # Monday
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    tz = ZoneInfo("UTC")
    loads = {d: 0 for d in weekdays}
    content = "Please submit by 2026-10-16 so finance can close."

    email_day = place_on_sprint(
        today=today,
        weekdays=weekdays,
        load_by_day=loads,
        tz=tz,
        priority="medium",
        content_text=content,
        extracted_due=None,
    )
    schedule_day = place_on_sprint(
        today=today,
        weekdays=weekdays,
        load_by_day=dict(loads),
        tz=tz,
        priority="medium",
        content_text=content,
        extracted_due=None,
    )
    assert email_day == schedule_day == date(2026, 10, 16)


def test_resolve_placement_deadline_prefers_content_over_llm_due():
    today = date(2026, 10, 12)
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    tz = ZoneInfo("UTC")
    deadline = resolve_placement_deadline(
        today=today,
        weekdays=weekdays,
        tz=tz,
        content_text="submit by 2026-10-16",
        extracted_due="2026-10-14",
    )
    assert deadline == date(2026, 10, 16)


def test_choose_sprint_due_date_lightest_day():
    today = date(2026, 10, 12)
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    loads = {d: 2 for d in weekdays}
    loads[weekdays[3]] = 0
    assert choose_sprint_due_date(None, today, weekdays, loads) == weekdays[3]


def test_truncate_for_schedule():
    assert truncate_for_schedule("short") == "short"
    long = "x" * 500
    out = truncate_for_schedule(long, max_chars=50)
    assert len(out) == 50
    assert out.endswith("…")
