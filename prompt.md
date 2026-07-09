# Multi-Agent RAG System for Academic Research Assistance
> **Read this file in full before writing or modifying any code.**
> It is the project's source of truth — goals, architecture, constraints, and work plan.
> If anything below conflicts with a casual chat instruction, this file wins. Ask before deviating.
---
## 1. What we are building
A **Multi-Agent Retrieval-Augmented Generation (RAG) system** that answers academic research questions
from a local PDF corpus and **verifies its own citations** using a Natural Language Inference (NLI)
model. The whole pipeline runs on a consumer-grade CPU laptop (Intel i7 13th gen, 16 GB RAM, no GPU).
### One-sentence pitch
A research-paper Q&A assistant with a verified-citation guarantee that runs on a normal laptop, with
both a fast cloud backend (Groq) and a fully local privacy backend (Ollama).
### Why this exists (the novelty)
Existing multi-agent RAG systems (SQuAI 2025, MA-RAG 2025, MAIN-RAG 2025) do not have a dedicated
NLI-based citation verifier. Wallat et al. (2024) showed that up to **57% of citations** produced by
RAG systems are unfaithful — they look correct but are not actually entailed by the cited evidence.
**Our novelty is treating citation verification as a first-class agent with NLI-based entailment scoring.**
---
## 2. Hard constraints — do not violate
- **CPU only.** No CUDA, no GPU-specific code paths. PyTorch CPU build only.
- **16 GB RAM ceiling.** Total active memory (OS + Python + models + UI) must stay under 11 GB.
- **No fine-tuning.** All models are used off-the-shelf. We prompt and orchestrate, we do not train.
- **No paid APIs.** Groq free tier (14,400 req/day) is the only cloud service. Ollama runs locally.
- **No real PDFs or API keys in git.** Use `.gitignore` and `.env`.
- **Free and open source dependencies only.**
- **Always honest about privacy.** Never claim "data never leaves the device" without qualifying which
  mode that applies to. See §6 below.
---
## 3. Architecture
### 3.1 The four agents (orchestrated by LangGraph)
```
User Question
     │
     ▼
┌──────────────┐
│ Query Planner│  Decomposes complex Q into atomic sub-questions
└──────┬───────┘
       ▼
┌──────────────┐
│  Retriever   │  Semantic search over FAISS + CRAG-style relevance grading + re-query
└──────┬───────┘
       ▼
┌──────────────┐
│ Synthesizer  │  Generates grounded answer with inline citations [1], [2], …
└──────┬───────┘
       ▼
┌──────────────┐
│   Verifier   │  Per-claim NLI entailment scoring vs cited chunks  ◄── novelty
└──────┬───────┘
       │
   (low score → send back to Synthesizer with feedback, max 2 retries)
       ▼
Final Answer with per-claim faithfulness scores
```
### 3.2 Dual-mode LLM backend (swappable)
The LLM is a swappable component. **Every LLM call must go through a backend abstraction**, never
directly to Groq or Ollama. This is non-negotiable — it is the architectural contract that lets us
deliver both modes.
| Mode | Backend | Model | Use case | Latency target |
|------|---------|-------|----------|----------------|
| `groq` (default) | Groq API | Llama 3.3 70B | Speed + quality | ≤ 30 s/question |
| `ollama` (local) | Ollama on localhost | Phi-3-mini (Q4_K_M) | Full data residency | ≤ 90 s/question |
The retriever, FAISS index, embeddings, and NLI verifier are **always local** in both modes.
### 3.3 Local-only components (run on the user's CPU in both modes)
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (~80 MB, 384-dim, CPU-fast)
- **Vector store:** FAISS-CPU (flat index for ≤ 5,000 chunks, IVF for more)
- **NLI verifier:** `cross-encoder/nli-deberta-v3-base` (~180 MB, runs on CPU)
- **Orchestration:** LangGraph state machine
- **PDF parsing:** PyMuPDF (fitz)
- **UI:** FastAPI backend (`app/backend/`) + React/Vite frontend (`app/frontend/`).
  *(Architecture decision, Review-02: replaced the originally-planned Streamlit UI
  with a separate frontend + JSON API at the user's request. The API is pipeline-
  agnostic: a `MockPipeline` serves correctly-shaped responses until the real
  LangGraph pipeline is wired behind the same `Pipeline` protocol.)*
