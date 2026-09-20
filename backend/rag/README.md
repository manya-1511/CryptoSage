# CryptoSage Phase 7 -- RAG Explanation Layer

Evidence-grounded explanations for the upstream ML/risk/recommendation
pipeline's already-produced results. Runs entirely on CPU, using only
local/free models -- no paid APIs, no GPU requirement.

```
CryptoSage ML/Risk Engine
        |
Retrieval Query
        |
BGE-small (or TF-IDF fallback)
        |
ChromaDB  --  top RAG_CANDIDATE_K candidates
        |
Lightweight deterministic reranking
        |
top RAG_TOP_K evidence chunks
        |
Qwen2.5 3B (Ollama)  --  or deterministic template if unavailable
        |
Output validation  ->  Citation validation
        |
Structured explanation (ExplanationResult)
```

Three fallback layers exist and are never removed:

| Component            | Primary                     | Fallback                          |
|-----------------------|------------------------------|-------------------------------------|
| Embeddings             | `BAAI/bge-small-en-v1.5`     | TF-IDF (scikit-learn)               |
| Explanation generator  | Qwen2.5 3B via Ollama        | Deterministic template              |
| LLM output             | Passes validation             | Falls back to template if it doesn't|

## Windows / CPU setup

This is designed for a CPU-only machine such as a Dell Inspiron 15
(Intel i5, no NVIDIA GPU). No step here requires a GPU or a paid API
key.

1. **Install Ollama for Windows** from https://ollama.com and start it
   (it runs as a background service after install).

2. **Pull the local LLM:**

   ```bash
   ollama pull qwen2.5:3b
   ```

3. **Verify it downloaded:**

   ```bash
   ollama list
   ```

   You should see `qwen2.5:3b` in the list.

4. **Ollama must be running** before using LLM-generated explanations
   (`POST /explain/{firmware_id}`). If it isn't running, or the model
   isn't pulled, CryptoSage automatically falls back to the
   deterministic template explanation -- the endpoint never crashes or
   blocks waiting for Ollama.

5. **Install Python dependencies:**

   ```bash
   pip install -r rag/requirements.txt
   ```

   `sentence-transformers` (for real BGE embeddings) is optional. If it
   isn't installed, or the model can't be downloaded (no network to
   Hugging Face Hub), ingestion/retrieval automatically use the local
   TF-IDF fallback instead -- this is logged clearly and reported in
   `EmbeddingBackend.name`, never silently substituted.

6. **Ingest the knowledge base:**

   ```bash
   python -m rag.ingest
   ```

   (or call `rag.ingest.ingest_knowledge_base()` from your own startup
   code -- it's idempotent and safe to re-run after editing the
   knowledge base.)

## What each local model is for

```
Qwen2.5 3B (via Ollama) = primary local explanation model
TF-IDF                  = embedding fallback (when BGE can't load)
Template explanation    = LLM fallback (when Ollama can't be reached,
                           times out, or its output fails validation)
```

No paid API is used or recommended anywhere in this pipeline.

## Configuration

See `.env.example` for every setting. The two knobs most worth tuning
on constrained hardware:

- `RAG_CANDIDATE_K` / `RAG_TOP_K` -- retrieval depth before/after
  reranking. Lower `RAG_TOP_K` means a shorter prompt and faster Qwen
  generation, at the cost of less supporting evidence.
- `OLLAMA_TIMEOUT_SECONDS` -- raise this if generation is slow on your
  hardware; a timeout is treated identically to "Ollama unavailable"
  and falls back to the template, it never crashes the request.

## Running tests and evaluation

```bash
pip install -r rag/requirements.txt
python -m pytest tests/ -q

# Dataset-level evaluation against the ingested knowledge base:
python -m rag.eval_dataset
```

`rag/eval_dataset.py`'s `expert_scores`/answer text are illustrative
placeholders documented in the file itself -- replace them with real
human ratings and real Qwen-generated answers (once Ollama is running)
before reporting evaluation numbers anywhere.

## Files

| File | Purpose |
|---|---|
| `rag/embeddings.py` | BGE-small embeddings, TF-IDF fallback |
| `rag/ingest.py` | Knowledge-base discovery, section-aware chunking, ChromaDB ingestion |
| `rag/retriever.py` | Two-stage retrieval: ChromaDB candidates -> lightweight rerank |
| `rag/prompt.py` | Structured, upstream-decisions/features/evidence prompt for Qwen |
| `rag/validation.py` | Programmatic output/citation validation gating the fallback |
| `rag/citations.py` | Citation extraction, dedup, sentence-level citation checking |
| `rag/explain.py` | Orchestrates the full pipeline; `ExplanationResult` |
| `rag/evaluation.py` | Precision@K, Recall@K, groundedness, citation metrics |
| `rag/eval_dataset.py` | Dataset-level evaluation runner |
