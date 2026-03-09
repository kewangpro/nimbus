# API Specification: Nimbus

## Overview
*   **Base URL:** `/api/v1`
*   **Swagger UI:** Available at `http://localhost:8000/docs` when running locally.
*   **Auth:** SSO (Google / Outlook OAuth2). All endpoints require a valid Bearer token (`Authorization: Bearer <token>`).

## 1. Authentication
*   `GET /auth/login/{provider}`
    *   **Description:** Redirects browser to Google or Microsoft SSO login.
    *   **Providers:** `gmail`, `outlook`.
*   `GET /auth/callback/{provider}`
    *   **Description:** OAuth2 callback handler. Redirects to frontend with `?token=<jwt>`. On first login, auto-creates **"General"** and **"Email"** projects for the user.

## 2. Email & Inbox (SSO-Linked)
*   `GET /email-oauth/inbox`
    *   **Auth:** Requires user to have a linked SSO account.
    *   **Description:** Fetches emails from the **last 3 days** via IMAP/XOAUTH2. Uses raw `protocol.execute` to ensure Outlook compatibility (bypasses `aioimaplib`'s UTF-8 charset injection).
    *   **Response:** `List[dict]` — up to 20 emails, newest first. Each item: `{ id, subject, from, date, snippet }`.
*   `POST /email-oauth/create-task-from-email`
    *   **Body:** `{ "subject": "...", "snippet": "..." }`
    *   **Description:** AI-powered task creation from an email. Creates the issue in the user's **"Email"** project, **auto-assigned to the current user**.
    *   **Response:** `{ "status": "success", "issue_id": "uuid" }`

## 3. Issues (Core)


*   `GET /issues`
    *   **Query Params:** `project_id`, `assignee_id`, `status`, `priority`, `overdue`, `unscheduled`
    *   **Response:** `List[IssueSchema]`
*   `POST /issues`
    *   **Body:** `{ "title": "...", "description": "...", "priority": "...", "due_date": "...", "labels": ["bug","backend"] }`
*   `PATCH /issues/{id}`
    *   **Body:** `{ "status": "DONE", "labels": ["bug","backend"], ... }` (Partial update)
    *   **Note:** Triggers WebSocket event `ISSUE_UPDATED`.
*   `DELETE /issues/{id}`
*   `GET /issues/{id}/dependencies`
    *   **Response:** List of Issues that this issue depends on.
*   `POST /issues/backfill`
    *   **Description:** Enqueues a background job to generate vector embeddings for all issues.
    *   **Response:** `{ "message": "Backfill job queued", "job_id": "uuid" }`

## 4. Projects & Workspaces

*   `GET /projects`
*   `POST /projects`
*   `GET /users/me`

## 5. AI & Intelligence

*   `POST /ai/triage`
    *   **Body:** `{ "title": "...", "description": "...", "issue_id": "uuid?" }`
    *   **Response:** `{ "priority": "...", "labels": [...] }`
*   `POST /ai/similar`
    *   **Body:** `{ "title": "...", "description": "...", "project_id": "uuid?", "exclude_issue_id": "uuid?", "limit": 5 }`
    *   **Response:** List of Issues (ranked by semantic similarity).
*   `POST /ai/search`
    *   **Body:** `{ "query": "...", "limit": 5 }`
    *   **Response:** List of Issues (ranked by semantic similarity).
*   `POST /ai/summary`
    *   **Body:** `{ "issue_id": "uuid", "force": false }`
    *   **Response:** `{ "issue_id": "uuid", "summary": "...", "next_steps": ["..."] }`
*   `POST /ai/query`
    *   **Body:** `{ "text": "...", "project_id": "uuid?", "assignee_id": "uuid?" }`
    *   **Response:** `{ "project_id": "uuid?", "assignee_id": "uuid?", "status": "TODO?", "priority": "HIGH?", "overdue": true?, "unscheduled": false? }`
*   `POST /ai/client-update`
    *   **Body:** `{ "project_id": "uuid?" }`
    *   **Response:** `{ "project_id": "uuid?", "update_text": "..." }`
*   `POST /ai/dependencies`
    *   **Body:** `{ "issue_id": "uuid", "project_id": "uuid?", "limit": 30 }`
    *   **Response:** List of Issues (dependencies)
*   `POST /ai/plan`
    *   **Body:** `{ "text": "Raw natural language plan..." }`
    *   **Response:** `List[PlannedIssue]` (suggested tasks).
*   `POST /ai/schedule`
    *   **Description:** Auto-assigns due dates only for open tasks that are unscheduled or past due, distributing them across the next 5 weekdays to optimize productivity and prevent burnout.
    *   **Response:** `{ "scheduled_count": int, "message": "..." }`

## 6. File Storage

*   `POST /uploads`
    *   **Form Data:** `file`
    *   **Response:** `{ "url": "https://minio.../file.png" }`

## 7. Real-time (WebSocket)

*   `WS /ws/{client_id}` (full path: `/api/v1/ws/{client_id}`)
    *   **Events:**
        *   `{"type": "ISSUE_CREATED", "data": "uuid"}`
        *   `{"type": "ISSUE_UPDATED", "data": "uuid"}`
        *   `{"type": "ISSUE_DELETED", "data": "uuid"}`
