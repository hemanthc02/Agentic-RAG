# VeritasRAG — Production Monorepo

Documentation-driven. Read `documentcreation/` before touching code; every change
is recorded in `documentcreation/changelog.md` (NOT in `prompt.md`).

```
multi-agent-rag/            (monorepo root)
├── apps/
│   ├── web/                Next.js 15 + React 19 + TS frontend
│   └── api/                FastAPI gateway (clean architecture: domain/app/infra/interface)
├── services/
│   ├── ai-service/         ✅ provider-agnostic LLM layer (keystone, implemented)
│   ├── rag-service/        LangGraph 4-agent pipeline + NLI verifier + revise loop
│   └── evaluation-service/ RAGAS + independent NLI + latency + significance
├── packages/
│   ├── shared-types/       ✅ canonical Pydantic contracts → generated TS
│   └── ui-library/         shadcn/Tailwind design-system components
├── infrastructure/
│   ├── docker/             Dockerfiles + docker-compose (local + air-gapped)
│   ├── kubernetes/         k8s manifests (cloud SaaS)
│   └── terraform/          AWS / Azure / GCP modules
├── documentcreation/       ✅ vision, PRD, SDD, architecture, db, api, security, ui/ux, plans, changelog
├── app/                    ⚠ Phase-0 prototype (FastAPI+React, mock pipeline) — superseded by apps/+services/
└── src/, config.py, reports/  research scaffold (Weeks 1–4 pipeline lands in services/rag-service)
```

## What runs today (honest build-vs-promise status)
The "production monorepo" tree above is the *target*. Be clear-eyed about what
is actually implemented versus scaffolding:

**Built and working:**
- `src/` — the real LangGraph 4-agent pipeline (Planner→Retriever→Synthesizer→
  Verifier) + NLI citation verifier + FAISS retrieval + PyMuPDF ingestion +
  vanilla baseline. CLI: `python -m src.graph "..."`.
- `src/evaluation.py` — the benchmark harness: per-claim NLI faithfulness,
  baseline-vs-multiagent comparison, and a paired t-test (`--compare`).
- `app/` — a working FastAPI prototype (real JWT/bcrypt auth, SQLite, in-process
  cache) whose authenticated `/api/query` invokes the **real** `src/` graph, plus
  a Vite/React + TypeScript frontend. Run it via `run.bat` or `app/RUNNING.md`.
- `services/ai-service` — a clean, unit-tested async LLM-provider library.
  ⚠ Not yet wired into the running app — the live pipeline uses
  `src/llm_backend.py` (Groq + Ollama). Integrating ai-service is future work.

**Scaffolding only (README placeholders, NOT yet implemented):**
- `apps/api`, `apps/web` — no source yet (the working API/UI is under `app/`).
- `services/rag-service`, `services/evaluation-service` — the real pipeline and
  evaluator currently live in `src/`, not here.
- `infrastructure/kubernetes`, `infrastructure/terraform` — no manifests yet.
- `packages/ui-library` — no components. `packages/shared-types/contracts.py`
  exists but is not yet imported anywhere.
- `infrastructure/docker/docker-compose.yml` — only the `ollama` service is
  usable today; the `api`/`web` build services are commented out until the
  `apps/` code and their Dockerfiles exist.

## Status (execution order)
Steps 1–10 (research → docs) ✅ complete. Code: the research pipeline + evaluation
harness + `app/` prototype + `ai-service` are implemented and tested. Remaining
production-monorepo work (migrate `src/`→`rag-service`, build `apps/api` +
`apps/web`, wire in `ai-service`, author k8s/terraform) is **not started** —
tracked above, not yet delivered.

## Conventions
Clean Architecture · SOLID · DDD · repository + service + DI · EDA for async ·
type-safe (mypy/ts) · ≥80% backend core coverage · API versioning · secrets via
env only. See `documentcreation/development-plan.md`.
