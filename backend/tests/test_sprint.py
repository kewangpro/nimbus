from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from app.core.sprint import (
    SPRINT_WEEKDAYS,
    choose_sprint_due_date,
    next_weekdays,
    parse_extracted_due_date,
    resolve_email_task_due_date,
)
from app.models.issue import Issue
from app.models.project import Project
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession


def test_next_weekdays_skips_weekends():
    monday = date(2026, 9, 14)
    days = next_weekdays(monday, SPRINT_WEEKDAYS)
    assert len(days) == 10
    assert days[0] == monday
    assert days[-1] == date(2026, 9, 25)
    assert all(d.weekday() < 5 for d in days)


def test_choose_keeps_deadline_inside_sprint():
    today = date(2026, 9, 15)
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    chosen = choose_sprint_due_date(
        date(2026, 9, 18),
        today,
        weekdays,
        {d: 0 for d in weekdays},
    )
    assert chosen == date(2026, 9, 18)


def test_choose_pulls_far_future_onto_lightest_day():
    today = date(2026, 9, 15)
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    loads = {d: 3 for d in weekdays}
    loads[weekdays[4]] = 0
    chosen = choose_sprint_due_date(
        date(2026, 12, 1),
        today,
        weekdays,
        loads,
    )
    assert chosen == weekdays[4]
    assert chosen <= weekdays[-1]


def test_choose_does_not_create_already_overdue_tasks():
    today = date(2026, 9, 15)
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    chosen = choose_sprint_due_date(
        date(2026, 6, 1),
        today,
        weekdays,
        {d: 0 for d in weekdays},
    )
    assert chosen == weekdays[0]


def test_choose_places_null_due_on_lightest_day():
    today = date(2026, 9, 15)
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    loads = {d: 2 for d in weekdays}
    loads[weekdays[-1]] = 0
    chosen = choose_sprint_due_date(None, today, weekdays, loads)
    assert chosen == weekdays[-1]


def test_urgent_placement_uses_first_two_weekdays():
    today = date(2026, 9, 15)
    weekdays = next_weekdays(today, SPRINT_WEEKDAYS)
    loads = {d: 5 for d in weekdays}
    loads[weekdays[1]] = 1
    loads[weekdays[9]] = 0
    chosen = choose_sprint_due_date(
        None,
        today,
        weekdays,
        loads,
        prefer_early=True,
    )
    assert chosen == weekdays[1]


def test_parse_extracted_due_date_null_strings():
    tz = ZoneInfo("UTC")
    assert parse_extracted_due_date("null", tz) is None
    assert parse_extracted_due_date("2026-09-18", tz).date() == date(2026, 9, 18)


@pytest.mark.asyncio
async def test_resolve_email_task_due_date_avoids_loaded_days(db: AsyncSession):
    user = User(email="sprint-place@example.com", full_name="Sprint")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    project = Project(name="General", owner_id=user.id)
    db.add(project)
    await db.commit()
    await db.refresh(project)

    tz = ZoneInfo("UTC")
    now = datetime(2026, 9, 15, 12, 0, tzinfo=tz)
    weekdays = next_weekdays(now.date(), SPRINT_WEEKDAYS)
    for day in weekdays[:3]:
        db.add(
            Issue(
                title=f"Busy {day}",
                owner_id=user.id,
                assignee_id=user.id,
                project_id=project.id,
                due_date=datetime.combine(day, datetime.min.time(), tzinfo=tz),
                status="todo",
            )
        )
    await db.commit()

    placed = await resolve_email_task_due_date(
        db,
        user,
        extracted_due="2026-06-01",
        priority="medium",
        now=now,
    )
    assert placed.date() == weekdays[3]
    assert placed.date() <= weekdays[-1]
