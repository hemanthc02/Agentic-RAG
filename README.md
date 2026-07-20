# VeritasRAG — Retrieval-Augmented Generation with Verified Citations

A research-paper Q&A assistant with a **verified-citation guarantee**. You upload
your PDFs, ask questions, and it answers **only** from those documents — then an
independent verifier checks that every citation is actually supported by its
source, showing you a faithfulness score and per-claim green/red cards.

Runs on a normal laptop. Two modes: **online** (fast, cloud model) and **offline**
(fully on-device, private).

---

## Quick start (one file)

```
Double-click:  START.bat
```

- **First run** auto-creates the environment, installs everything, downloads the
  AI models, and starts the app (~10–20 min, needs internet once).
- **Every run after** just starts the app at **http://localhost:8000**.

For **online** mode, put your own Anthropic key in `.env`:
`ANTHROPIC_API_KEY=sk-ant-…` (get one at console.anthropic.com).
**Offline** mode needs [Ollama](https://ollama.com) + `ollama pull phi4-mini` and
no key. See `../documentation/` for full guides.

---

## Why this exists

Standard RAG can attach a citation to a sentence its cited source does not actually
support. Wallat et al. (2024) report up to **57%** of RAG citations are unfaithful.
VeritasRAG treats **citation verification as a first-class agent**: it measures each
citation's faithfulness with a Natural Language Inference (NLI) entailment model and
enforces it — and is honest when it cannot verify a claim.

## Architecture

Four agents orchestrated as a state graph, preceded by a guard that answers
small-talk / off-topic questions instantly instead of hallucinating:

```
Question → Guard → Planner → Retriever(CRAG) → Synthesizer → Verifier → Answer
                                                     ▲            │
                                                     └─ revise ◄───┘  (unsupported claim; offline max 1, online max 2)
```

The answer-writing model is the only swappable, potentially-remote component.
Everything else — embeddings, the FAISS index, and the NLI verifier — runs
**locally in both modes**.

## Two modes

| Mode | Writer model | Notes |
|------|--------------|-------|
| **Online** (default) | Anthropic Claude (`claude-sonnet-5`) | Fast, high quality; sends the question + retrieved excerpts over HTTPS |
| **Offline** | Ollama `phi4-mini` (on-device) | Fully private, nothing leaves the machine; slower (CPU); auto-optimised (fewer chunks/tokens, ≤1 revision) |

## Privacy (mode-specific — state the mode)

- **Your PDFs never leave the device** in either mode.
- **Online:** your question and the retrieved chunk excerpts go to the cloud model over HTTPS.
- **Offline:** nothing leaves the device.
- The **retriever and verifier are local in both modes.**

## Features

- **Ask** — verified RAG Q&A with a **"Retrieved from" sources list** (each `[n]`
  citation mapped to its PDF + page) and per-claim green/red verification cards.
- **PDF libraries** — create multiple projects; upload PDFs (files or a folder);
  **delete** individual PDFs (index rebuilds automatically).
- **Research guide** — a corpus-grounded mentor for gap analysis and methodology
  comparison, with an explicit **project selector**.
- **Viva** — dynamically generated exam questions from your papers + scored answers.
- **Papers** — search arXiv / Semantic Scholar and import open-access PDFs (online).
- **Agents** — a visual map of the pipeline: each agent's input, process, output,
  and the three layers it works across.
- **Settings** — shows the models in use; no API keys are entered in the app.

## Project layout

```
multi-agent-rag/
├── START.bat            # single launcher (setup on first run, then start)
├── config.py            # single source of truth: paths, model names, thresholds
├── requirements.txt     # exact pinned dependencies
├── .env / .env.example  # secrets & settings (JWT, ANTHROPIC_API_KEY, OLLAMA_MODEL)
├── bootstrap_env.py     # creates .env with a secure JWT secret on first setup
├── src/
│   ├── agents/          # planner, retriever, synthesizer, verifier, graph, viva, guide
│   ├── ingestion.py     # PDF → chunks
│   ├── retrieval.py     # embeddings + FAISS + shared-model caching
│   ├── llm_backend.py   # online (Claude) / offline (Ollama) abstraction
│   ├── evaluation.py    # faithfulness benchmark + paired t-test
│   └── paper_search/    # arXiv + Semantic Scholar
├── app/
│   ├── backend/         # FastAPI, 7 routers, JWT+bcrypt auth, SQLite, guardrails
│   └── frontend/        # React + Vite + Tailwind SPA (pre-built into dist/)
├── tests/               # 34 pytest tests
└── data/                # app.db, pdfs/, corpora/ (created at runtime)
```

## Manual run (alternative to START.bat)

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python bootstrap_env.py                 # writes .env with a secure JWT secret
# add ANTHROPIC_API_KEY to .env for online mode
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

Then open http://localhost:8000. Login is created via the sign-up page.

## Command-line tools (optional)

```bash
python -m src.graph "What is corrective RAG?" --corpus <corpus_id>   # run the pipeline
python -m src.evaluation --compare                                    # baseline vs multi-agent + t-test
python -m pytest tests -q                                             # run the 34 tests
```

## Deployment

VeritasRAG is a **single FastAPI service** that serves both the JSON API and the
pre-built React SPA on one port — so deploying it means deploying one Python web
app. There is **no Streamlit** and no separate web server; the frontend is
compiled to static files (`app/frontend/dist/`) that the backend serves directly.

**What must be true on the server**
- Python 3.10–3.13.
- The frontend built once (`cd app/frontend && npm install && npm run build`). The
  built `dist/` is already included in the distributed package, so the server does
  **not** need Node.js.
- Environment variables (never committed):
  - `APP_ENV=production`
  - `JWT_SECRET` — a random 256-bit secret (the app **refuses to start** in
    production with a placeholder secret).
  - `ANTHROPIC_API_KEY` — for online mode.
  - `OLLAMA_HOST` — only if offline mode is used (an Ollama daemon with
    `phi4-mini` must be reachable).
- Persistent storage for `data/` (SQLite database, uploaded PDFs, FAISS indexes).

**Run it (production-style)**
```bash
python -m uvicorn app.backend.main:app --host 0.0.0.0 --port 8000
```
Put a reverse proxy (nginx / Caddy) in front for TLS and to serve on 80/443.

**Honest scaling notes (address before multi-user production)**
- Runs as a **single process today**: the SQLite database, the response cache, and
  the per-corpus FAISS indexes are process-local. Horizontal scaling (multiple
  workers/replicas) would first need a shared database (e.g. PostgreSQL), a shared
  cache (e.g. Redis), shared index storage, and per-corpus write locks.
- A **Dockerfile for the app, cloud hosting, CI/CD to a cluster, and
  monitoring/experiment tracking are planned but NOT yet implemented** — they are
  future work, not current capabilities.
- Online mode needs outbound HTTPS to the model provider; offline mode keeps
  everything on the host.

## Constraints & honesty

CPU-only friendly; no model training (pre-trained models are composed, not
trained); the offline model is `phi4-mini` (3.8B) because full models don't fit in
~7 GB RAM. The published faithfulness figures (0.821 vs 0.643 baseline) come from an
earlier run and a re-run with the current verifier is recommended before citing
them. Deployment is a single local server; containerisation / cloud hosting are
future work. The knowledge-graph feature was removed as it was not reliable.
