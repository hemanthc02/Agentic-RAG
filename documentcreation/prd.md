# Product Requirements Document (PRD)
**Project:** VeritasRAG · **Phase:** 4 (step 4) · **Version:** 1.0 · **Date:** 2026-06-07
**Depends on:** `product-vision.md` v1.0

## 1. Overview & scope
A multi-tenant SaaS (with a fully local single-tenant mode) for verifiable, agentic question answering over user-uploaded scientific/legal PDF corpora. MVP targets single-tenant + the research pipeline; SaaS capabilities (auth, multi-tenant, metering) are H2 and specified here for forward-compatible design.

## 2. Personas & permissions (RBAC)
| Role | Capabilities |
|---|---|
| **Researcher (user)** | Upload PDFs, build/select corpora, ask questions, view per-claim verification, export, manage own runs |
| **Admin** | All user caps + manage org members, providers/keys, thresholds, quotas, view usage + audit logs |
| **Owner/Org admin** | All admin caps + billing, SSO config, data-residency policy, delete org data |
| **Service (machine)** | Programmatic API access via scoped tokens |

## 3. Functional requirements (MoSCoW)

### Core RAG (Must)
- FR-1 Upload PDFs (drag-drop, batch); validate type/size; never persist outside designated storage.
- FR-2 Ingest: parse (PyMuPDF), chunk (configurable size/overlap), embed (MiniLM/configurable), store vectors in pgvector with `{source,page,chunk_id}`.
- FR-3 Corpus management: create/list/delete corpora; re-index; show index stats.
- FR-4 Ask a question against a selected corpus; stream the answer.
- FR-5 Planner decomposes complex questions into 1–4 sub-questions.
- FR-6 Retriever: per-sub-question vector search + CRAG-style relevance grading + single re-query on weak retrieval.
- FR-7 Synthesizer: grounded answer with inline `[n]` citations; emit `(claim, cited_chunk_ids)`.
- FR-8 **Verifier (core novelty):** independent NLI entailment score per claim vs cited chunks; verdict at configurable threshold.
- FR-9 **Reject-and-revise loop:** on failed verdict and retries remaining, re-synthesize with targeted feedback; else finalize and flag.
- FR-10 **Supportedness + reliance:** report per-claim supportedness score and (H2) a counterfactual reliance flag.
- FR-11 Provenance UI: per-claim card with cited chunk (file+page), excerpt, colour-coded score, reject control.

### Backends & providers (Must)
- FR-12 Configurable LLM provider (Gemini / OpenRouter / NVIDIA NIM / Ollama-local) via unified interface; per-request or per-tenant selection.
- FR-13 Mode-specific privacy statement surfaced in UI; retriever + verifier always local.

### Evaluation (Should)
- FR-14 Run benchmark (baseline / multi-agent / +verifier) × (cloud/local); produce RAGAS + custom metrics + latency; export CSV/report.

### SaaS (Should/Could — H2)
- FR-15 Auth (JWT + OAuth), RBAC; FR-16 usage metering & quotas; FR-17 admin panel; FR-18 audit log; FR-19 billing hooks; FR-20 onboarding flow.

### Admin (Should)
- FR-21 Manage providers/keys, thresholds, chunking params, model choices (env + DB-backed config).

## 4. Non-functional requirements
| Category | Requirement |
|---|---|
| **Performance** | Cloud mode ≤ 30 s/question P50; local mode ≤ 90 s P50 (no-retry); ingest ≥ 20 pages/s on CPU. |
| **Scalability** | Stateless API horizontally scalable; async workers for ingest/eval; pgvector to ≥ 1M chunks/tenant (IVF/HNSW); provider rate-limit aware. |
| **Reliability** | Retry w/ backoff (1,2,4s ×3) on provider calls; graceful degradation if a provider is down; bounded verifier retries (2). |
| **Security** | JWT/OAuth, RBAC, input validation (Zod/Pydantic), rate limiting, secrets via env, encryption in transit; per-tenant isolation. |
| **Privacy** | Air-gapped profile with zero egress; precise per-mode data-flow; configurable chunk-text retention. |
| **Maintainability** | Clean architecture, SOLID, DDD, repository + service layers, DI, ≥ 80% test coverage, typed end-to-end. |
| **Observability** | Structured logs, metrics, health checks, audit logs; OpenTelemetry-ready. |
| **Accessibility** | WCAG 2.1 AA; keyboard nav; dark mode. |

## 5. User workflows (happy paths)
1. **Onboard → index → ask:** sign in → create corpus → upload PDFs → "Build index" (async, progress) → ask → watch streamed answer → expand per-claim verification → export.
2. **Sensitive mode:** select *Local (air-gapped)* → confirm privacy statement → ask → all on-device.
3. **Evaluate:** admin selects benchmark + pipelines + modes → run → view comparison table + significance → export.
4. **Admin config:** set provider + key + default model + thresholds + quotas → save (audited).

## 6. Acceptance criteria (MVP gate)
- End-to-end ask→verify→answer works in both cloud and local modes.
- Verifier rejects a known unfaithful claim (regression test) and the loop repairs or flags it.
- Benchmark run reproduces the research KPIs on the 20-question set with significance.
- ≥ 80% test coverage on backend core; API documented (OpenAPI); no secrets in repo.

## 7. Risks & dependencies
NLI domain mismatch (mitigate: calibration, §research-analysis §9); provider quota/latency variance; benchmark validity (blind + adversarial); scope creep between research artifact and SaaS platform (mitigate: H1/H2/H3 horizons).

*Changes logged in `changelog.md`.*