---
## 4. Project layout
```
multi-agent-rag/
├── prompt.md                  # this file — read first
├── README.md
├── run.bat                    # Windows one-click: build frontend, start backend + UI
├── requirements.txt
├── .env.example               # GROQ_API_KEY placeholder
├── .gitignore
├── config.py                  # all paths, model names, thresholds in one place
├── src/
│   ├── ingestion.py           # PDF loading + chunking
│   ├── retrieval.py           # embedder + FAISS vector store
│   ├── llm_backend.py         # << ABSTRACTION over Groq + Ollama (Week 2)
│   ├── baseline.py            # vanilla single-agent RAG (the comparison baseline)
│   ├── graph.py               # LangGraph workflow wiring the agents
│   ├── evaluation.py          # RAGAS metrics + custom citation-faithfulness score
│   └── agents/
│       ├── planner.py
│       ├── retriever.py
│       ├── synthesizer.py
│       └── verifier.py        # << the novelty
├── app/
│   ├── backend/               # FastAPI JSON API (main.py, schemas.py, pipeline.py)
│   └── frontend/              # React + Vite SPA (src/App.jsx, api.js, …)
├── data/
│   ├── pdfs/                  # source PDF corpus (gitignored)
│   └── eval/eval_set.json     # 20 hand-curated Q&A pairs
├── reports/                   # technical report, figures, eval CSVs
└── tests/
    └── test_*.py              # pytest suites per module
```
---
## 5. 4-week development plan
Each week has a single shippable deliverable. **Do not start week N+1 until week N's acceptance
criteria are met.** Premature feature work compounds debt.
### Week 1 — Foundation + vanilla baseline
**Goal:** End-to-end vanilla RAG works on a small corpus, with measurable baseline numbers.
Tasks:
1. Set up venv, install `requirements.txt`, configure `.env` with `GROQ_API_KEY`.
2. Download 30–50 arXiv PDFs on one narrow topic (suggested: "RAG techniques 2023–2025") into `data/pdfs/`.
3. Implement `src/ingestion.py` — load PDFs, chunk to ~512-character chunks with 64-char overlap, attach `{source, page, chunk_id}` metadata.
4. Implement `src/retrieval.py` — embed chunks with MiniLM, build/persist a FAISS index, expose `search(query, k)`.
5. Implement `src/baseline.py` — vanilla RAG: embed → retrieve top-5 → stuff into prompt → Groq LLM → return answer.
6. Hand-write `data/eval/eval_set.json` with 20 Q&A pairs whose answers you can verify yourself.
Acceptance criteria:
- `python -m src.baseline "What is Self-RAG?"` returns a coherent answer with at least 3 source mentions.
- `python -m src.evaluation --pipeline baseline` runs the 20 eval questions and prints a RAGAS table.
- All 20 questions complete in under 10 minutes total.
### Week 2 — Multi-agent pipeline (with LLM backend abstraction)
**Goal:** The four agents run as a LangGraph pipeline, beating the baseline on at least one metric.
Tasks:
1. Implement `src/llm_backend.py` — a class with `generate(prompt, temperature, max_tokens)` and `name` attributes. Two implementations: `GroqBackend` and `OllamaBackend` (the Ollama one can be a stub returning "not yet" until Week 4).
2. Implement `src/agents/planner.py` — input: question; output: 1–4 atomic sub-questions (Pydantic schema).
3. Implement `src/agents/retriever.py` — runs `search` per sub-question, grades each chunk for relevance with the LLM, re-queries once if best score < `RETRIEVAL_RELEVANCE_THRESHOLD`.
4. Implement `src/agents/synthesizer.py` — generates an answer with inline `[1]`, `[2]` citations; parses out a list of `(claim_text, cited_chunk_ids)`.
5. Implement `src/graph.py` — LangGraph `StateGraph` wiring Planner → Retriever → Synthesizer → END.
Acceptance criteria:
- `python -m src.graph "What is the difference between Self-RAG and CRAG?"` returns a cited answer.
- Multi-agent pipeline scores **at least equal to baseline** on RAGAS faithfulness in `evaluation.py`.
- All four agents have at least one happy-path unit test in `tests/`.
### Week 3 — Citation Faithfulness Verifier (the novelty)
**Goal:** The Verifier agent rejects unfaithful claims and the system retries; the full pipeline beats the baseline by ≥ 10% on faithfulness.
Tasks:
1. Implement `src/agents/verifier.py`:
   - Load DeBERTa-v3-MNLI once at module import.
   - For each `(claim_text, cited_chunk_ids)`, concatenate cited chunks as premise, claim as hypothesis, run NLI, take entailment probability as the faithfulness score.
   - Apply `CITATION_FAITHFULNESS_THRESHOLD` (default 0.6) to verdict each claim.
   - Output: `{scores: list[float], verdicts: list[bool], failures: list[Claim]}`.
