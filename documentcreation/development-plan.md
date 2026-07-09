# Development Plan
**Project:** VeritasRAG · **Phase:** 10 (step 10) · **Version:** 1.0 · **Date:** 2026-06-07
**Method:** Documentation-driven, clean architecture, test-as-you-go (≥ 80% backend core coverage).

## 1. Execution map (your 16-step order → status)
| Step | Deliverable | Status |
|---|---|---|
| 1 Research Review | research-analysis.md | ✅ done |
| 2 Gap Analysis | gap-analysis.md, research-gap-analysis.md | ✅ done |
| 3 Product Vision | product-vision.md | ✅ done |
| 4 PRD | prd.md | ✅ done |
| 5 SDD | software-design-document.md v1.0 | ✅ done |
| 6 Architecture + Security | architecture.md, security-design.md v1.0 | ✅ done |
| 7 Database Design | database-design.md v1.0 | ✅ done |
| 8 API Design | api-design.md v1.0 | ✅ done |
| 9 UI/UX Design | ui-ux-specification.md v1.0 | ✅ done |
| 10 Development Plan | this file | ✅ done |
| 11 Backend Dev | apps/api + domain/app/infra | ⏳ scaffold started (monorepo + LLM abstraction) |
| 12 AI Layer | services/ai-service (provider abstraction), rag-service | ⏳ keystone started |
| 13 Frontend Dev | apps/web (Next.js) | ⛔ next |
| 14 Testing | unit/integration/api/e2e | ⛔ alongside 11–13 |
| 15 Deployment | docker/k8s/terraform | ⛔ after MVP |
| 16 Final Docs + UML diagrams | diagrams, README set | ⛔ ongoing |

## 2. Build sequence (dependency-ordered milestones)
**M1 — Monorepo + contracts (this turn):** workspace layout; `packages/shared-types` (Pydantic↔TS); `services/ai-service` **LLMProvider abstraction + Gemini/OpenRouter/NIM/Ollama adapters + factory**; typed settings; CI skeleton.
**M2 — Backend core:** FastAPI app, clean-architecture layers, SQLAlchemy models + Alembic migrations (per `database-design.md`), repositories, auth/RBAC, health/metrics. Tests: domain unit + repo integration.
**M3 — RAG pipeline (real):** ingestion (PyMuPDF→chunk→embed→pgvector), retrieval + CRAG grading, synthesizer, **NLI verifier + reject/revise loop** (the contribution), LangGraph wiring. Replace the prototype MockPipeline behind the same port. Regression test: known-unfaithful-claim rejected.
**M4 — Evaluation service:** RAGAS + independent NLI + latency; blind/adversarial 20-Q benchmark; paired t-test; report export.
**M5 — Frontend:** Next.js app, ask console, verification panel, dashboard, corpora, settings/providers, admin; TanStack Query + Zustand; dark mode + a11y.
**M6 — Hardening + deploy:** observability, rate limiting, security headers; Docker/compose (local + air-gapped), k8s manifests, Terraform per cloud; coverage ≥ 80%.

## 3. Definition of Done (per module)
Documented (doc updated first) → typed → unit + integration tested → observable (logs/metrics) → secure (validated, authZ) → changelog entry with date/change/reason/impact.

## 4. Risk register (top 5)
1. **Verifier quality (NLI domain mismatch)** → calibrate threshold, report P/R vs human (M3/M4). 
2. **Scope split research↔SaaS** → horizons H1/H2/H3; MVP = H1 + minimal H2 auth. 
3. **Provider variance/limits** → abstraction + retries + circuit breaker (M1). 
4. **Latency under retries (local mode)** → cap retries, measure worst case (M3/M4). 
5. **Benchmark validity** → blind + adversarial, pre-registered (M4).

## 5. Standards checklist (enforced in CI)
Clean architecture · SOLID · DDD · repository + service + DI · EDA for async · type-safe (mypy/ts) · ≥80% coverage · API versioning · no secrets in repo · structured logging · OpenAPI generated.

*Changes logged in `changelog.md`.*
