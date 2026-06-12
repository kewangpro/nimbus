# AI Architecture: Nimbus (Local AI + Email Intelligence)

## 1. Overview
The AI layer is **additive** — the core project management system works without it. Intelligence is applied asynchronously using **local LLMs via MLX on Apple Silicon**, ensuring complete privacy and zero inference cost. Long-running AI tasks are processed by a Redis-backed background worker.

Email intelligence is powered by the same AI pipeline: incoming emails are parsed and structured by Gemma 3 into tasks, using the user's IMAP inbox via XOAUTH2.

---

## 2. Models & Providers

| Model | Purpose | Library |
|:---|:---|:---|
| `mlx-community/gemma-3-4b-it-4bit` | Planning, triage, summarization, email extraction | `mlx-lm` (Apple Silicon GPU) |
| `nomic-ai/nomic-embed-text-v1` | Issue embeddings for semantic search | `sentence-transformers` |

Models are downloaded from Hugging Face on first use and cached locally. Use `HF_TOKEN` in your environment to enable higher rate limits. The chat model is configurable via the `MLX_CHAT_MODEL` env var; the embedding model via `EMBEDDING_MODEL`.

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
*   **Input:** All open issues within the 10-day horizon (Redistributes the entire active sprint + backlog).
*   **Output:** Optimized `due_date` for each issue.
*   **Logic:**
    *   **Capacity:** Scalable to **100+ tasks** using **Stateful Batching** (20 tasks per iteration).
    *   **Total Sprint Balance:** Unlike simple scheduling, this mode includes tasks already in the 5-day window to ensure the *entire week* is re-balanced if one day is overloaded.
    *   **Stateful Load Awareness:** Each batch prompt includes a `CURRENT WORKLOAD` summary, allowing the AI to see how many tasks are already assigned to Days 1-5.
    *   **Deterministic Safety Layer:** The backend enforces a strict `Least-Busy-Day` override. If the AI suggests an overloaded day, the system automatically pulls the task to the truly lightest day.
    *   **100% Coverage Loop:** A final verification pass ensures every single task identified in the redistribution pool receives an update, using round-robin assignment for any items skipped by the AI.
...
*   **De-duplication Mechanism:**
    *   **Layer 1 (Local):** Identical task titles within a single AI response are collapsed.
    *   **Layer 2 (Global):** Before creation, the system queries the DB for existing issues with the same title for that user, preventing "Email Loop" duplicates from marketing bundles or redundant polls.
*   **Validation:** Every extracted task is validated for required fields (`title`) and sanitized before database insertion.

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
*   **Output:** One or more structured tasks with `title`, `description`, `priority`, and optional `due_date`.
*   **Prompting Strategy:** Uses an advanced system prompt with explicit **negative constraints** (ignore boilerplate, marketing footers, "Unsubscribe" links) and **few-shot examples** of both actionable tasks and non-actionable advertisements (which should return `[]`).
*   **Parsing Resilience:**
    *   **Level 1:** Standard JSON parse after pre-cleaning (removing markdown code blocks and trailing comments).
    *   **Level 2:** Fallback to `ast.literal_eval` to handle AI-generated "JSON" that uses single quotes.
    *   **Level 3:** Regex-based block extraction (handles conversational filler before/after JSON).
    *   **Level 4:** Manual brace-matching parser for partial or multiple JSON objects.
*   **Validation:** Every extracted task is validated for required fields (`title`) and sanitized before database insertion.
*   **Fallback Mechanism:** If all AI parsing levels fail or return zero tasks for an email that was expected to be actionable, the system falls back to creating a single task with the title `Auto-Task: <Subject>` and the full email body as the description. This ensures zero data loss.
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
4. For each email: extract task with `email_processor` → create issue in user's "General" project → assign to user.


---

## 6. Controls & Performance
*   **Async:** All AI calls run in a single-worker `ThreadPoolExecutor` wrapped with `asyncio.run_in_executor` — non-blocking to the FastAPI event loop. MLX requires sequential GPU access, hence `max_workers=1`.
*   **Lazy loading:** Models are loaded on first inference call and kept in memory for the process lifetime.
*   **Debounce:** UI updates are immediate (optimistic); vector updates happen on save.
*   **Context Window:** Completion calls use a `max_tokens` limit of **4096** (increased from 2048) to support large structured outputs (e.g., 100+ task schedules).
*   **Fallback:** If inference fails (e.g. model not yet downloaded), AI endpoints return HTTP 500. No keyword fallback — treat AI features as optional.
*   **Consolidated Background Jobs:** Embedding backfills and email polling run via an integrated async worker task inside the main FastAPI process to minimize memory footprint.
*   **Caching:** Issue summaries are content-hash cached; regenerated only when issue content changes.
*   **Memory Management:** The system releases unused Metal GPU memory after each generation by calling `mlx.core.metal.clear_cache()`. This minimizes unified memory fragmentation and prevents OutOfMemory errors in the persistent backend process.
---
136: 
137: ## 7. External AI Integration (MCP)
138: Nimbus implements a **Model Context Protocol (MCP)** server via the `FastMCP` framework. This allows external AI assistants (like Claude) to securely access and modify the user's project data.
139: 
140: ### Tools Provided:
141: | Tool | Purpose |
142: |:---|:---|
143: | `list_calendar_events` | Fetch tasks within a timeframe, sorted by due date. Excludes completed items. |
144: | `search_tasks` | Executes natural language semantic search against the vector database. |
145: | `create_calendar_task` | Create new issues with dynamic project selection support. |
146: | `schedule_task` | Update task deadlines. |
147: | `get_task_details` | Retrieve full issue metadata. |
148: 
149: ### Transport:
150: *   **Protocol:** SSE (Server-Sent Events).
151: *   **Endpoint:** `/mcp/sse` (Mounted within the main FastAPI application).
152: 
153: ### Security:
154: *   Currently uses environment-based user lookup (`NIMBUS_USER_EMAIL`) for MCP context.
155: *   Strictly filters data by `owner_id` to ensure isolation.
156: 