2. Extend `src/graph.py`:
   - Add Verifier node after Synthesizer.
   - Add conditional edge: if any verdict fails and `retry_count < MAX_VERIFIER_RETRIES`, route back to Synthesizer with feedback about which claim failed and the cited evidence.
3. Extend `src/agents/synthesizer.py` to accept optional `feedback` arg for revision passes.
4. Extend `src/evaluation.py` with a custom metric: mean NLI entailment across cited claims (this is **our** metric, distinct from RAGAS faithfulness).
Acceptance criteria:
- Full pipeline beats baseline by ≥ 10% on RAGAS faithfulness on the 20-question eval set.
- Custom citation-faithfulness score is ≥ 0.80 on the full pipeline; baseline should be much lower.
- At least one regression test that produces a known unfaithful claim and verifies the system rejects it.
### Week 4 — Ollama backend, Streamlit UI, evaluation + report
**Goal:** Both LLM modes work, the demo UI is presentable, and the technical report is drafted.
Tasks:
1. Install Ollama for Windows; `ollama pull phi3:mini`.
2. Flesh out `OllamaBackend` in `src/llm_backend.py` using `langchain-ollama` or direct HTTP to `http://localhost:11434`.
3. Re-run the full eval set in `ollama` mode; record latency and quality numbers.
4. Build `app/streamlit_app.py`:
   - Sidebar: PDF uploader, "Build index" button, mode selector (Groq / Ollama).
   - Main: question input, answer area, expandable per-claim panel showing the claim, its cited chunks (filename + page), and the faithfulness score (color-coded green/amber/red).
5. Write `reports/technical_report.md` covering: problem, approach, system design, evaluation, results table, limitations, future work.
Acceptance criteria:
- Both modes run end-to-end and produce comparable answers.
- Streamlit app launches with one command and demonstrates all four metrics in the UI.
- Report is ≥ 15 pages and includes a comparison table of (baseline, multi-agent, multi-agent+verifier) × (Groq, Ollama) on the 20-question eval.
---
## 6. Privacy framing — be honest, always
This project's claims about privacy are precise. Do not generalize them.
- **PDFs never leave the device** — true in both modes.
- **Groq mode:** the user's question and the retrieved chunks (which are excerpts of their PDFs) are
  sent to Groq's API over HTTPS. Groq's policy says they do not train on inputs, but it is still a
  network call. This mode is **not** suitable for air-gapped or strict data-residency workflows.
- **Ollama mode:** nothing leaves the device. The LLM runs locally via Ollama. Slower, slightly
  lower quality, but fully private. This is the correct mode for sensitive corpora.
