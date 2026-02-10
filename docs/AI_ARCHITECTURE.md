# AI Architecture Strategy: Nimbus (Local AI)

## 1. Overview
The AI layer in Nimbus is designed to be **additive**, meaning the core system functions perfectly without it. Intelligence is applied asynchronously to enhance data using **local LLMs** via Ollama, ensuring privacy and zero cost. Long-running AI tasks are processed by a lightweight Redis-backed worker.

## 2. Models & Providers (Ollama)
*   **Provider:** Ollama (Local API at `http://localhost:11434`)
*   **Embeddings:** `nomic-embed-text`
    *   *Reason:* High performance, open weights, optimized for RAG.
    *   *Dimensions:* 768
*   **Inference (Chat/Reasoning):** `gemma3`
    *   *Reason:* Google's latest open model, highly capable at instruction following and project planning.

## 3. Data Schema (pgvector)
We use a dedicated table for embeddings to enable semantic search.

```sql
-- Embedding Table
CREATE TABLE issue_embeddings (
    issue_id UUID PRIMARY KEY REFERENCES issues(id) ON DELETE CASCADE,
    embedding vector(768), -- Matches nomic-embed-text dimensions
    content_hash VARCHAR(64),
    last_updated TIMESTAMP DEFAULT NOW()
);
```

Issue summaries are cached to avoid regenerating unchanged content.
```sql
CREATE TABLE issue_summaries (
    issue_id UUID PRIMARY KEY REFERENCES issues(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    next_steps TEXT NOT NULL, -- newline-delimited list
    content_hash VARCHAR(64) NOT NULL,
    last_updated TIMESTAMP DEFAULT NOW()
);
```

## 4. AI Feature Implementation

### 4.1 Auto-Triage (Single Issue)
*   **Logic:** Analyzes `title` + `description`.
*   **Output:** Suggests `Priority`.

### 4.2 Project Planner (Batch)
*   **Logic:** Takes a multi-sentence "plan" and uses `gemma3` to perform entity extraction and task breakdown.
*   **Prompt:** System instructs the model to return a structured JSON array of actionable tasks.

### 4.3 AI Schedule (Time Management)
*   **Logic:** Analyzes open tasks that are **unscheduled or past due** and distributes them across the **next 5 weekdays**.
*   **Optimization:**
    *   Prioritizes `URGENT` items early.
    *   Limits workload to ~3-5 tasks per day to prevent burnout.
    *   Ensures deadlines are realistic and balanced.

### 4.4 Semantic Search (Vector)
*   **SQL:** Uses `pgvector` cosine distance (`<=>`) to rank results based on user query embeddings.

### 4.5 Similar Issues (Duplicate Detection)
*   **Logic:** Embeds a draft title/description and returns nearest issues.
*   **Use Case:** Show likely duplicates during issue creation.

### 4.6 Issue Summaries
*   **Logic:** Generates a concise summary + next steps for a single issue.
*   **Storage:** Stored per issue with content hash to avoid redundant regeneration.

## 5. Controls & Performance
*   **Async:** All AI calls are made using `ollama.AsyncClient`.
*   **Debounce:** Local state updates are immediate; vector updates happen on save.
*   **Fallbacks:** If Ollama is offline, AI endpoints return errors and should be treated as unavailable (no keyword-only fallback yet).
*   **Background Jobs:** Embedding backfills run via the worker to avoid blocking the API.
