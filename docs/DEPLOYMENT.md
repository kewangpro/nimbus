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
OLLAMA_HOST=http://localhost:11434

# MinIO / S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# URLs
BACKEND_URL=http://localhost:8000
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
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/ws
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
   http://localhost:8000/api/v1/auth/callback/gmail
   ```
7. Copy **Client ID** → `GOOGLE_CLIENT_ID`, **Client Secret** → `GOOGLE_CLIENT_SECRET`.

### 🔷 Microsoft (Outlook + Email)
1. Open [Microsoft Entra admin center](https://entra.microsoft.com/).
2. **Identity → Applications → App registrations → + New registration**.
3. **Account types:** Multitenant + personal Microsoft accounts.
4. **Redirect URI (Web):**
   ```
   http://localhost:8000/api/v1/auth/callback/outlook
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
- API Docs: `http://localhost:8000/docs`
- MinIO Console: `http://localhost:9001`

> **Note:** The backend connects to Ollama via `http://host.docker.internal:11434`. Ensure Ollama is running locally with:
> ```bash
> ollama pull gemma3
> ollama pull nomic-embed-text
> ```

### Option B: Cloud PaaS (Production)
| Component | Recommended Service |
|:---|:---|
| **Frontend** | Vercel or Netlify |
| **Backend** | Railway, Render, or DigitalOcean App Platform |
| **Database** | Supabase or Neon (both support `pgvector`) |
| **Redis** | Upstash |
| **Storage** | AWS S3 or Cloudflare R2 |
| **AI** | Private GPU node running Ollama |

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
