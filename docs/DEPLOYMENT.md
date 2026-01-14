# Deployment Strategy: Nimbus

## 1. Architecture Overview
Nimbus is composed of three Dockerized services:
1.  **Frontend:** Next.js (Node.js runtime).
2.  **Backend:** FastAPI (Python runtime).
3.  **Worker:** Python Celery/ARQ (Optional, for AI tasks).

Supporting Infrastructure:
*   **Database:** PostgreSQL 15+ (Requires `pgvector` extension).
*   **Cache:** Redis 6+.
*   **Storage:** S3-compatible (AWS S3, Cloudflare R2, or MinIO).

## 2. Environment Variables
### Backend (.env)
```ini
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
REDIS_URL=redis://host:6379/0
SECRET_KEY=openssl-rand-hex-32
OLLAMA_HOST=http://localhost:11434
MINIO_ENDPOINT=...
MINIO_ACCESS_KEY=...
MINIO_SECRET_KEY=...
```

### Frontend (.env.local)
```ini
NEXT_PUBLIC_API_URL=https://api.nimbus.app
NEXT_PUBLIC_WS_URL=wss://api.nimbus.app/ws
```

## 3. Deployment Options

### Option A: Docker Compose (Self-Hosted / MVP)
Best for testing or small internal tools.
1.  Ensure Docker and Ollama are installed on the host.
2.  Run `docker compose up --build -d`.
3.  Frontend available at `localhost:3000`, API at `localhost:8000`.
4.  *Note:* The backend connects to Ollama via `host.docker.internal`.

### Option B: Cloud PaaS (Recommended for Prod)
*   **Frontend:** Deploy `frontend/` to **Vercel** or **Netlify**.
    *   *Config:* Set `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL`.
*   **Backend:** Deploy `backend/` to **Railway**, **Render**, or **DigitalOcean App Platform**.
    *   *Config:* Set env vars. Use the provided `Dockerfile`.
*   **Database:** Use a managed Postgres (e.g., **Supabase** or **Neon**) that supports `pgvector`.
*   **AI:** You will need a hosted Ollama instance or a private GPU node to run the AI engine remotely.

## 4. CI/CD Pipeline (GitHub Actions)
We recommend a simple `.github/workflows/deploy.yml`:
1.  **Lint/Test:** Run `pytest` and `eslint` on PRs.
2.  **Build:** Build Docker images on push to `main`.
3.  **Deploy:** Webhook trigger to update the PaaS or SSH into the VPS to pull new images.

## 5. Migrations
*   **Always** run migrations before deploying the new code.
*   Command: `alembic upgrade head` (Backend container entrypoint should handle this).