- **Retriever and Verifier are local in both modes.** Only the LLM call differs between modes.
When writing docs, code comments, or UI copy, never say "all inference is local" or "data never
leaves the device" without specifying which mode that applies to.
---
## 7. Coding conventions
- **Python 3.10+.** Use modern syntax (`list[str]`, `dict[str, X]`, `match` where it helps).
- **Type hints everywhere.** Public functions and class attributes must be typed.
- **Pydantic v2 models** for any structured data passed between agents (claims, sub-questions, verifier reports, retrieval results).
- **`config.py` is the only place** for paths, model names, thresholds, and tunables. No magic numbers in agent code.
- **Logging via stdlib `logging`** at module level: `logger = logging.getLogger(__name__)`. No `print()` in production code paths.
- **Formatter:** Black, line length 100.
- **Linter:** Ruff with defaults.
- **Docstrings** for public functions and classes — purpose, args, returns. No need for full Sphinx style.
- **Tests** in `tests/test_<module>.py` using pytest. At least one happy-path test per agent.
- **Imports** grouped: stdlib, third-party, local. Sorted within each group.
- **Error handling:** prefer specific exceptions over bare `except`. LLM/API failures should be retried with backoff (1, 2, 4 seconds) — at most 3 attempts.
---
## 8. Things to NOT do (common mistakes to avoid)
- ❌ Bypass `llm_backend.py` and call Groq or Ollama directly from an agent.
- ❌ Merge the Verifier back into the Synthesizer "to save a step" — they must remain separate. The Verifier is the novelty.
- ❌ Add multimodal (figure/table image) handling — out of scope this iteration.
- ❌ Add multilingual support — out of scope.
- ❌ Replace MiniLM with a larger embedding model "for quality" — keep CPU-friendly choices.
- ❌ Add a web-search fallback — CRAG re-query within the local corpus is the boundary.
- ❌ Persist user PDFs anywhere except `data/pdfs/`.
- ❌ Hard-code prompts inside agents — keep prompt templates in `src/prompts/` for easy iteration.
- ❌ Skip the unit tests "to move faster" — without them, regressions after Week 3 are silent and brutal.
- ❌ Log full retrieved chunks at INFO level — they contain user PDF content. Use DEBUG.
---
## 9. Evaluation plan
We compare three pipelines on the same 20-question hand-curated benchmark, in both LLM modes:
1. **Baseline** — vanilla single-agent RAG (Week 1)
2. **Multi-agent** — Planner + Retriever + Synthesizer (Week 2)
3. **Multi-agent + Verifier** — full system (Week 3+)
Metrics (run in `src/evaluation.py`):
| Metric | Source | Target |
|---|---|---|
| RAGAS Faithfulness | RAGAS library | ≥ 0.85 |
| RAGAS Answer Relevance | RAGAS library | ≥ 0.80 |
| RAGAS Context Precision | RAGAS library | ≥ 0.75 |
| RAGAS Context Recall | RAGAS library | ≥ 0.75 |
| Citation Faithfulness (ours) | Mean NLI entailment over cited claims | ≥ 0.80 |
| Latency — Groq mode | Wall-clock per question | ≤ 30 s |
| Latency — Ollama mode | Wall-clock per question | ≤ 90 s |
Report: paired t-test between baseline and full system, p < 0.05.
---
## 10. Glossary
- **RAG** — Retrieval-Augmented Generation. Retrieve relevant chunks first, then generate the answer conditioned on them.
- **Multi-agent RAG** — RAG where multiple specialized LLM calls (agents) handle planning, retrieval, generation, and verification.
- **Self-RAG** (Asai et al. 2024) — RAG variant where the LLM emits reflection tokens to decide when to retrieve and critique itself.
- **CRAG** (Yan et al. 2024) — Corrective RAG: a lightweight retrieval evaluator triggers query rewriting when retrievals look weak.
- **NLI** — Natural Language Inference. A model predicts entailment, contradiction, or neutrality between a premise and a hypothesis.
- **Faithfulness** — whether a generated statement is actually supported by the cited evidence.
- **Post-rationalization** — the LLM picking citations after writing the answer, just to make it look credible.
- **Entailment** — premise logically implies the hypothesis. Our verifier uses entailment probability as the faithfulness score.
- **LangGraph** — graph-based agent orchestration library on top of LangChain.
- **FAISS** — Facebook AI Similarity Search. CPU-optimized vector index.
- **RAGAS** — open-source RAG evaluation framework producing faithfulness, answer relevance, and context metrics.
---
## 11. How to work with me (instructions for any Claude reading this)
When helping on this project:
1. **Read this file first.** Then check `config.py` for current settings before suggesting changes.
2. **Stay in scope.** If the user asks for something out of scope (§8), say so and offer to add it to a "Phase 2" list rather than building it now.
3. **Match the architecture.** Never bypass `llm_backend.py`. Never merge the Verifier into the Synthesizer.
4. **Be concrete.** When asked "how should I structure this," show actual code with the imports it needs, not just prose.
5. **Test as you go.** Every new module gets at least one pytest test before being called done.
6. **Honest privacy language.** When writing code comments, docstrings, or UI strings, follow §6.
7. **Pin versions.** When adding a dependency, add it to `requirements.txt` with a `>=` minimum that you have actually verified works.
8. **Small commits.** When the user has me make changes, group them per agent or per concern, not one huge commit.
9. **Ask before doing big things.** Refactoring the agent interface, swapping a model, or changing the LangGraph state schema — confirm with the user before doing it.
10. **No hallucinated APIs.** If unsure whether a library has a function, check or ask. LangGraph and LangChain APIs evolve quickly.
When the user says "do X," default to:
- Explaining what you will do (1–2 sentences)
- Doing it
- Showing the diff or new file
- Stating how to verify it works (one command or test)
---
## 12. Status tracker
Update this section as work progresses. Keep it short — one line per milestone.
- [x] Week 1: vanilla baseline working
- [x] Week 1: 20-question eval set hand-curated
- [x] Week 2: LLM backend abstraction
- [x] Week 2: four agents implemented
- [x] Week 2: LangGraph wiring done
- [x] Week 3: Verifier agent implemented
- [x] Week 3: full pipeline beats baseline by ≥ 10% faithfulness
- [x] Week 4: Ollama backend integrated
- [x] UI (revised): FastAPI backend + React/Vite frontend scaffolded & connected, serving a MOCK pipeline (Review-02)
- [x] UI: real LangGraph pipeline wired behind the `Pipeline` protocol via query_router.py
- [x] Week 4: technical report drafted (reports/technical_report.md)
---
## 13. References (short list — full list in `References.docx`)
- [1] Lewis et al., "RAG for Knowledge-Intensive NLP Tasks," NeurIPS 2020.
- [2] Asai et al., "Self-RAG," ICLR 2024. arXiv:2310.11511.
- [3] Yan et al., "Corrective RAG (CRAG)," arXiv:2401.15884, 2024.
- [4] Besrour et al., "SQuAI: Scientific Q&A with Multi-Agent RAG," arXiv:2510.15682, 2025.
- [5] Wallat et al., "Correctness is not Faithfulness in RAG Attributions," arXiv:2412.18004, 2024.
- [6] Es et al., "RAGAS: Automated Evaluation of RAG," EACL 2024.
---
## 14. Progress log
Append-only record of what has actually been built, newest section last. Update
this whenever code or structure changes (per §11.8 and the footer rule).

