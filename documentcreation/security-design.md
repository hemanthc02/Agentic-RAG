# Security Design
**Project:** VeritasRAG · **Phase:** 6 (step 6, security) · **Version:** 1.0 · **Date:** 2026-06-07

## 1. Threat model (STRIDE, summarised)
- **Spoofing:** stolen tokens → short-lived JWT access (15 min) + rotating refresh; optional MFA/SSO (H3).
- **Tampering:** request integrity via HTTPS/TLS; signed JWTs (RS256); DB constraints + audit.
- **Repudiation:** immutable `audit_events` for security-relevant actions.
- **Information disclosure:** per-tenant isolation; least-privilege; no chunk text in logs at INFO; secrets never in DB/repo.
- **DoS:** rate limiting (per-token + per-tenant), request size caps, async backpressure, provider circuit breakers.
- **Elevation of privilege:** RBAC enforced server-side on every route; deny-by-default scopes.

## 2. Authentication
- JWT (RS256) access + refresh; refresh rotation + reuse detection. OAuth2 / OIDC providers (Google, GitHub, enterprise SSO in H3). Passwords: Argon2id. Service-to-service: scoped machine tokens.

## 3. Authorization (RBAC)
Roles `researcher < admin < owner` (+ `service`). Scopes mapped to routes; tenant-scoped resource checks (a user may only touch rows where `tenant_id` matches their token). Admin/owner routes require elevated scope; all checks server-side.

## 4. Secrets management
- All secrets via environment / secret manager (AWS Secrets Manager, Azure Key Vault, GCP Secret Manager, or `.env` locally). 
- DB stores only `secret_ref` (a key name), never key material. 
- `.env` git-ignored; `.env.example` documents required vars:
```
DATABASE_URL=  REDIS_URL=  JWT_PRIVATE_KEY=  JWT_PUBLIC_KEY=
NVIDIA_NIM_API_KEY=  OPENROUTER_API_KEY=  GEMINI_API_KEY=
OAUTH_GOOGLE_CLIENT_ID=  OAUTH_GOOGLE_CLIENT_SECRET=
```

## 5. Input validation & API hardening
Pydantic v2 (backend) + Zod (frontend) validate every input; strict output models prevent overexposure; file uploads validated by MIME + magic bytes + size cap; SSRF guard on any provider URL config; parameterised queries only (SQLAlchemy) — no string SQL; CORS allow-list per env; security headers (HSTS, CSP, X-Content-Type-Options) via middleware/edge.

## 6. Data protection & privacy
- TLS in transit; at-rest encryption (managed DB/object store). 
- Mode-specific data flow (the honest privacy contract): PDFs never leave the device; cloud mode transmits question + retrieved chunks to the chosen provider over HTTPS; local mode = zero egress; retriever + verifier always local. 
- Right-to-erasure: tenant/corpus hard-delete path, audited. 
- PII minimisation; configurable chunk-text retention for `local` tenants.

## 7. Rate limiting & abuse
Token-bucket in Redis per token and per tenant; stricter limits on `/queries` and ingest; `429 + Retry-After`; provider-side quota awareness to avoid cascading failures.

## 8. Observability for security
Structured audit log (actor, action, target, result); auth events; anomaly hooks (failed-login spikes); OpenTelemetry traces tagged with tenant (never with secret/PII).

## 9. Compliance posture (roadmap)
GDPR-aligned data handling now; SOC 2 controls mapped in H3 (access reviews, change mgmt via `changelog.md`, encryption, logging). Air-gapped distribution for residency-restricted customers.

## 10. Dependency & supply-chain security
Pinned deps; SCA scanning (e.g., `pip-audit`, `npm audit`) in CI; image scanning; SBOM generation; least-privilege container users; no `latest` tags in prod.

*Changes logged in `changelog.md`.*
