# AI Architecture Strategy: Nimbus (Local AI)

## 1. Overview
The AI layer in Nimbus is designed to be **additive**, meaning the core system functions perfectly without it. Intelligence is applied asynchronously to enhance data using **local LLMs** via Ollama, ensuring privacy and zero cost.

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

## 4. AI Feature Implementation

### 4.1 Auto-Triage (Single Issue)
*   **Logic:** Analyzes `title` + `description`.
*   **Output:** Suggests `Priority`.

### 4.2 Project Planner (Batch)
*   **Logic:** Takes a multi-sentence "plan" and uses `gemma3` to perform entity extraction and task breakdown.
*   **Prompt:** System instructs the model to return a structured JSON array of actionable tasks.

### 4.3 AI Schedule (Time Management)
*   **Logic:** Analyzes all open tasks and distributes them across the **next 5 days**.
*   **Optimization:**
    *   Prioritizes `URGENT` items early.
    *   Limits workload to ~3-5 tasks per day to prevent burnout.
    *   Ensures deadlines are realistic and balanced.

### 4.4 Semantic Search (Vector)
*   **SQL:** Uses `pgvector` cosine distance (`<=>`) to rank results based on user query embeddings.

## 5. Controls & Performance
*   **Async:** All AI calls are made using `ollama.AsyncClient`.
*   **Debounce:** Local state updates are immediate; vector updates happen on save.
*   **Fallbacks:** If Ollama is offline, the system degrades gracefully to keyword-only search and manual triage.