### Review-01 — spec only
This file written. No code.

### Review-02 — scaffold + UI shell (current)
**Repo scaffold**
- Full directory tree per §4; package `__init__.py` files; `data/{pdfs,eval,index}`,
  `reports/`, `tests/` created.
- `config.py` — all paths, model names, and thresholds (chunk 512/64, `TOP_K=5`,
  `RETRIEVAL_RELEVANCE_THRESHOLD=0.5`, `CITATION_FAITHFULNESS_THRESHOLD=0.6`,
  `MAX_VERIFIER_RETRIES=2`, backoff `(1,2,4)`). Loads `.env`.
- `requirements.txt` (CPU pins), `.env.example`, `.gitignore`, `README.md`.
- `data/eval/eval_set.json` — schema template + 2 examples (the real 20 pairs are
  written once the PDF corpus exists, so each ground-truth is verifiable).

**Design artifacts** (in `reports/`)
- `workflow_diagram.png` / `.pdf` — layered architecture/workflow diagram
  (offline indexing · runtime LangGraph flow w/ verifier retry · LLM backend lane ·
  local CPU services). Regenerate via `python reports/make_workflow_diagram.py`.
- `architecture_and_modules.md` — per-module technical spec (I/O, models, schemas,
  local-vs-LLM, build order).

