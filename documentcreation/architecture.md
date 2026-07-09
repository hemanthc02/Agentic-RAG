# Architecture Design
**Project:** VeritasRAG · **Phase:** 6 (step 6) · **Version:** 1.0 · **Date:** 2026-06-07
**Depends on:** `prd.md`, `software-design-document.md`

## 1. Architectural style
Clean Architecture + Domain-Driven Design, per service. Layers (dependencies point inward):
```
Interface (FastAPI routers / Next.js)  →  Application (use cases / services)
   →  Domain (entities, value objects, ports)  ←  Infrastructure (repos, providers, adapters)
```
Cross-cutting: Dependency Injection (constructor injection via a container), Repository pattern, Service layer, Event-Driven Architecture for long-running/async work (ingest, eval) via a task queue + domain events.

## 2. System context (C4 L1)
```
[Researcher] ─▶ [Web (Next.js)] ─▶ [API Gateway (FastAPI)]
                                          │
        ┌─────────────────────────────────┼───────────────────────────┐
        ▼                                 ▼                             ▼
  [rag-service]                    [ai-service]                 [evaluation-service]
  plan/retrieve/synth/verify     LLM provider abstraction        RAGAS + NLI + latency
        │         │                    │   │   │                        │
        ▼         ▼                    ▼   ▼   ▼                        ▼
 [pgvector]  [Redis]          [Gemini][OpenRouter][NIM][Ollama]   [reports store]
   (Postgres + vectors)  (cache/queue/rate-limit)   (external/local)
```
Local stack (always on-device): PyMuPDF, MiniLM embedder, FAISS/pgvector search, DeBERTa-v3-MNLI verifier. Only the LLM call may be remote (cloud mode).

## 3. Components (C4 L2) & responsibilities
| Component | Tech | Responsibility |
|---|---|---|
| **apps/web** | Next.js 15, React 19, TS, Tailwind, shadcn/ui, TanStack Query, Zustand, RHF+Zod | UI, auth, streaming answers, per-claim verification UX, admin |
| **apps/api** | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2, Alembic | API gateway, auth/RBAC, orchestration entry, persistence, metering |
| **services/rag-service** | LangGraph, Python | The 4-agent state machine + verify/revise loop |
| **services/ai-service** | Python | **Unified LLMProvider interface** + Gemini/OpenRouter/NIM/Ollama adapters; retries/backoff; token accounting |
| **services/evaluation-service** | RAGAS, transformers (NLI) | Benchmark runner, metrics, significance tests, reports |
| **packages/shared-types** | TS + Pydantic (generated) | Single source of truth for DTOs/contracts across web↔api |
| **packages/ui-library** | React + Tailwind + shadcn | Reusable design-system components |
| **infrastructure** | Docker, k8s, Terraform | Build, deploy, multi-cloud |

## 4. The agentic pipeline (rag-service)
LangGraph `StateGraph`: `Planner → Retriever → Synthesizer → Verifier → (conditional) → END | Synthesizer`. State carries question, sub-questions, retrieved chunks, claims, verifier report, retry_count. The LLM-using nodes (Planner, Retriever-grading, Synthesizer) call **ai-service**; Retriever search + Verifier NLI are local. Conditional edge: any failed verdict and `retry_count < 2` → back to Synthesizer with targeted feedback.

## 5. AI layer — provider abstraction (keystone)
```
LLMProvider (Protocol / ABC)
 ├── generate(messages, *, temperature, max_tokens, stream) -> Completion | AsyncIterator
 ├── name, model, supports_streaming
 ├── GeminiProvider        (google-genai)
 ├── OpenRouterProvider    (OpenAI-compatible HTTP)
 ├── NvidiaNIMProvider     (OpenAI-compatible / NIM HTTP)
 └── OllamaProvider        (localhost:11434)
LLMProviderFactory.from_config(settings) -> LLMProvider   # switch by env
```
Rules: agents depend on the **interface**, never a concrete provider; all keys via env; uniform retry/backoff (1,2,4s ×3) and error taxonomy; token/latency accounting emitted as metrics. Adding a provider = one new adapter, zero agent changes (Open/Closed).

## 6. Data architecture
- **PostgreSQL** — relational source of truth (tenants, users, corpora, documents, runs, claims, audit).
- **pgvector** — chunk embeddings co-located with metadata; HNSW index for scale; FAISS retained for the local single-tenant profile.
- **Redis** — cache (config, hot queries), rate-limit counters, async job queue (ingest/eval), pub/sub for progress.
- **Object storage** (S3/AzBlob/GCS or local FS) — raw PDFs, generated reports.

## 7. Event-driven flows
- `DocumentUploaded` → ingest worker (parse→chunk→embed→index) → `CorpusIndexed`.
- `EvaluationRequested` → eval worker → `EvaluationCompleted`.
- Synchronous path: `POST /query` streams tokens; verification runs inline; long corpora ingest is async with progress over SSE/WebSocket.

## 8. Cross-cutting concerns
- **Config:** 12-factor, env-only; typed settings (Pydantic Settings).
- **Security:** see `security-design.md` (JWT/OAuth, RBAC, rate limit, input validation, secrets).
- **Observability:** structured JSON logs (no chunk text at INFO), metrics (latency, retries, tokens, verifier scores), health/readiness, audit logs; OpenTelemetry-ready.
- **Resilience:** provider failover, bounded retries, circuit-breaker on providers, idempotent ingest.

## 9. Deployment topology
- **Local/air-gapped:** docker-compose (web, api, rag, ai[ollama], evaluation, postgres+pgvector, redis); zero egress profile.
- **Cloud SaaS:** k8s — stateless web/api/rag/ai/eval deployments (HPA), managed Postgres(+pgvector) & Redis, object storage, ingress + WAF; Terraform modules per cloud (AWS/Azure/GCP).
- Diagrams (component + deployment + sequence + class + use-case) to be generated as PNG/PDF and linked here in the diagram pass.

## 10. ADRs (key decisions)
- **ADR-001 pgvector over standalone vector DB** — co-locate vectors with relational data for transactional integrity + simpler ops; FAISS kept for local mode.
- **ADR-002 Provider abstraction first** — avoid lock-in; required for the dual-mode privacy story.
- **ADR-003 LangGraph for orchestration** — explicit state + conditional edges fit the verify/revise loop better than linear chains.
- **ADR-004 Monorepo** — shared types/contracts across web/api; atomic cross-cutting changes.

*Changes logged in `changelog.md`.*
