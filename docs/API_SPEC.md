# API Specification: Nimbus

## Overview
*   **Base URL:** `/api/v1`
*   **Documentation:** Auto-generated Swagger UI at `/docs` (when running locally).
*   **Auth:** OAuth2 with Password Flow (Bearer Token).

## 1. Authentication
*   `POST /auth/access-token`
    *   **Body:** `username`, `password` (OAuth2 Password flow)
    *   **Response:** `{ "access_token": "jwt...", "token_type": "bearer" }`
*   `POST /users`
    *   **Body:** `{ "email": "...", "password": "...", "full_name": "...", "timezone": "..." }`
    *   **Notes:** Public signup endpoint.

## 2. Issues (Core)
*   `GET /issues`
    *   **Query Params:** `project_id`, `assignee_id`
    *   **Response:** `List[IssueSchema]`
*   `POST /issues`
    *   **Body:** `{ "title": "...", "description": "...", "priority": "...", "due_date": "..." }`
*   `PATCH /issues/{id}`
    *   **Body:** `{ "status": "DONE", ... }` (Partial update)
    *   **Note:** Triggers WebSocket event `ISSUE_UPDATED`.
*   `DELETE /issues/{id}`
*   `POST /issues/backfill`
    *   **Description:** Manually trigger vector embedding generation for all issues.

## 3. Projects & Workspaces
*   `GET /projects`
*   `POST /projects`
*   `GET /users/me`

## 4. AI & Intelligence (Phase 3 & 5)
*   `POST /ai/triage`
    *   **Body:** `{ "title": "...", "description": "..." }`
    *   **Response:** `{ "priority": "...", "labels": [...] }`
*   `POST /ai/search`
    *   **Body:** `{ "query": "...", "limit": 5 }`
    *   **Response:** List of Issues (ranked by semantic similarity).
*   `POST /ai/plan`
    *   **Body:** `{ "text": "Raw natural language plan..." }`
    *   **Response:** `List[PlannedIssue]` (suggested tasks).
*   `POST /ai/schedule`
    *   **Description:** Auto-assigns due dates only for open tasks that are unscheduled or past due, distributing them across the next 5 weekdays to optimize productivity and prevent burnout.
    *   **Response:** `{ "scheduled_count": int, "message": "..." }`

## 5. File Storage
*   `POST /uploads`
    *   **Form Data:** `file`
    *   **Response:** `{ "url": "https://minio.../file.png" }`

## 6. Real-time (WebSocket)
*   `WS /ws/{client_id}` (full path: `/api/v1/ws/{client_id}`)
    *   **Events:**
        *   `{"type": "ISSUE_CREATED", "data": "uuid"}`
        *   `{"type": "ISSUE_UPDATED", "data": "uuid"}`
        *   `{"type": "ISSUE_DELETED", "data": "uuid"}`