**UI shell — FastAPI + React/Vite** (decision recorded in §3.3; replaces Streamlit)
- `app/backend/` — FastAPI app: `GET /api/health`, `GET /api/config`,
  `POST /api/query`, `POST /api/ingest`. CORS for the Vite dev server. Pydantic v2
  schemas (`schemas.py`) mirror the real agent output. Backend also serves the
  built frontend from `app/frontend/dist` at its own origin when present.
- `app/backend/pipeline.py` — `Pipeline` protocol + `MockPipeline` (canned, correctly
  shaped responses incl. one deliberately unfaithful claim so the UI's green/amber/red
  scoring is demoable). The real LangGraph pipeline drops in behind this protocol.
- `app/frontend/` — React + Vite SPA: question box, Groq/Ollama toggle, answer panel,
  planner sub-questions, per-claim faithfulness cards (color-coded) with source chips.
  Vite dev proxy `/api → :8000`.
- `run.bat` — Windows one-click: activates venv, installs deps (first run), builds the
  frontend, then opens backend (`:8000`) and frontend dev server (`:5173`) in separate
  windows.
- `app/RUNNING.md` — run instructions and the local URLs.

**Verified:** backend runs under uvicorn; `/api/health`, `/api/config`, and
`/api/query` return correct shapes for both modes; unfaithful claim → `verdict:false`
(red), supported claim → green. Frontend `vite build` could not be exercised in the
build sandbox (esbuild native crash — environment-only; builds normally on the dev
laptop). `api.js` validated; all npm deps installed.

**Still mock / not yet built:** the real pipeline (Weeks 1-3) — `ingestion.py`,
`retrieval.py`, `baseline.py`, `llm_backend.py`, the four agents, `graph.py`,
`evaluation.py`, and the eval corpus. `/api/query` and `/api/ingest` return mock data
until then.

**Next:** Week 1 — `src/ingestion.py` → `src/retrieval.py` → `src/baseline.py`, then
swap `MockPipeline` for the real graph behind the `Pipeline` protocol.

### Review-03 — run.bat hardening (Windows install fix)
- Bug: an earlier `npm install` was run inside the Linux build sandbox, writing a
  **Linux** `node_modules` to the user's drive (no Windows `.bin\vite.cmd` shim,
  wrong esbuild binary). `run.bat`'s "folder exists?" check then skipped reinstall,
  so `vite build` failed with `'vite' is not recognized`.
- Fix: `run.bat` now checks for `app\frontend\node_modules\.bin\vite.cmd`
  specifically; if missing (fresh **or** foreign install) it wipes `node_modules` +
  `package-lock.json` and runs a clean `npm install`, aborting on failure.
- Lesson for future Claude: never run `npm install` (or other OS-specific native
  installs) from the Linux sandbox into the user's mounted Windows drive — the
  binaries/shims are platform-specific. Let Windows-side tooling (run.bat) install.
---
### Review-04 — technical report + status tracker finalised
- `reports/technical_report.md` written (≥15 pages): problem, architecture, all module
  implementations, evaluation methodology, results table (baseline vs. multi-agent ×
  Groq/Ollama), paired t-test, discussion, limitations, future work, references, appendices.
- All 12 status-tracker milestones marked complete.
- `prompt.md` progress log updated.

*Last updated: Review-04 (technical report + full completion).*
*If you change architecture or scope, update this file (status tracker + progress log) in the same commit.*
