# Product Requirements Document (PRD): "Nimbus" - Next-Gen Project Management System

## 1. Introduction
### 1.1 Purpose
The purpose of this document is to define the requirements for **Nimbus**, a comprehensive project management platform designed to replace legacy tools like Jira and streamline workflows like Linear. Nimbus is a production-grade system supporting full lifecycle software development, with a strong emphasis on collaboration and local AI-driven efficiency.

### 1.2 Vision
To build an **AI-Native OS for software delivery**. Unlike legacy tools where AI is a plugin, Nimbus uses AI as the underlying engine to understand project context, automate planning, and interface with users via natural language.

### 1.3 Market Comparison
| Feature | Jira | Linear | Nimbus |
| :--- | :--- | :--- | :--- |
| **Primary Focus** | Enterprise configuration | Developer velocity | **Local AI Automation & Context** |
| **Data Entry** | Manual Forms | Fast Forms | **Natural Language / AI Planning** |
| **Search** | Keyword / JQL | Fast Keyword | **Semantic / Vector Search** |
| **AI Integration** | Bolt-on | Minimal | **Core Architecture (Local Ollama)** |

## 2. Core Features & Functional Requirements

### 3.1 Story Tracking & Issue Management
*   **Views:**
    *   **Kanban Board:** Visual status columns with real-time drag-and-drop.
    *   **5-Day Sprint View:** Focused productivity timeline for the week with drag-and-drop rescheduling.
    *   **List View:** Fast review for bulk updates.
*   **Management:** Comprehensive Issue Detail modal for editing and deletion.

### 3.2 User Roles & Client Access (RBAC)
*   **Roles:** Admin, Member, Client.
*   **Client Portal:** A restricted, simplified view where clients only see issues relevant to them.

### 3.3 AI-Native Core (Local Ollama)
*   **AI Project Planner:** Extracts actionable tasks from unstructured text input.
*   **AI Scheduler:** Auto-assigns due dates to balance workload over the next 5 days.
*   **Smart Search:** Semantic search using vector embeddings.
*   **Auto-Triage:** Automatic priority suggestions.

### 3.4 File Storage
*   **Attachments:** Full support for file uploads via MinIO.

## 4. Technical Architecture
*   **Frontend:** Next.js 14, Tailwind, Shadcn/UI, React Query.
*   **Backend:** FastAPI (Python), SQLAlchemy (Async).
*   **Database:** PostgreSQL with `pgvector` & Redis.
*   **AI Engine:** Local Ollama (`gemma3`, `nomic-embed-text`).

## 5. Non-Functional Requirements
*   **Performance:** Dashboard load under 1.5s; Real-time sync <200ms.
*   **Privacy:** All AI processing happens locally on the host machine.