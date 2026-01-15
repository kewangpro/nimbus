export enum IssueStatus {
  TODO = "todo",
  IN_PROGRESS = "in_progress",
  DONE = "done",
  CANCELED = "canceled",
}

export enum IssuePriority {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high",
  URGENT = "urgent",
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  owner_id?: string;
  created_at: string;
}

export interface Issue {
  id: string;
  title: string;
  description?: string;
  status: IssueStatus;
  priority: IssuePriority;
  assignee_id?: string;
  owner_id: string;
  project_id: string;
  created_at: string;
  updated_at?: string;
  due_date?: string;
}

export interface User {
    id: string;
    email: string;
    full_name: string;
}
