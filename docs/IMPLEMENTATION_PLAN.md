# Implementation Plan: Nimbus (FastAPI + Next.js)

## Overview
**Strategy:** "Core Mechanics First." Build a lightning-fast, real-time project management tool first. AI and integrations are layered on top once the core UX is validated.

### Tech Stack
*   **Frontend:** Next.js 15 (Stable), Tailwind CSS, Shadcn/UI, React Query.
*   **Backend:** FastAPI, SQLAlchemy (Async), Alembic, Redis.
*   **Database:** PostgreSQL 16 with `pgvector`.
*   **Infrastructure:** Docker Compose, MinIO.
*   **AI (Local):** Ollama (`gemma3`, `nomic-embed-text`).

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
**Goal:** Additive AI using local Ollama — no cloud dependence.
*   [x] `pgvector` enabled in Docker.
*   [x] Auto-embedding on issue create/update (`nomic-embed-text`).
*   [x] **Auto-Triage:** Priority suggestions (`gemma3`).
*   [x] **Semantic Search:** Vector cosine distance queries.
*   [x] **Similar Issues:** Duplicate detection during creation.

---

## Phase 4: Expansion ✅
*   [x] MinIO file attachment support.
*   [x] Client Portal (restricted, read-only external view).

---

## Phase 5: Advanced AI & Planning ✅
*   [x] **AI Project Planner:** Break down natural language into structured issues.
*   [x] **AI Scheduler:** Distribute unscheduled/overdue tasks across next 5 business days.
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
*   [x] On first login, automatically create **"General"** and **"Email"** projects.
*   [x] "Email" project is the designated target for all email-generated tasks.

### 9.3 Email Inbox (Manual)
*   [x] `GET /email-oauth/inbox` — Fetches the last 3 days of emails via IMAP/XOAUTH2.
*   [x] Outlook compatibility: uses raw `imap.protocol.execute(Command("SEARCH", ...))` to bypass `aioimaplib`'s UTF-8 charset injection.
*   [x] Fetch response handles `bytearray` (Outlook) and `bytes` (Gmail) for email body.
*   [x] `POST /email-oauth/create-task-from-email` — AI-powered manual task creation. Auto-assigned to user.
*   [x] Manual Inbox Refresh: Emails are only fetched on-demand (Refresh button) to save bandwidth.
*   [x] RFC 2047 subject/from decoding: `=?utf-8?B?...?=` encoded headers decoded to readable text.
*   [x] HTML snippet stripping: regex strips HTML tags from marketing emails; prefers `text/plain` part.
*   [x] Timezone-aware email dates: displayed in the user's configured timezone via `formatInTimezone()`.

*   [x] "View Inbox" button in the Email project header opens an inbox modal.

### 9.4 Email Automation (Background Polling)
*   [x] `email_automation_enabled` toggle in User Settings (checkbox).
*   [x] Background worker polls every 60 seconds for UNSEEN emails from the last 3 days.
*   [x] `email_processor.extract_task()` extracts title, description, and priority using `gemma3`.
*   [x] Created tasks are assigned to the inbox owner and placed in their "Email" project.
*   [x] Graceful fallback: if `UNSEEN SINCE <date>` fails, retries with `UNSEEN` only.

### 9.5 Cleanup & Quality
*   [x] Removed legacy `EmailSettings` model, schemas, CRUD, and per-project settings UI.
*   [x] Removed obsolete debug scripts (`check_db_state.py`, `cleanup_data.py`, etc.).
*   [x] Fixed stale `EmailProvider` enum references and `.value` calls in `auth.py`.
*   [x] Added `crud_user` and `crud_project` imports to `auth.py`.
*   [x] Updated all test mocks to match new IMAP search protocol.
*   [x] Python 3.9 Compatibility: Mocked `mcp` in `conftest.py` and handled type union syntax for compatibility.
*   [x] Cleanup utility: `scripts/fix_encoded_titles.py` for retroactive title fixing.
*   [x] **All 11 tests passing.**
