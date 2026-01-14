import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { isBefore, startOfDay, parseISO } from "date-fns"
import { Issue, IssueStatus } from "@/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function isOverdue(issue: Issue): boolean {
  if (!issue.due_date) return false
  if (issue.status === IssueStatus.DONE || issue.status === IssueStatus.CANCELED) return false
  
  const today = startOfDay(new Date())
  const dueDate = startOfDay(parseISO(issue.due_date))
  
  return isBefore(dueDate, today)
}

