# Implementation Plan: Nimbus (FastAPI + Next.js)

## Overview
**Strategy:** "Core Mechanics First." Build a lightning-fast, real-time project management tool first. AI and integrations are layered on top once the core UX is validated.

### Tech Stack
*   **Frontend:** Next.js 15 (Stable), Tailwind CSS, Shadcn/UI, React Query.
*   **Backend:** FastAPI, SQLAlchemy (Async), Alembic, Redis.
*   **Database:** PostgreSQL 16 with `pgvector`.
*   **Infrastructure:** Docker Compose, MinIO.
*   **AI (Local):** MLX + `mlx-lm` (Gemma 3, Apple Silicon), `sentence-transformers` (nomic-embed-text-v1).

---

## Phase 1: Foundation ✅
**Goal:** Working monorepo with secure Auth and Database connections.
*   [x] Scaffold `frontend/` and `backend/` directories.
*   [x] Dockerize Postgres, Redis, MinIO.
*   [x] FastAPI setup + Alembic migrations.
*   [x] Next.js setup + Shadcn/UI.
*   [x] OAuth2 auth endpoints + login UI.

---

## Phase 2: Core UX — The "Linear" Experience ✅
**Goal:** App must feel instant. Validation before adding complexity.
*   [x] CRUD for Issues (title, description, status, priority).
*   [x] API response times < 50ms for reads.
*   [x] Kanban Board with `@hello-pangea/dnd` (60fps drag-and-drop).
*   [x] Optimistic UI via React Query mutations.
*   [x] WebSocket real-time sync (multi-user).
*   [x] List View with sortable columns and keyboard navigation.

---

## Phase 3: Intelligence Layer (Local AI) ✅
**Goal:** Additive AI using local MLX — no cloud dependence.
*   [x] `pgvector` enabled in Docker.
*   [x] Auto-embedding on issue create/update (`nomic-ai/nomic-embed-text-v1` via sentence-transformers).
*   [x] **Auto-Triage:** Priority suggestions (Gemma 3 via mlx-lm).
*   [x] **Semantic Search:** Vector cosine distance queries.
*   [x] **Similar Issues:** Duplicate detection during creation.

---

## Phase 4: Expansion ✅
*   [x] MinIO file attachment support.
*   [x] Client Portal (restricted, read-only external view).

---

## Phase 5: Advanced AI & Planning ✅
*   [x] **AI Project Planner:** Break down natural language into structured issues.
*   [x] **AI Scheduler:** Redistribute open tasks (unscheduled, scheduled for today/future, or mis-scheduled far future) across next 5 business days in stateful batches of 20. Calendar updates live every 4s during the run. **Overdue tasks are skipped to prevent automatic rescheduling.**
*   [x] **5-Day Sprint Calendar:** Visual per-user timeline with drag-and-drop rescheduling.
*   [x] **AI Summary:** Per-issue summary with next steps (cached by content hash).
*   [x] **AI Filters:** Natural language to structured issue filters (List View).
*   [x] **Client Update Drafts:** Weekly status summaries for each project.
*   [x] **Dependency Detection:** Identifies and stores issue-to-issue dependencies.

---

## Phase 6: Refinement & Polish ✅
*   [x] Calendar range auto-expands to show all relevant tasks (min 5 days).
*   [x] AI Scheduler strictly respects business days (Mon-Fri only).
*   [x] "Show Weekends" toggle persisted in local storage.
*   [x] Overdue task indicators (red) across Board, List, and Calendar.
*   [x] "Do Today" and "Complete" quick actions in Issue Detail modal.
*   [x] Global timezone support (user-configurable, stored as UTC).

---

