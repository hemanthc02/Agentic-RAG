# Architecture & Per-Module Technical Specification

Companion to `reports/workflow_diagram.png`. Derived from `prompt.md` (the source
of truth). Describes the data flow and the technical contract of every module.
Where this conflicts with `prompt.md`, `prompt.md` wins.

---

## How the pieces fit (end-to-end flow)

The system has two phases.

**Phase 1 — Offline indexing (one-time, fully local, no network).**
PDFs in `data/pdfs/` are parsed by `ingestion.py` (PyMuPDF) into ~512-char chunks
with 64-char overlap, each tagged with `{source, page, chunk_id}`. `retrieval.py`
embeds those chunks with `all-MiniLM-L6-v2` (384-dim) and persists a FAISS index
plus a chunk store to `data/index/`.

**Phase 2 — Runtime Q&A (a LangGraph `StateGraph`).**
A question enters the **Planner**, which decomposes it into 1–4 atomic
sub-questions. The **Retriever** runs FAISS search per sub-question, grades chunk
relevance with the LLM, and re-queries once (CRAG-style) if the best grade falls
below `RETRIEVAL_RELEVANCE_THRESHOLD`. The **Synthesizer** writes a grounded
answer with inline `[1][2]` citations and emits a structured list of
`(claim_text, cited_chunk_ids)`. The **Verifier** — the novelty — scores each
claim with an NLI entailment model against its cited chunks; if any claim fails
`CITATION_FAITHFULNESS_THRESHOLD` and `retry_count < MAX_VERIFIER_RETRIES`, the
graph routes back to the Synthesizer with feedback naming the failed claim and
its evidence. Otherwise it returns the final answer with per-claim faithfulness
scores.

**Two cross-cutting contracts.** (1) Every LLM call goes through
`llm_backend.py` — agents never touch Groq or Ollama directly. (2) Retriever
(MiniLM + FAISS) and Verifier (DeBERTa-NLI) are **local in both modes**; only the
LLM call differs between `groq` and `ollama`.

---

## Module-by-module

### `config.py` — single source of tunables
Holds every path, model name, and threshold; no magic numbers live in agent code.
Key values: `CHUNK_SIZE=512`, `CHUNK_OVERLAP=64`, `TOP_K=5`,
`RETRIEVAL_RELEVANCE_THRESHOLD=0.5`, `CITATION_FAITHFULNESS_THRESHOLD=0.6`,
`MAX_VERIFIER_RETRIES=2`, retry backoff `(1, 2, 4)` s, model identifiers, and the
`LLM_MODE` switch. Loads `.env` for `GROQ_API_KEY` / `LLM_MODE`.

### `src/ingestion.py` — PDF loading + chunking *(Week 1)*
- **Input:** PDF files under `data/pdfs/`.
- **Library:** PyMuPDF (`fitz`).
- **Behaviour:** open each PDF, extract text per page, split into ~512-char
  chunks with 64-char overlap.
- **Output:** `list[Chunk]` where each `Chunk` (Pydantic v2) carries
  `text: str`, `source: str` (filename), `page: int`, `chunk_id: str`.
- **Local?** Yes, always. No network.

### `src/retrieval.py` — embedder + FAISS vector store *(Week 1)*
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`, 384-dim, CPU. Do not
  swap for a larger model (`prompt.md` §8).
- **Index:** FAISS-CPU — flat index for ≤ 5,000 chunks, IVF above that.
- **Persistence:** writes `data/index/faiss.index` + `data/index/chunks.pkl`.
- **API:** `build(chunks)` and `search(query: str, k: int = TOP_K) ->
  list[RetrievalResult]` where each result has the chunk + similarity score.
- **Local?** Yes, always.

### `src/llm_backend.py` — LLM abstraction *(Week 2, fleshed out Week 4)*
- **Contract:** a class exposing `generate(prompt, temperature, max_tokens) ->
  str` and a `name` attribute. **All** agent LLM calls route through this — never
  call providers directly (`prompt.md` §8).
- **`GroqBackend` (default):** Groq API, model `llama-3.3-70b-versatile`. Free
  tier; cloud HTTPS. Latency target ≤ 30 s/question.
- **`OllamaBackend` (local):** Phi-3-mini via `http://localhost:11434` (or
  `langchain-ollama`). Stub returning "not yet" until Week 4, then real. Latency
  target ≤ 90 s/question.
- **Resilience:** retry with backoff `(1, 2, 4)` s, max 3 attempts; specific
  exceptions, no bare `except`.

### `src/agents/planner.py` — query decomposition *(Week 2)*
- **Input:** the user question (`str`).
- **Output:** `PlannerOutput` (Pydantic) with `sub_questions: list[str]` (1–4
  atomic sub-questions).
