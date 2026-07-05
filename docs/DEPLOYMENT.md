# Deployment Guide: Nimbus

## 1. Architecture Overview
Nimbus is composed of Dockerized services:

| Service | Runtime | Purpose |
|:---|:---|:---|
| **backend** | Python / FastAPI | REST API + WebSocket server |
| **worker** | Python | Background jobs (AI embeddings, email polling) |
| **postgres** | PostgreSQL 16 | Primary database (with `pgvector`) |
| **redis** | Redis 6 | Job queue + caching |
| **minio** | MinIO | S3-compatible file storage |

The **frontend** (Next.js) runs separately (locally via `npm run dev`, or deployed to Vercel/Netlify in production).

---

## 2. Environment Variables

### Backend (`backend/.env`)
```ini
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/nimbus
REDIS_URL=redis://host:6379/0
SECRET_KEY=<generate with: openssl rand -hex 32>

# AI models (downloaded from Hugging Face on first use)
MLX_CHAT_MODEL=mlx-community/Llama-3.2-1B-Instruct-4bit
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1
HF_TOKEN=your_hugging_face_token  # Optional, but recommended

# MinIO / S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# URLs
BACKEND_URL=http://localhost:8100
FRONTEND_URL=http://localhost:3100

# Google OAuth (for Gmail SSO + Email)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Microsoft OAuth (for Outlook SSO + Email)
MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
```

### Frontend (`frontend/.env.local`)
```ini
NEXT_PUBLIC_API_URL=http://localhost:8100/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8100/api/v1/ws
```

> For production, replace `localhost` URLs with your deployed domain.

---

## 3. OAuth Setup

Nimbus uses **SSO as the primary authentication method**. Both Google and Outlook SSO grant access to the user's IMAP inbox for email integration.

### 🔶 Google (Gmail + Email)
1. Open [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project → **APIs & Services → OAuth consent screen** → "External".
3. **Scopes required:** `openid`, `email`, `profile`, `https://mail.google.com/`
4. Go to **Credentials → + Create Credentials → OAuth client ID**.
5. **Type:** Web application.
6. **Authorized redirect URI:**
   ```
   http://localhost:8100/api/v1/auth/callback/gmail
   ```
7. Copy **Client ID** → `GOOGLE_CLIENT_ID`, **Client Secret** → `GOOGLE_CLIENT_SECRET`.

### 🔷 Microsoft (Outlook + Email)
1. Open [Microsoft Entra admin center](https://entra.microsoft.com/).
2. **Identity → Applications → App registrations → + New registration**.
3. **Account types:** Multitenant + personal Microsoft accounts.
4. **Redirect URI (Web):**
   ```
   http://localhost:8100/api/v1/auth/callback/outlook
   ```
5. **API Permissions:** Add `openid`, `offline_access`, `https://outlook.office.com/IMAP.AccessAsUser.All`.
6. Copy **Application (client) ID** → `MICROSOFT_CLIENT_ID`.
7. **Certificates & secrets → + New client secret** → copy value → `MICROSOFT_CLIENT_SECRET`.

---

## 4. Deployment Options

### Option A: Full Docker Compose (Local / Self-Hosted)
```bash
# 1. Start infrastructure
docker compose up -d

# 2. Run database migrations
docker compose exec backend alembic upgrade head

# 3. Start frontend
cd frontend && npm install && PORT=3100 npm run dev
```
- App: `http://localhost:3100`
- API Docs: `http://localhost:8100/docs`
- MinIO Console: `http://localhost:9001`

> **Note on MLX + Docker:**
> - MLX only runs natively on macOS with Apple Silicon. Inside the Linux Docker container, MLX is not available (as the C++ library is macOS exclusive). Consequently, standard MLX chat completions will fail with a descriptive ModuleNotFoundError inside the container.
> - For full GPU performance and MLX chat features, you should run the backend natively on your host Apple Silicon Mac (using `make backend` or `make run`). Inference will still run locally via `sentence-transformers` on CPU inside the container for vector embeddings.

### Option B: Cloud PaaS (Production)
| Component | Recommended Service |
|:---|:---|
| **Frontend** | Vercel or Netlify |
| **Backend** | Railway, Render, or DigitalOcean App Platform |
| **Database** | Supabase or Neon (both support `pgvector`) |
| **Redis** | Upstash |
| **Storage** | AWS S3 or Cloudflare R2 |
| **AI** | Apple Silicon Mac running the backend locally for MLX GPU inference |

---

## 5. CI/CD (GitHub Actions)
Recommended `.github/workflows/deploy.yml`:
1. **Lint/Test:** Run `pytest` (backend) and `eslint` (frontend) on all PRs.
2. **Build:** Build Docker images on push to `main`.
3. **Deploy:** Webhook or SSH to pull new images on the target platform.

---

## 6. Migrations
Always run migrations before deploying new code:
```bash
# Inside the backend container
alembic upgrade head
```

The `docker compose exec backend alembic upgrade head` command can be added to CI/CD pipelines to automate this step.

---

## 7. Monitoring & Reliability

### Logs
To monitor services in real-time, use Docker Compose logs:
```bash
# View last 100 lines and follow all logs
docker compose logs --tail=100 -f

# Follow specific service logs
docker compose logs -f backend
docker compose logs -f worker
```

### Auditing Active Ports
To verify the status of all Nimbus ports, identify conflicts, and see what processes are running on them on your host machine, run:
```bash
make ports
```
This prints a clean, real-time diagnostic dashboard directly in your CLI.

### Stopping Services
To stop all application servers (Next.js Client, FastAPI Backend, background Async Worker) and core Docker infrastructure containers in one command, run:
```bash
make stop
```


### Resilience
- **Worker Reconnection:** The background worker includes automatic reconnection logic. If Redis or the database becomes temporarily unavailable, the worker will enter a retry loop (5-10s delay) rather than exiting.
- **Worker Crash Recovery:** The worker target in the `Makefile` is run inside an auto-restart loop. If the Python process is aborted or terminated (e.g., due to local GPU memory exceptions), it will automatically restart after 5 seconds to resume processing.
- **Worker Timeout Safety:** To prevent the background worker from hanging indefinitely due to half-closed sockets or un-timed-out connections (e.g., when the IMAP server drops the connection silently), long-running jobs like email polling are wrapped in a 120-second timeout. If the job times out, it is aborted and logged, freeing the worker to process other queued tasks.
- **Job Idempotency:** Scheduled jobs (like email polling) use a Redis-based idempotency check. New jobs are only enqueued if a job of the same type isn't already pending, preventing task accumulation during infrastructure downtime.
