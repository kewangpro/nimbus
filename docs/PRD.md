# Product Requirements Document (PRD): Nimbus — AI-Native Project Management

## 1. Introduction

### 1.1 Purpose
**Nimbus** is a production-grade project management platform designed to replace legacy tools like Jira/Linear. It combines a real-time Kanban board, semantic AI features, and deep email integration into a single, cohesive product.

### 1.2 Vision
An **AI-Native OS for software delivery**. Unlike legacy tools where AI is a plugin, Nimbus uses AI as the underlying engine — automating planning, triaging issues, and converting emails into tasks automatically.

### 1.3 Market Comparison
| Feature | Jira | Linear | **Nimbus** |
| :--- | :--- | :--- | :--- |
| **Primary Focus** | Enterprise config | Developer velocity | **Local AI + Email Automation** |
| **Data Entry** | Manual forms | Fast forms | **Natural Language + Email** |
| **Search** | Keyword / JQL | Fast keyword | **Semantic / Vector search** |
| **AI Integration** | Bolt-on | Minimal | **Core architecture (Local Ollama)** |
| **Email Integration** | None | None | **SSO-linked IMAP inbox** |

---

## 2. Core Features & Functional Requirements

### 2.1 Project Management
*   **Projects:** Container for issues. Every issue belongs to exactly one project.
*   **Auto-Created Projects:** On first login, Nimbus automatically creates two projects:
    *   **General** — Default workspace for all issues.
    *   **Email** — Connected to the user's SSO inbox for email-to-task automation.
*   **Context Switching:** Users switch between projects to filter Board/List views.

### 2.2 Issue Tracking
*   **Kanban Board:** Drag-and-drop with real-time WebSocket updates.
*   **List View:** Sortable, filterable, high-density table.
*   **My Calendar:** User-centric 5-day sprint timeline showing all assigned tasks across all projects.
*   **Visual Indicators:** Overdue (red), unassigned (blue), unscheduled (amber).

### 2.3 SSO & Email Integration
*   **Single Sign-On:** Login via Google or Outlook (OAuth2 PKCE).
*   **Email Inbox:** View the last 3 days of inbox emails from within Nimbus ("View Inbox" in the Email project).
*   **Manual Task Creation:** Convert any email to a task with one click. Task is automatically assigned to the logged-in user.
*   **Automation Toggle:** Users can enable/disable automatic email-to-task generation in User Settings. When enabled, the background worker polls for new unseen emails every minute.

### 2.4 AI-Native Core (Local Ollama)
*   **AI Project Planner:** Converts unstructured text into structured tasks with auto-scheduled due dates.
*   **AI Scheduler:** Distributes open/overdue tasks across the next 5 business days (Mon-Fri only).
*   **Smart Search:** Semantic search using `pgvector` cosine distance.
*   **Auto-Triage:** Suggests issue priority using `gemma3`.
*   **Similar Issues:** Detects likely duplicates during issue creation.
*   **Issue Summaries:** Generates per-issue AI summaries with next steps.
*   **AI Filters:** Natural language to structured issue filters.
*   **Client Updates:** Drafts weekly client-facing status updates per project.
*   **Dependency Detection:** Identifies and persists issue dependencies.

### 2.5 User Roles & Access
*   **Roles:** Admin, Member, Client.
*   **Client Portal:** Restricted view showing only relevant client issues.

### 2.6 File Storage
*   **Attachments:** MinIO (S3-compatible) for secure file uploads.

---

## 3. Technical Architecture
*   **Frontend:** Next.js 15 (Stable), Tailwind CSS, Shadcn/UI, React Query.
*   **Backend:** FastAPI (Python), SQLAlchemy (Async), Alembic.
*   **Database:** PostgreSQL 16 with `pgvector`.
*   **Infrastructure:** Docker Compose, Redis, MinIO.
*   **AI Engine:** Local Ollama (`gemma3`, `nomic-embed-text`).
*   **Email:** IMAP/XOAUTH2 via `aioimaplib` using SSO tokens.

---

## 4. Non-Functional Requirements
*   **Performance:** Dashboard load < 1.5s; real-time sync < 200ms.
*   **Privacy:** All AI processing runs locally on the host machine via Ollama. No data leaves the user's environment.
*   **Reliability:** OAuth tokens are automatically refreshed. Email polling recovers gracefully on transient failures.
