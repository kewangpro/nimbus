import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { isBefore, startOfDay, parseISO } from "date-fns"
import { Issue, IssueStatus } from "@/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

import { toZonedTime } from "date-fns-tz"

export function isOverdue(issue: Issue, timezone: string = "UTC"): boolean {
  if (!issue.due_date) return false
  if (issue.status === IssueStatus.DONE || issue.status === IssueStatus.CANCELED) return false

  // Get start of today in the user's timezone
  const now = new Date()
  const zonedNow = toZonedTime(now, timezone)
  const today = startOfDay(zonedNow)

  // Get start of due date in the user's timezone
  // issue.due_date is UTC ISO string
  const zonedDueDate = toZonedTime(issue.due_date, timezone)
  const dueDate = startOfDay(zonedDueDate)

  return isBefore(dueDate, today)
}

