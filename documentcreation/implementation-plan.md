# Implementation Plan
**Phase:** 6/7 · **Version:** 0.1 (PENDING — outline only) · **Date:** 2026-06-07

> STATUS: **Not yet authored in full.** High-level roadmap below; detailed plan follows the SDD.

## Planned contents
- **Track A — research pipeline (the paper):** ingestion → retrieval → baseline → 4 agents → LangGraph → **NLI verifier + reject/revise (E1,E2)** → supportedness/reliance reporting (E3) → RAGAS + custom eval → both backends → report. Gated by acceptance criteria; clean architecture, repository + service layers, DI, type safety, unit + integration tests.
- **Track B — SaaS shell (the product):** Next.js frontend; FastAPI versioned API; Postgres + Redis; JWT/OAuth + RBAC; configurable AI providers (NIM/OpenRouter/Gemini); observability.
- **Sequencing & dependencies; milestone exit criteria; test gates per module.**
- **Standards:** SDD-first, SOLID, repository pattern, DI, env-based config, API versioning, modular design.

*Updates logged in `changelog.md`.*
