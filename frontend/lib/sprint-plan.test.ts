import test from "node:test"
import assert from "node:assert/strict"
import { addDays, startOfDay, subDays } from "date-fns"
import {
    getSprintPlanRange,
    nextWeekdays,
    SPRINT_WEEKDAYS,
    OVERDUE_LOOKBACK_DAYS,
} from "./sprint-plan.ts"

test("nextWeekdays generates exactly SPRINT_WEEKDAYS weekdays skipping weekends", () => {
    // 2026-09-14 is a Monday
    const monday = new Date(2026, 8, 14)
    const weekdays = nextWeekdays(monday, SPRINT_WEEKDAYS)

    assert.strictEqual(weekdays.length, 10)
    for (const d of weekdays) {
        const day = d.getDay()
        assert.notStrictEqual(day, 0, "Sunday must be excluded")
        assert.notStrictEqual(day, 6, "Saturday must be excluded")
    }

    assert.strictEqual(weekdays[0].getDay(), 1) // Monday
    assert.strictEqual(weekdays[weekdays.length - 1].getDay(), 5) // Friday
})

test("nextWeekdays correctly advances when starting on a weekend", () => {
    // 2026-09-12 is a Saturday
    const saturday = new Date(2026, 8, 12)
    const weekdays = nextWeekdays(saturday, 5)

    assert.strictEqual(weekdays.length, 5)
    assert.strictEqual(weekdays[0].getDay(), 1) // First weekday should be Monday
})

test("getSprintPlanRange defaults start to today and end to 10th weekday when oldestDue is null", () => {
    const today = new Date(2026, 8, 14)
    const { start, end } = getSprintPlanRange(today, null)

    assert.strictEqual(start.getTime(), startOfDay(today).getTime())
    const expectedWeekdays = nextWeekdays(today, SPRINT_WEEKDAYS)
    assert.strictEqual(end.getTime(), expectedWeekdays[expectedWeekdays.length - 1].getTime())
})

test("getSprintPlanRange keeps start as today when oldestDue is in the future", () => {
    const today = new Date(2026, 8, 14)
    const futureDue = addDays(today, 5)
    const { start } = getSprintPlanRange(today, futureDue)

    assert.strictEqual(start.getTime(), startOfDay(today).getTime())
})

test("getSprintPlanRange allows recent overdue lookback up to OVERDUE_LOOKBACK_DAYS", () => {
    const today = new Date(2026, 8, 14)
    const overdue3Days = subDays(today, 3)
    const { start } = getSprintPlanRange(today, overdue3Days)

    assert.strictEqual(start.getTime(), startOfDay(overdue3Days).getTime())
})

test("getSprintPlanRange caps overdue lookback at OVERDUE_LOOKBACK_DAYS for ancient tasks", () => {
    const today = new Date(2026, 8, 14)
    const ancientOverdue = subDays(today, 45)
    const { start } = getSprintPlanRange(today, ancientOverdue)

    const expectedCap = startOfDay(addDays(today, -OVERDUE_LOOKBACK_DAYS))
    assert.strictEqual(start.getTime(), expectedCap.getTime())
})

test("getSprintPlanRange end never extends beyond the 10th weekday even with far-future tasks", () => {
    const today = new Date(2026, 8, 14)
    const farFutureTask = addDays(today, 200)
    const { end } = getSprintPlanRange(today, farFutureTask)

    const expectedEnd = nextWeekdays(today, SPRINT_WEEKDAYS)[SPRINT_WEEKDAYS - 1]
    assert.strictEqual(end.getTime(), expectedEnd.getTime())
})
