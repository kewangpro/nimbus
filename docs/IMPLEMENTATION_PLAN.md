# Implementation Plan: Nimbus (FastAPI + Next.js)

## Overview
**Strategy:** "Core Mechanics First." We will build a lightning-fast, real-time project management tool first. AI features will *only* be implemented after the core UX (optimistic updates, drag-and-drop) is validated as buttery smooth.

### Tech Stack
*   **Frontend:** Next.js 14, Tailwind, Shadcn/UI, React Query (for Optimistic UI).
*   **Backend:** FastAPI, SQLAlchemy (Async), Redis (Real-time).
*   **Database:** PostgreSQL.
*   **Infrastructure:** Docker Compose.
*   **AI (Local):** Ollama (`gemma3` for chat/triage, `nomic-embed-text` for embeddings).

---

## Phase 1: Foundation (The Skeleton) ✅
**Goal:** A working Monorepo with secure Auth and Database connections.

### 1.1 Infrastructure
*   [x] **Scaffold:** Root `frontend/` and `backend/`.
*   [x] **Docker:** Postgres, Redis, MinIO (No pgvector yet - keep it light).
*   [x] **Backend:** FastAPI setup + Alembic.
*   [x] **Frontend:** Next.js setup + Shadcn/UI.

### 1.2 Auth & Users
*   [x] **API:** OAuth2 Login/Register endpoints.
*   [x] **UI:** Login Page + Session management.
*   [x] **Test:** Verify Auth flow works end-to-end.

---

## Phase 2: The "Linear" Experience (Performance Focus) ✅
**Goal:** Validation. The app must feel instant.

### 2.1 High-Performance Issue Tracking
*   [x] **API:** Standard CRUD for Issues (Title, Desc, Status, Priority).
*   [x] **Performance:** Ensure API response times are <50ms for standard reads.
*   [x] **UI:** List View with Keyboard navigation (Arrow keys to select, Enter to edit).

### 2.2 The Interactive Board
*   [x] **UI:** Kanban Board using `@hello-pangea/dnd`.
*   [x] **Optimistic UI:** React Query mutations must update the UI *immediately* before the server responds.
*   [x] **Real-time:** WebSockets. When User A moves a card, User B sees it move instantly.

### 2.3 🛑 VALIDATION CHECKPOINT
*   *Before moving to AI:*
    *   [x] Is Drag-and-Drop 60fps?
    *   [x] Do updates feel instant?
    *   [x] Is the board stable with 100+ items?

---

## Phase 3: The Intelligence Layer (Local AI with Ollama) ✅
**Goal:** Now that the car handles well, we add the self-driving features using local LLMs.

### 3.1 Vector Infrastructure
*   [x] **DB:** Enable `pgvector` in Docker.
*   [x] **Backfill:** Generate embeddings using `nomic-embed-text` via Ollama.

### 3.2 "Magic" Features
*   [x] **Auto-Triage:** API endpoint to suggest labels/priority using `gemma3`.
*   [x] **Semantic Search:** Replace standard search with Vector Search ("Find that bug about the login crash").
*   [x] **Context:** "Similar Issues" sidebar.

---

## Phase 4: Expansion ✅
*   [x] **File Storage:** MinIO integration.
*   [x] **Client Portal:** External views.

---

## Phase 5: Advanced AI & Planning ✅
**Goal:** Leverage AI for high-level project management and time organization.

### 5.1 AI Planner
*   [x] **API:** Endpoint to break down natural language plans into multiple structured issues.
*   [x] **UI:** Dedicated dialog for plan input and task review.

### 5.2 Time Management
*   [x] **5-Day Sprint View:** Visual columns for the upcoming work week with drag-and-drop rescheduling.
*   [x] **AI Schedule:** AI-powered prioritization and balanced workload distribution (3-5 tasks/day).
*   [x] **Visual Status:** Color-coded tasks (Blue/Todo, Yellow/In Progress, Green/Done) in Calendar.
*   [x] **Persistent UI:** "Show Completed" toggle preference saved in local storage.