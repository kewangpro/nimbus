# AI Architecture: Nimbus (Local AI + Email Intelligence)

## 1. Overview
The AI layer is **additive** — the core project management system works without it. Intelligence is applied asynchronously using **local LLMs via Ollama**, ensuring complete privacy and zero inference cost. Long-running AI tasks are processed by a Redis-backed background worker.

Email intelligence is powered by the same AI pipeline: incoming emails are parsed and structured by `gemma3` into tasks, using the user's IMAP inbox via XOAUTH2.

---

## 2. Models & Providers

| Model | Purpose | Provider |
|:---|:---|:---|
| `nomic-embed-text` | Issue embeddings for semantic search | Ollama (local) |
| `gemma3` | Planning, triage, summarization, email extraction | Ollama (local) |

**Ollama API:** `http://localhost:11434` (or `http://host.docker.internal:11434` inside Docker)

---

## 3. Data Schema (pgvector)

**Issue embeddings** (semantic search):
```sql
CREATE TABLE issue_embeddings (
    issue_id UUID PRIMARY KEY REFERENCES issues(id) ON DELETE CASCADE,
    embedding vector(768),  -- nomic-embed-text dimensions
    content_hash VARCHAR(64),
    last_updated TIMESTAMP DEFAULT NOW()
);
```

**Issue summaries** (cached to avoid regeneration):
```sql
CREATE TABLE issue_summaries (
    issue_id UUID PRIMARY KEY REFERENCES issues(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    next_steps TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    last_updated TIMESTAMP DEFAULT NOW()
);
```

**Issue dependencies** (directed links):
```sql
CREATE TABLE issue_links (
    issue_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    depends_on_id UUID NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    PRIMARY KEY (issue_id, depends_on_id)
);
```

---

## 4. AI Feature Implementation

### 4.1 Auto-Triage
*   **Input:** Issue `title` + `description`.
*   **Output:** Suggested `priority` (`URGENT`, `HIGH`, `MEDIUM`, `LOW`).
*   **Trigger:** Wand (🪄) button in Create Issue dialog.

### 4.2 AI Project Planner
*   **Input:** Unstructured natural language plan.
*   **Output:** JSON array of `PlannedIssue` objects with `title`, `description`, `priority`, and `due_date`.
*   **Scheduling:** Distributes tasks across the next 5 business days (Mon-Fri), respecting existing load.

### 4.3 AI Scheduler
*   **Input:** All open issues that are unscheduled or past due.
*   **Output:** Updated `due_date` for each affected issue.
*   **Logic:** Prioritizes `URGENT` items early, limits ~3-5 tasks/day to prevent burnout, skips weekends.

### 4.4 Semantic Search
*   **Input:** User query string.
*   **Output:** Issues ranked by `pgvector` cosine distance (`<=>`) to the query embedding.

### 4.5 Similar Issues
*   **Input:** Draft issue title + description.
*   **Output:** Top N nearest issues (excluding the issue being created).
*   **Use case:** Duplicate detection during issue creation.

### 4.6 Issue Summaries
*   **Input:** Issue `title` + `description`.
*   **Output:** `summary` + `next_steps[]`, cached by content hash to avoid redundant API calls.

### 4.7 Natural Language Filters
*   **Input:** Free-text query (e.g. "high priority overdue tasks").
*   **Output:** Structured filter object (`status`, `priority`, `overdue`, `unscheduled`, etc.).

### 4.8 Client Update Drafts
*   **Input:** All issues in a project.
*   **Output:** Weekly status update narrative for client-facing communication.

### 4.9 Dependency Extraction
*   **Input:** Issue + candidate list of related issues.
*   **Output:** List of issues that the given issue depends on.
*   **Storage:** Persisted in `issue_links` table.

### 4.10 Email Task Extraction
*   **Input:** Email `subject` + `body` snippet.
*   **Output:** Structured task with `title`, `description`, `priority`, and optional `due_date`.
*   **Used by:** Both manual inbox task creation and automatic background email polling.

---

## 5. Email Integration Architecture

### IMAP Connection
*   **Library:** `aioimaplib` (async IMAP client).
*   **Auth:** XOAUTH2 using the user's SSO `oauth_access_token`.
*   **Token Refresh:** Tokens are checked before every IMAP connection. If expired (within 5 minutes), they are refreshed automatically via the provider's token endpoint.

### IMAP Search (Outlook Compatibility)
*   `aioimaplib`'s `imap.search()` injects a `CHARSET UTF-8` header automatically. Outlook rejects this with `NO [BADCHARSET (US-ASCII)]`.
*   **Fix:** Use `imap.protocol.execute(Command("SEARCH", tag, criteria))` directly to send raw ASCII-compatible IMAP commands, identical to how `AUTHENTICATE` is handled.

### Email Body Decoding
*   `imap.fetch()` returns the email body as `bytearray` (Outlook) or `bytes` (Gmail).
*   **Fix:** `isinstance(data, (bytes, bytearray))` check before calling `.decode()`.

### Polling Flow
1. Background worker enqueues a poll job every 60 seconds.
2. Query all users with `oauth_access_token IS NOT NULL AND email_automation_enabled = TRUE`.
3. For each user: refresh token if needed → connect to IMAP → search `UNSEEN SINCE <3 days ago>`.
4. For each email: extract task with `email_processor` → create issue in user's "Email" project → assign to user.

---

## 6. Controls & Performance
*   **Async:** All AI calls use `ollama.AsyncClient` — non-blocking.
*   **Debounce:** UI updates are immediate (optimistic); vector updates happen on save.
*   **Fallback:** If Ollama is offline, AI endpoints return HTTP 500. No keyword fallback exists — treat AI features as optional.
*   **Background Jobs:** Embedding backfills and email polling run via the async worker to avoid blocking the API.
*   **Caching:** Issue summaries are content-hash cached; regenerated only when issue content changes.
