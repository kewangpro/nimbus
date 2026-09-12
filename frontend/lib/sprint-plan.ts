import { addDays, isAfter, isBefore, startOfDay } from "date-fns"

export const SPRINT_WEEKDAYS = 10
export const OVERDUE_LOOKBACK_DAYS = 7

export function nextWeekdays(from: Date, count: number): Date[] {
    const days: Date[] = []
    let current = startOfDay(from)
    while (days.length < count) {
        const dayOfWeek = current.getDay()
        if (dayOfWeek !== 0 && dayOfWeek !== 6) {
            days.push(current)
        }
        current = addDays(current, 1)
    }
    return days
}

/**
 * Stable sprint grid: optional 7-day overdue lookback through the 10th
 * weekday from today. Oldest/newest due dates never change the width.
 */
export function getSprintPlanRange(today: Date, oldestDue: Date | null): { start: Date; end: Date } {
    const todayStart = startOfDay(today)
    const weekdays = nextWeekdays(todayStart, SPRINT_WEEKDAYS)
    const end = weekdays[weekdays.length - 1]
    let start = todayStart

    if (oldestDue) {
        const oldest = startOfDay(oldestDue)
        if (isBefore(oldest, todayStart)) {
            const lookbackCap = addDays(todayStart, -OVERDUE_LOOKBACK_DAYS)
            start = isBefore(oldest, lookbackCap) ? lookbackCap : oldest
        }
    }

    // Never let lookback eat the 10-weekday horizon
    if (isAfter(start, end)) {
        start = todayStart
    }

    return { start, end }
}
