# API Design
**Project:** VeritasRAG · **Phase:** 8 (step 8) · **Version:** 1.0 · **Date:** 2026-06-07
**Style:** REST, versioned `/api/v1`, JSON, OpenAPI 3.1, async FastAPI

## 1. Conventions
- Base path `/api/v1`; additive changes only within a version; breaking → `/v2`.
- Auth: `Authorization: Bearer <JWT>`; scopes per role (RBAC). Machine clients use scoped service tokens.
- Errors: RFC 9457 `application/problem+json` (`type`, `title`, `status`, `detail`, `instance`).
- Pagination: cursor (`?cursor=&limit=`). Idempotency: `Idempotency-Key` header on POST ingest.
- Rate limits: per-token + per-tenant (Redis); `429` with `Retry-After`.
- Streaming: `POST /queries` supports SSE (`text/event-stream`) for token + per-claim events.

## 2. Resource map
| Method | Path | Scope | Purpose |
|---|---|---|---|
| POST | `/auth/register` | public | Create user/tenant |
| POST | `/auth/login` | public | JWT access+refresh |
| POST | `/auth/refresh` | public | Rotate access token |
| GET | `/auth/me` | user | Current user/roles |
| GET/POST | `/corpora` | user | List / create corpus |
| GET/DELETE | `/corpora/{id}` | user | Get / delete corpus |
| POST | `/corpora/{id}/documents` | user | Upload PDFs (multipart, async index) |
| GET | `/corpora/{id}/jobs/{job_id}` | user | Ingest job status/progress |
| POST | `/queries` | user | Ask a question (SSE stream) |
| GET | `/queries` `/queries/{id}` | user | History / run detail (+claims) |
| GET | `/health` `/ready` `/metrics` | public/internal | Liveness/readiness/Prometheus |
| GET/PUT | `/admin/providers` | admin | List/set provider configs (secret_ref only) |
| GET/PUT | `/admin/config` | admin | Thresholds, chunking, default model |
| GET | `/admin/usage` `/admin/audit` | admin | Metering + audit log |
| POST | `/evaluations` | admin | Run benchmark (async) |
| GET | `/evaluations/{id}` | admin | Metrics + significance + report |

## 3. Core schemas (DTOs — shared-types source of truth)
```jsonc
// POST /api/v1/queries  (request)
{ "question": "string(>=3)", "corpus_id": "uuid",
  "mode": "cloud|local", "provider": "gemini|openrouter|nvidia_nim|ollama?",
  "top_k": 5, "stream": true }

// QueryRun (response / SSE final event)
{ "id":"uuid","question":"...","answer":"... [1][2]",
  "sub_questions":["..."],
  "claims":[{ "claim_text":"...","cited_chunks":[{"chunk_id":"...","source":"a.pdf","page":3,"text":"..."}],
              "supportedness_score":0.91,"reliance_flag":false,"verdict":true }],
  "sources":[ ... ], "overall_supportedness":0.88,
  "mode":"cloud","provider":"gemini","model":"...","latency_ms":2400,"retries":0 }
```
SSE event types: `token` (answer delta), `claim` (verified claim), `done` (final QueryRun), `error` (problem+json).

## 4. AI provider selection
`mode` chooses local (Ollama) vs cloud; `provider` (optional) overrides the cloud provider. Effective provider resolved as: request → tenant `provider_configs` → global default (env). Keys come from env/secret-manager via `secret_ref`; **never** accepted over the API.

## 5. Versioning, deprecation, contract tests
OpenAPI published at `/api/v1/openapi.json`; client types generated into `packages/shared-types`. Provider adapters and endpoints covered by contract tests (mock + optional live). Deprecations announced via `Deprecation`/`Sunset` headers.

## 6. Security touchpoints
Input validation (Pydantic) on every body; output models prevent overexposure; authZ guards per scope; rate limiting + idempotency on writes; CORS allow-list per environment. Full detail in `security-design.md`.

*Changes logged in `changelog.md`.*
