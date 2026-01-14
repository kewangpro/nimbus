# Nimbus ☁️

**AI-Native Project Management System**

Nimbus is a modern, high-performance project management tool designed to replace legacy systems. It features a real-time Kanban board, local AI integration for planning, triage, and semantic search, and a dedicated client portal.

## 🚀 Features

*   **Real-time Collaboration:** Live updates via WebSockets ensure your team is always in sync.
*   **Interactive Views:**
    *   **Kanban Board:** Drag-and-drop interface with optimistic UI updates.
    *   **5-Day Sprint View:** Focused timeline for managing the current week's workload. Supports drag-and-drop rescheduling and status-based coloring.
    *   **List View:** Fast, high-density issue tracking for bulk review.
*   **Issue Management:**
    *   **Detail View:** Comprehensive modal for viewing and editing issue details, including status, priority, and descriptions.
    *   **Persistent Preferences:** Remembers UI settings like the "Show Completed" toggle across sessions.
*   **Local AI Intelligence (Ollama):**
    *   **🤖 AI Project Planner:** Turn natural language "brain dumps" into structured project tasks automatically.
    *   **📅 AI Schedule:** Intelligently distributes open tasks across the next 5 days to optimize output and prevent burnout.
    *   **✨ Smart Search:** A dedicated search dialog in the header that uses vector embeddings to find relevant issues by meaning.
    *   **🪄 AI Auto-Triage:** A "Wand" button in the Create Issue dialog that automatically suggests the issue priority using `gemma3`.
    *   **Automatic Embedding:** Every issue is automatically vectorized on creation/update using `nomic-embed-text`.
*   **Role-Based Access:** Distinct views for Admins, Members, and Clients.
*   **File Storage:** Secure attachment handling with MinIO (S3 compatible).

## 🛠️ Tech Stack

*   **Frontend:** Next.js 14, Tailwind CSS, Shadcn/UI, React Query.
*   **Backend:** FastAPI (Python), SQLAlchemy (Async), Alembic.
*   **Database:** PostgreSQL with `pgvector`.
*   **Infrastructure:** Docker Compose, Redis, MinIO.
*   **AI:** Ollama (Local LLM Inference).

## 📦 Prerequisites

1.  **Docker & Docker Compose**
2.  **Node.js 18+ & npm**
3.  **Python 3.9+**
4.  **Ollama** (Running locally)
    *   `ollama pull gemma3`
    *   `ollama pull nomic-embed-text`

## 🏃‍♂️ Quick Start

### 1. Start Infrastructure
Run the database, Redis, and MinIO services:
```bash
docker compose up -d
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run Migrations
alembic upgrade head

# Start API Server
uvicorn app.main:app --reload
```
API Documentation: `http://localhost:8000/docs`

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
App: `http://localhost:3000`

## 🧠 AI Configuration
Ensure **Ollama** is running on your host machine at `http://localhost:11434` (default).
The backend connects to it via `http://host.docker.internal:11434` if running in Docker, or `localhost` if running locally.

To test AI features:
1.  **Planner:** Click "AI Plan" in the header and type your project thoughts.
2.  **Schedule:** Go to "Calendar" tab and click "AI Schedule" to organize your week.
3.  **Search:** Click "Smart Search..." and find issues by meaning.

## 📚 Documentation

*   [Product Requirements (PRD)](docs/PRD.md)
*   [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
*   [API Specification](docs/API_SPEC.md)
*   [AI Architecture](docs/AI_ARCHITECTURE.md)
*   [UX Design](docs/UX_Design.md)
*   [Deployment Guide](docs/DEPLOYMENT.md)

## 📝 License
MIT