- **LLM?** Yes, via `llm_backend`.

### `src/agents/retriever.py` — retrieval + CRAG grading *(Week 2)*
- **Input:** the sub-questions from the Planner.
- **Behaviour:** call `retrieval.search` per sub-question; grade each chunk's
  relevance with the LLM; if the best grade < `RETRIEVAL_RELEVANCE_THRESHOLD`,
  rewrite the query and re-query **once** (corpus-only — no web fallback,
  `prompt.md` §8).
- **Output:** the deduplicated, relevance-ordered set of chunks for synthesis.
- **LLM?** Yes (grading). **Search itself is local.**

### `src/agents/synthesizer.py` — grounded answer + citations *(Week 2, extended Week 3)*
- **Input:** question + retrieved chunks (+ optional `feedback` on revision
  passes, added Week 3).
- **Output:** answer text with inline `[1][2]` markers **and** a parsed
  `list[Claim]` of `(claim_text, cited_chunk_ids)`.
- **LLM?** Yes, via `llm_backend`.

### `src/agents/verifier.py` — NLI citation verifier ★ *(Week 3 — the novelty)*
- **Model:** `cross-encoder/nli-deberta-v3-base` (DeBERTa-v3-MNLI), loaded once at
  module import, CPU.
- **Behaviour:** for each `(claim_text, cited_chunk_ids)`, concatenate cited
  chunks as the **premise** and the claim as the **hypothesis**, run NLI, and take
  the **entailment probability** as the faithfulness score. Apply
  `CITATION_FAITHFULNESS_THRESHOLD` (0.6) for a per-claim verdict.
- **Output:** `VerifierReport` with `scores: list[float]`,
  `verdicts: list[bool]`, `failures: list[Claim]`.
- **LLM?** No — uses NLI only. **Local in both modes.** Kept strictly separate
  from the Synthesizer (`prompt.md` §8).

### `src/graph.py` — LangGraph orchestration *(Week 2, extended Week 3)*
- **Week 2:** `StateGraph` wiring Planner → Retriever → Synthesizer → END.
- **Week 3:** add the Verifier node after the Synthesizer, plus a conditional
  edge — if any verdict fails and `retry_count < MAX_VERIFIER_RETRIES`, loop back
  to the Synthesizer with feedback; else END.
- **State:** typed schema carrying question, sub-questions, chunks, claims,
  verifier report, retry_count.

### `src/baseline.py` — vanilla single-agent RAG *(Week 1)*
The comparison baseline: embed → retrieve top-5 → stuff into one prompt → LLM →
answer. Routes through `llm_backend`. CLI: `python -m src.baseline "..."`.

### `src/evaluation.py` — metrics *(Week 1, extended Week 3)*
- **RAGAS:** faithfulness, answer relevance, context precision, context recall.
- **Custom metric (ours):** mean NLI entailment over cited claims — distinct from
  RAGAS faithfulness.
- **Reporting:** paired t-test between baseline and full system (p < 0.05);
  latency per question per mode. CLI: `python -m src.evaluation --pipeline ...`.

### `app/streamlit_app.py` — demo UI *(Week 4)*
Sidebar: PDF uploader, "Build index" button, Groq/Ollama mode selector. Main:
question input, answer area, and an expandable per-claim panel showing each
claim, its cited chunks (filename + page), and the color-coded faithfulness score
(green/amber/red).

---

## What is local vs. networked (privacy, per `prompt.md` §6)

| Component | `groq` mode | `ollama` mode |
|---|---|---|
| PDFs / ingestion / chunking | local | local |
| Embeddings (MiniLM) + FAISS search | local | local |
| LLM (Planner / Retriever grading / Synthesizer) | **Groq cloud (HTTPS)** | local (Ollama) |
| Verifier (DeBERTa NLI) | local | local |

In `groq` mode the question and retrieved chunks (PDF excerpts) leave the device
over HTTPS — **not** suitable for air-gapped or strict data-residency workflows.
In `ollama` mode nothing leaves the device. Never describe the system as "fully
local" without naming the mode.

---

## Build order (gated by acceptance criteria — `prompt.md` §5)

Week 1: `ingestion.py` → `retrieval.py` → `baseline.py` → eval set → baseline
RAGAS numbers. Week 2: `llm_backend.py` → four agents → `graph.py`. Week 3:
`verifier.py` + retry edge + custom metric (beat baseline by ≥ 10% faithfulness).
Week 4: real `OllamaBackend` → Streamlit UI → technical report. Each module ships
with at least one pytest happy-path test before it is called done.