## Phase 7: Multi-Project Workspace ✅
*   [x] `Project` entity + `issues.project_id` FK.
*   [x] Persistent sidebar navigation.
*   [x] My Calendar is global (all projects, current user's tasks).
*   [x] Board/List filtered by selected project.
*   [x] Assignee avatars, due date picker, visual signal system (overdue / unassigned / unscheduled).

---

## Phase 8: AI Enhancements ✅
*   [x] Similar Issues endpoint and UI integration.
*   [x] Issue Summary with background caching and invalidation.
*   [x] AI Filters for List View.
*   [x] Client Update drafts.
*   [x] Dependency extraction and persistence.

---

## Phase 9: SSO & Email Integration ✅
**Goal:** Streamline authentication and automate task ingestion from personal email.

### 9.1 SSO Authentication
*   [x] OAuth2 flows for Google (Gmail) and Microsoft (Outlook).
*   [x] User model with `oauth_provider`, `oauth_access_token`, `oauth_refresh_token`, `oauth_token_expires_at`.
*   [x] Auto-refresh token on expiry.
*   [x] Social login buttons on the frontend.

### 9.2 Auto-Project Setup
*   [x] On first login, automatically create a **"General"** project.
*   [x] "General" project is the designated target for all tasks, including those generated from email.

### 9.3 Email Inbox (Manual)
*   [x] `GET /email-oauth/inbox` — Fetches the last 3 days of emails via IMAP/XOAUTH2.
*   [x] Outlook compatibility: uses raw `imap.protocol.execute(Command("SEARCH", ...))` to bypass `aioimaplib`'s UTF-8 charset injection.
*   [x] Fetch response handles `bytearray` (Outlook) and `bytes` (Gmail) for email body.
*   [x] `POST /email-oauth/create-task-from-email` — AI-powered manual task creation. Auto-assigned to user.
*   [x] Manual Inbox Refresh: Emails are only fetched on-demand (Refresh button) to save bandwidth.
*   [x] RFC 2047 subject/from decoding: `=?utf-8?B?...?=` encoded headers decoded to readable text.
*   [x] HTML snippet stripping: regex strips HTML tags from marketing emails; prefers `text/plain` part.
*   [x] Timezone-aware email dates: displayed in the user's configured timezone via `formatInTimezone()`.

*   [x] "View Inbox" button in the header opens an inbox modal.

### 9.4 Email Automation (Background Polling)
*   [x] `email_automation_enabled` toggle in User Settings (checkbox).
*   [x] Background worker polls every 60 seconds for UNSEEN emails from the last 3 days.
*   [x] `email_processor.extract_task()` extracts title, description, and priority using Gemma 3 via MLX.
*   [x] Created tasks are assigned to the inbox owner and placed in their "General" project.
*   [x] Graceful fallback: if `UNSEEN SINCE <date>` fails, retries with `UNSEEN` only.

### 9.5 Cleanup & Quality
*   [x] Removed legacy `EmailSettings` model, schemas, CRUD, and per-project settings UI.
*   [x] Removed obsolete debug scripts (`check_db_state.py`, `cleanup_data.py`, etc.).
*   [x] Fixed stale `EmailProvider` enum references and `.value` calls in `auth.py`.
*   [x] Added `crud_user` and `crud_project` imports to `auth.py`.
*   [x] Updated all test mocks to match new IMAP search protocol.
*   [x] Python 3.9 Compatibility: Mocked `mcp` in `conftest.py` and handled type union syntax for compatibility.
*   [x] Cleanup utility: `scripts/fix_encoded_titles.py` for retroactive title fixing.
*   [x] **All 87 tests passing with robust coverage expansion (reaching 70% overall).**

---

## Phase 10: Reliability & Auditing ✅
**Goal:** Harden the system for production and ensure operational visibility.

*   [x] **Atomic Email Polling:** Use `BODY.PEEK` and explicit flagging to prevent email loss.
*   [x] **Expanded Audit Logging:** Track authentication (SSO login), user profile updates, manual email-to-task creation, AI backfill jobs, and file uploads.
*   [x] **Detailed Auditing (Titles & Changes):** Every log entry captures the entity title/name (e.g., Issue Title) and tracks specific field-level changes (e.g., `status`, `priority`) during updates.
*   [x] **Enhanced Documentation:** Updated `AUDITS.md` and `README.md` with detailed action references and data structure info.

---

## Phase 11: System Resilience & Optimization ✅
**Goal:** Ensure the system recovers gracefully from infrastructure failure.

*   [x] **Worker Reconnection:** Implemented error handling and retry loops in the background worker for Redis/Postgres connection drops.
*   [x] **Job Idempotency:** Added a check to prevent redundant periodic jobs (e.g., email polling) from accumulating in the queue when the worker is offline.
*   [x] **Improved Monitoring:** Added standard logging commands and monitoring guides to `README.md` and `DEPLOYMENT.md`.
---
151: 
## Phase 12: External AI Integration (MCP) ✅
**Goal:** Enable external AI assistants (e.g., Claude Desktop) to directly manage Nimbus data via the Model Context Protocol.

*   [x] **FastMCP Server:** Integrated `FastMCP` into the FastAPI backend.
*   [x] **SSE Transport:** Mounted MCP at `GET /mcp/sse` for standard cross-tool connectivity.
*   [x] **Calendar Tools:** Implemented `list_calendar_events` (with chronological sorting and timeframe windowing) and `schedule_task`.
*   [x] **Task Management Tools:** Implemented `create_calendar_task` (with dynamic project selection) and `get_task_details`.
*   [x] **Semantic Search Tool:** Exposed `search_tasks` to allow external AIs to find issues using the local vector database.
*   [x] **Robust Error Handling:** Comprehensive try-except blocks with actionable feedback for AI self-correction.
*   [x] **Automated Testing:** Dedicated test suite (`tests/test_mcp_server.py`) with enhanced mocking for Python 3.9 compatibility.

---

## Phase 13: Email Processor Refinement & JSON Robustness ✅
**Goal:** Reduce noise from automated email tasks and ensure valid JSON extraction even with smaller local models.

*   [x] **Negative Prompting:** Updated system prompt to explicitly ignore boilerplate links (Unsubscribe, More Info, Help Center).
*   [x] **Few-Shot Advertising Filtering:** Added examples of marketing emails returning an empty list `[]` to guide the AI.
*   [x] **JSON Pre-cleaning:** Automated stripping of markdown blocks and trailing comments (e.g., `#` or `//`) from AI responses.
*   [x] **Single-Quote Fallback:** Implemented `ast.literal_eval` to handle AI-generated single-quoted dictionaries.
*   [x] **Strict Validation:** Only processes items that include a valid `title` key, filtering out conversational noise.
*   [x] **Bulk Creation Stability:** Fixed Pydantic validation error by sanitizing `"null"` strings in the `due_date` field.

---

## Phase 14: Scheduler Intelligence Optimization ✅
**Goal:** Maximize scheduling accuracy for local 1B models when handling large backlogs.

*   [x] **Index Mapping:** Replaced 36-character UUIDs with short integers (`0, 1, 2...`) in prompts to save tokens and eliminate model confusion.
*   [x] **Day Number Strategy:** Directed AI to output `day_number` (1-5) instead of date strings, preventing hallucinated future months.
*   [x] **Priority Mapping:** Implemented numerical prioritization (`URGENT=0`, `HIGH=1`) to ensure correct sorting in batch processing.
*   [x] **Skip Overdue Items:** Modified AI Scheduler to explicitly exclude already overdue items from the rescheduling pool, ensuring user-defined deadlines are respected.

162: 
