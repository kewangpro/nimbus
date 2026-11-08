# API Specification: Nimbus

## Overview
*   **Base URL:** `/api/v1`
*   **Swagger UI:** Available at `http://localhost:8100/docs` when running locally.
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
    *   **Body:** `{ "subject": "...", "snippet": "...", "id": "..." }`
    *   **Description:** AI-powered task creation from an email. Stores the raw email body in `description`, saves the AI summary in `IssueSummary`, and creates the issue in the user's **"General"** project, **auto-assigned to the current user**. Due dates are set within the current 2-week sprint.
    *   **Response:** `{ "status": "success", "issue_id": "uuid" }`
*   `POST /email-oauth/create-tasks-bulk`
    *   **Body:** `List[{ "subject": "...", "snippet": "...", "id": "..." }]`
    *   **Description:** Bulk AI-powered task creation from multiple emails. Stores each email body in `description` and saves AI summaries in `IssueSummary`. Due dates are set within the current 2-week sprint.
    *   **Response:** `{ "status": "success", "issue_ids": ["uuid", "uuid", ...] }`

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
*   `GET /ai/summary/{issue_id}`
    *   **Description:** Retrieves existing AI summary and next steps for an issue if already generated (returns `null` if none exists).
    *   **Response:** `{ "issue_id": "uuid", "summary": "...", "next_steps": ["..."] }` or `null`
*   `POST /ai/summary`
    *   **Body:** `{ "issue_id": "uuid", "force": false }`
    *   **Description:** Generates (or regenerates if `force: true`) a concise summary and concrete next steps for an issue using the local chat LLM, caching results in `IssueSummary`.
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
    *   **Description:** Auto-assigns due dates for open (non-done, non-canceled) tasks assigned to the current user (and owned by clients) that are unscheduled, scheduled for today/future, or mis-scheduled far in the future. **Overdue tasks (due before today) are skipped.** Prioritizes placement needs (unscheduled and far-future outlier tasks) and urgent priorities, redistributing tasks evenly across the next 10 weekdays in stateful batches of 20 (scalable up to 150 tasks). The frontend polls for changes every 4 seconds during the run to render live calendar updates.
    *   **Response:** `{ "scheduled_count": int, "message": "..." }`
*   `GET /ai/schedule/progress`
    *   **Description:** Returns real-time AI auto-scheduling progress for the current user. Polled by the frontend calendar view every 750ms during an active scheduling run to power an animated progress bar with task counts.
    *   **Response:** `{ "status": "idle" | "running" | "done", "processed": int, "total": int, "percent": int }`

## 6. File Storage

*   `POST /uploads`
    *   **Form Data:** `file`
    *   **Response:** `{ "url": "https://minio.../file.png" }`

## 7. Real-time (WebSocket)

*   `WS /ws/{client_id}` (full path: `/api/v1/ws/{client_id}`)
    *   **Events:**
        *   `{"type": "ISSUE_CREATED", "data": "uuid"}`
        *   `{"type": "ISSUE_UPDATED", "data": "uuid"}`
## 8. MCP Server (Model Context Protocol)

*   **SSE URL:** `GET /mcp/sse` (Full URL: `http://localhost:8100/mcp/sse`)
*   **Description:** Implements the MCP SSE transport for external AI assistant integration (e.g. Ensemble).
*   **Protocol:** [Model Context Protocol](https://modelcontextprotocol.io/)
*   **Tools Provided:**
    *   `list_calendar_events` (`days`): List scheduled issues.
    *   `get_task_details` (`task_id`): Fetch full metadata for an issue.
    *   `schedule_task` (`task_id`, `due_date_iso`): Update issue due dates.
    *   `create_calendar_task` (`title`, optional `description`, `due_date_iso`, `project_name`): Create a new issue with a deadline and optional project name.
    *   `search_tasks` (`query`, `limit`): Semantic search for issues using natural language.

### SSE session (JSON-RPC)

SSE is a **session pipe**, not token streaming:

1. `GET` `http://localhost:8100/mcp/sse`; keep it open.
2. Server: `event: endpoint` / `data: /mcp/messages/?session_id=…` (strip `\r`).
3. `POST` JSON-RPC to `http://localhost:8100` + that path.
4. Replies: `event: message` on the GET, matched by `id`.

Envelope:

```json
{"jsonrpc": "2.0", "id": 1, "method": "…", "params": {…}}
```

Notifications omit `id`.

### Smoke-test curls

```bash
mcp_rpc() {
  local BASE="$1"; shift
  local TMP; TMP=$(mktemp)
  curl -NsS -m 20 -H 'Accept: text/event-stream' "$BASE/mcp/sse" | tr -d '\r' > "$TMP" &
  local PID=$!
  local EP="" i=0
  while [ $i -lt 40 ]; do
    EP=$(awk '/^event: endpoint$/{getline; if($1=="data:"){print substr($0,7); exit}}' "$TMP")
    [ -n "$EP" ] && break
    sleep 0.1; i=$((i+1))
  done
  echo "POST $BASE$EP" >&2
  for json in "$@"; do
    curl -sS -m 15 -H 'Content-Type: application/json' -d "$json" "$BASE$EP" >/dev/null
  done
  i=0
  while [ $i -lt 50 ]; do
    grep -q '"id": 2' "$TMP" 2>/dev/null || grep -q '"id":2' "$TMP" && break
    sleep 0.1; i=$((i+1))
  done
  grep '^data: ' "$TMP" | sed 's/^data: //'
  kill $PID 2>/dev/null; wait $PID 2>/dev/null; rm -f "$TMP"
}

INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'
READY='{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
LIST='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

mcp_rpc http://localhost:8100 "$INIT" "$READY" "$LIST" | python3 -m json.tool

mcp_rpc http://localhost:8100 "$INIT" "$READY" \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_calendar_events","arguments":{"days":7}}}'

mcp_rpc http://localhost:8100 "$INIT" "$READY" \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_tasks","arguments":{"query":"sprint","limit":5}}}'

mcp_rpc http://localhost:8100 "$INIT" "$READY" \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"create_calendar_task","arguments":{"title":"curl test"}}}'
```

Two terminals:

```bash
# 1 — keep open; copy data: path
curl -N -H 'Accept: text/event-stream' http://localhost:8100/mcp/sse

# 2
EP='http://localhost:8100/mcp/messages/?session_id=PASTE'
curl -s -H 'Content-Type: application/json' -d "$INIT"  "$EP"
curl -s -H 'Content-Type: application/json' -d "$READY" "$EP"
curl -s -H 'Content-Type: application/json' -d "$LIST"  "$EP"
```

## 9. Audit Logs

*   `GET /audit-logs/`
    *   **Auth:** Requires valid Bearer token.
    *   **Query Params:** `skip` (default 0), `limit` (default 100).
    *   **Description:** Retrieves recent workspace activity, project/issue mutations, authentication events, email-to-task creations, integration failure events (`email.token_refresh_failed`, `email.auth_failed`, `email.connection_failed`, `email.task_creation_failed`, `auth.login_failed`), and recovery events (`email.connection_recovered`).
    *   **Response:** `List[AuditLog]` — sorted descending by `created_at`.
        *   **Schema Details:** Integration error logs include structured classification metadata in `details`:
            *   `error_class`: `"transient"` (auto-retried in background) or `"permanent"` (requires SSO re-authentication or payload remediation).
            *   `is_transient`: Boolean flag (`true` / `false`) used by frontend UI for amber vs. red badge styling.
            *   `error_description`: Human-readable error message (e.g. IMAP timeout reason, OAuth error description).


