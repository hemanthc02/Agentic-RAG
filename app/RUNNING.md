# Running the app (frontend + backend)

The app runs **on your machine** — there is no hosted/public URL. You start two
local processes and open the frontend in your browser.

| Process | URL | What it is |
|---|---|---|
| Frontend (React/Vite) | **http://localhost:5173** | The UI you open in the browser |
| Backend (FastAPI) | http://localhost:8000 | JSON API the frontend calls |
| API docs (Swagger) | http://localhost:8000/docs | Interactive API explorer |

The frontend's dev server proxies `/api/*` to the backend, so you only interact
with **http://localhost:5173**.

> Current state: the authenticated `POST /api/query` runs the **real** LangGraph
> pipeline (Planner→Retriever→Synthesizer→Verifier) from `src/agents/`, not a
> mock. A `MockPipeline` still exists in `app/backend/pipeline.py` for offline UI
> work, but the live query path does not use it. To use the API you must
> register/log in (JWT) and create a corpus, then upload PDFs — answers are only
> as good as the indexed corpus, so an empty corpus returns "no relevant
> information found".

## 1. Start the backend

From the **repo root** (`multi-agent-rag/`), with your venv active:

```bash
pip install -r requirements.txt          # first time only
uvicorn app.backend.main:app --reload --port 8000
```

Verify: open http://localhost:8000/docs, or:

```bash
curl http://localhost:8000/api/health
# {"status":"ok","version":"<APP_VERSION>"}
```

The backend refuses to start in production without a `JWT_SECRET` set (it only
falls back to a dev secret when `ENV`/`APP_ENV` is a dev value — see
`app/backend/auth.py`).

## 2. Start the frontend

In a **second terminal**:

```bash
cd app/frontend
npm install                              # first time only
npm run dev
```

Open **http://localhost:5173**. Register/log in, create a corpus, upload a few
arXiv PDFs, then ask a question (try "What is Self-RAG?" or "What problem does
CRAG address?") and pick Groq (cloud) or Ollama (local). Claims are color-coded
green / amber / red by their NLI faithfulness score.

## Endpoints (all `/api/*`; query/corpora/documents require a JWT)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + version |
| GET | `/api/config` | Thresholds, model names, UI color bands |
| GET | `/api/status` | Cloud-provider + Ollama reachability |
| POST | `/api/auth/register`, `/api/auth/login` | Get a JWT |
| GET/POST/DELETE | `/api/corpora` … | Manage corpora |
| POST | `/api/corpora/{id}/upload` | Upload PDFs (real ingestion + FAISS index) |
| POST | `/api/query` | `{question, corpus_id, mode, provider, top_k}` → answer + verified claims |
| GET | `/api/query/history` | Recent queries |

## Production build (optional)

```bash
cd app/frontend && npm run build         # outputs static files to dist/
```

Serve `dist/` behind any static host and point it at the backend via
`VITE_API_BASE` (see `app/frontend/.env.example`).
