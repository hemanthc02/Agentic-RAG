# Deployment Plan
**Phase:** 7 · **Version:** 0.1 (PENDING — outline only) · **Date:** 2026-06-07

> STATUS: **Not yet authored.** Outline below.

## Planned contents
- **Deployment modes:** (1) local research mode (CPU laptop, Ollama, no cloud); (2) SaaS mode (containerised FastAPI + Next.js, Postgres, Redis behind a reverse proxy).
- **Containerisation & orchestration:** Docker images per service; compose for dev; k8s/managed-container for prod.
- **Config & secrets:** env-only (`DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, provider API keys); no secrets in git.
- **Privacy/residency:** air-gapped profile (Ollama, no egress); cloud profile data-flow statement.
- **CI/CD:** build, test gates, image scan, migrations.
- **Observability:** logs, metrics, traces; cost/latency dashboards.
- **Diagrams:** deployment diagram generated and linked here.

*Updates logged in `changelog.md`.*
