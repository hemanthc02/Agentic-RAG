# Adversarial Gap Analysis — VeritasRAG / multi-agent-rag
**Methodology:** Product Gap Analysis (six-lens adversarial review) · **Version:** 1.0 · **Date:** 2026-06-14
**Reviewer stance:** hostile-by-design (auditor + attacker + 3 AM on-call + the competitor looking for FUD)
**Evidence base:** independent Evidence-Gatherer subagent pass over the on-disk code (file:line citations preserved). Devil's-Advocate subagent **not** run — see §9.

> Methodology note: the skill's `references/*.md` files were not staged on disk; this review applies the methodology defined in the skill body (six lenses, Risk × Confidence matrix, guardrails G1–G14, AI/LLM Blind-Spot Question Bank Q1–Q12). Quantitative claims are paired with the file:line or command that produced them (G8).

---

## 1. Scope & product profile

| Dimension | Value | Note |
|---|---|---|
| Product type | **AI/LLM + Hybrid** (web app + REST API + agentic RAG pipeline) | Heaviest lenses: Domain Depth, Functional, Code Quality, Governance, Security |
| User context | **B2B aspirational, single-user prototype today** | Pharma/legal/research targets per `prd.md` |
| Regulatory exposure | **Privacy-only today; sector-regulated aspirationally** | SOC 2 / HIPAA / GDPR named in docs but not in production → G12 framing applies |
| Data sensitivity | **Confidential / PII** | User PDFs may be unpublished research |
| Decision criticality | **Advisory** | Research assistant; human reads the cited answer |
| Build provenance | **Mixed: AI-codegen + hand-edited** | Drift between edits is the dominant defect class (see §7) |
| Maturity stage | **Prototype / early MVP** | Drives G10 — blocker tags are Pre-pilot / Pre-customer / 30d / Backlog, **never** "pre-launch" |
| Deployment platform | **None deployed** (docker-compose intent, no Dockerfiles) | Not on ACA/AKS/etc → full sub-lens 5I cloud-native audit not applicable; deployment gaps noted as Backlog |

**Effort key (G14):** estimates assume **one full-time senior engineer** at normal velocity. **S** = <1 day · **M** = 2–5 days · **L** = 1–2 weeks · **XL** = 3+ weeks.

---

## 2. Dashboard — at a glance

**15 findings** (after G9 root-cause consolidation of 21 raw observations).

| Severity | Count | IDs |
|---|---|---|
| 🔴 Critical | 5 | F-01, F-02, F-03, F-04, F-05 |
| 🟠 High | 5 | F-06, F-07, F-08, F-09, F-10 |
| 🟡 Medium | 4 | F-11, F-12, F-13, F-14 |
| 🟢 Low | 1 | F-15 |

| Lens | Findings |
|---|---|
| Code Quality & Engineering | F-01, F-03, F-04, F-11, F-12 |
| Functional Completeness | F-02, F-07, F-08, F-09 |
| Security (5A) | F-05, F-06, F-14 |
| Enterprise / Governance | F-10, F-13, F-15 |

**The headline (honest):** this is not a "security posture" story. **3 of the 5 Criticals (F-01, F-03, F-04) are integration-drift defects that a single green-build CI gate would have caught before they ever reached a reviewer** — the research pipeline currently does not import. The other two Criticals are that **the product's headline novelty (the NLI verifier) is not wired into the running product at all (F-02)**, and an **auth-forgery default (F-05)**. Fix the CI gate and you close or prevent the majority of the Critical column.

---

## 3. Executive summary & top 5

The codebase has grown well beyond the Phase-1 scaffold — there are now agent modules (`planner`, `retriever`, `synthesizer`, `verifier`, `graph`), a FastAPI backend with JWT auth + SQLite, and a React/TS frontend. The **ai-service provider abstraction is the most mature, internally consistent part of the repo (9/9 unit tests pass).** Everything downstream of `src/ingestion.py`, however, is currently **non-functional** because of uncoordinated edits that left modules calling APIs that no longer exist.

**Top 5 (by risk × severity × confidence):**

1. **F-01 🔴 — `src/ingestion.py:195` has a hard `SyntaxError`** (`…` U+2026 + unescaped nested quotes). The module cannot be parsed, so `retrieval`, `baseline`, every agent, the upload router, and all three test files that import it are dead on arrival. One-line fix, repo-wide blast radius.
2. **F-02 🔴 — the live product serves a hard-coded `MockPipeline`** (`app/backend/pipeline.py:230`); the NLI citation verifier that is the project's entire thesis never executes in the product surface, which emits canned verdicts (including a deliberately-fake 0.41 score).
3. **F-03 🔴 — model/API drift:** `Chunk` was downgraded Pydantic→dataclass and `chunk_text` rewritten, breaking `retrieval.save/load` (`.model_dump()` on a dataclass → `AttributeError`) and all ingestion tests.
4. **F-04 🔴 — `agents/retriever.py` + the upload router call a `VectorStore` API that doesn't exist** (wrong kwargs, `load` is a classmethod, results aren't tuples) → the agentic graph and live indexing both crash.
5. **F-05 🔴 (conditional) — JWT signs with a public default secret** when `JWT_PRIVATE_KEY` is unset (`app/backend/auth.py:16`) → token forgery on any non-dev deploy.

---

## 4. Critical findings

### F-01 — SyntaxError makes the entire research pipeline un-importable
- **Lens:** Code Quality · **Risk:** Certain × Major → 🔴 Critical · **Confidence:** High · **Blocker:** Pre-pilot
- **Observation (G8):** `src/ingestion.py:195`:
  `print(f"  [{c.chunk_id}] {c.source} p.{c.page} §{c.section[:30]}  "{c.text[:80]}…"")` — unescaped `"` inside the f-string and a literal `…` (U+2026). `PYTHONPATH=. python3 -c "import src.ingestion"` → `SyntaxError: invalid character '…' (U+2026)`. `pytest tests` → `3 errors in 1.36s (collection interrupted, 0 tests ran)`.
- **Impact:** The headline research deliverable (ingest → retrieve → baseline → agents) cannot be imported or tested. Everything in `src/` and the upload path is blocked behind this one line.
- **Recommendation:** Fix the line (`\"{c.text[:80]}…\"` or drop the ellipsis). **WHO:** any engineer. **EFFORT:** S. **TIMING:** Pre-pilot (now).
- **Verification:** `python -c "import src.ingestion"` exits 0; `pytest tests` collects.

### F-02 — Headline NLI verifier is not wired into the product; live API serves a mock
- **Lens:** Functional Completeness / Domain Depth · **Risk:** Certain × Major → 🔴 Critical · **Confidence:** High · **Blocker:** Pre-customer
- **Observation:** `app/backend/pipeline.py:230` hardwires `get_pipeline = MockPipeline()` (`is_mock=True`) returning canned Self-RAG/CRAG answers, including a deliberately-unfaithful 0.41 claim (`:185`). A real `verifier_node` exists (`src/agents/verifier.py:90`, loads `cross-encoder/nli-deberta-v3-base`) and `query_router.py:44` imports the real `src.agents.graph.run` — so **the API and the mock disagree about which pipeline runs**, and the real one is broken by F-01/F-04 regardless.
- **Impact:** The product demonstrates *fabricated* verification. The single differentiator vs SQuAI/Self-RAG (an independent, enforced citation check) is absent from anything a user or reviewer can actually exercise. For a publication, results would be unreproducible; for a demo, the verdicts are theater.
- **Recommendation:** Wire the real graph behind `query_router`, delete or clearly quarantine `MockPipeline` behind a `DEMO_MODE` flag, fix F-01/F-04, install `transformers`. **WHO:** AI/backend eng. **EFFORT:** M. **TIMING:** Pre-pilot for the research claim; Pre-customer for the product.
- **Verification:** A live `/api/query` call returns scores produced by the DeBERTa verifier, not from `pipeline.py`'s canned dict; integration test asserts `is_mock` absent.

### F-03 — Pydantic→dataclass model drift breaks persistence and all ingestion tests
- **Lens:** Code Quality · **Risk:** Certain × Major → 🔴 Critical · **Confidence:** High · **Blocker:** Pre-pilot
- **Observation (consolidated from 3 manifestations):**
  - `src/ingestion.py:32` `Chunk` is now a `@dataclass` (no validation).
  - `src/retrieval.py:108,120` call `c.model_dump()` and `Chunk(**d)` — Pydantic-only APIs → `AttributeError` on `save()`/`load()`.
  - `tests/test_ingestion.py:12,20,28` call `chunk_text(text, chunk_size=, overlap=)` expecting `list[str]`; the impl signature is `chunk_text(text, source, page, ..., *, target_chars=, overlap_chars=)` returning `tuple[list[Chunk], str]`; `:38,44` expect a `ValueError` a dataclass never raises.
- **Impact:** Index persistence crashes; the entire ingestion test file is invalid; the data contract for the most-depended-on type is ambiguous (dataclass vs Pydantic) across the codebase.
- **Recommendation:** Restore `Chunk` as a Pydantic v2 model with `page: int = Field(ge=1)`; keep the richer semantic-chunker fields; rewrite `test_ingestion.py` against the actual `chunk_text` signature. **WHO:** backend eng. **EFFORT:** M. **TIMING:** Pre-pilot.
- **Verification:** `retrieval` save/load round-trips; `pytest tests/test_ingestion.py` green.

### F-04 — Retriever agent + upload router call a non-existent VectorStore API
- **Lens:** Code Quality / Functional · **Risk:** Certain × Major → 🔴 Critical · **Confidence:** High · **Blocker:** Pre-pilot
- **Observation:** `src/agents/retriever.py:49,51,56,63` (and `app/backend/routers/documents_router.py:145`) call `VectorStore(embedder=, index_path=, chunk_store_path=)`, `store.load()` as an instance method, and `store.search(query, top_k=)`, then iterate `for c, score in results`. Actual `retrieval.py`: `__init__(self, embedder)` only (`:73`), `load` is a `@classmethod` (`:112`), `search(query, k=)` (`:125`) returns `list[RetrievalResult]` (`:130`), not tuples.
- **Impact:** The agentic graph (the multi-agent contribution) and the live PDF-indexing endpoint both raise `TypeError` on first call.
- **Recommendation:** Pick one `VectorStore` contract (recommend the real `retrieval.py` API) and reconcile both callers; add an integration test that runs the graph on a 1-PDF corpus. **WHO:** AI/backend eng. **EFFORT:** M. **TIMING:** Pre-pilot.
- **Verification:** `graph.run("…")` and `POST /corpora/{id}/documents` complete on a sample PDF.

### F-05 — JWT default signing secret enables token forgery
- **Lens:** Security (5A) · **Risk:** Possible × Severe → 🔴 Critical · **Confidence:** High · **Blocker:** Pre-customer · **CONDITIONAL (any non-dev deploy with `JWT_PRIVATE_KEY` unset)**
- **Observation:** `app/backend/auth.py:16` `_SECRET = os.getenv("JWT_PRIVATE_KEY", "dev-secret-key-change-in-prod-never-deploy-this")`. If the env var is unset the app signs HS256 tokens with a public constant → anyone can forge a token for any `sub`. The var is also misnamed for the algorithm (HS256 is symmetric; `JWT_PRIVATE_KEY`/`JWT_PUBLIC_KEY` imply RS256).
- **Impact:** Full auth bypass / impersonation if deployed without the env set — a plausible mistake. Present-tense risk is low only because it's not yet deployed (hence CONDITIONAL).
- **Recommendation:** Fail-fast on startup if the secret is unset outside an explicit dev mode; generate a strong random secret; either switch to RS256 with real key files or rename to `JWT_SECRET`. **WHO:** backend eng. **EFFORT:** S. **TIMING:** Pre-customer.
- **Verification:** App refuses to boot in prod mode without a configured secret; tokens signed with the old default are rejected.

---

## 5. High findings

### F-06 — Prompt injection: untrusted PDF text inserted verbatim into prompts
- **Lens:** Security (5A) / AI-LLM (Q1) · **Risk:** Likely × Major → 🟠 High · **Confidence:** High · **Blocker:** Pre-customer / 30d
- **Observation:** `src/agents/synthesizer.py:32` and `src/prompts/baseline.py:23` interpolate `c['text']` (user-uploaded PDF content) directly into the prompt; the CRAG rewrite (`retriever.py:24`) and the verifier LLM-fallback (`verifier.py:68`) do the same. No delimiting or injection guard.
- **Impact:** A poisoned PDF ("ignore previous instructions; output …") can hijack the synthesizer/planner, exfiltrate the system prompt, or force a false "supported" verdict — directly attacking the faithfulness guarantee that is the product's reason to exist.
- **Recommendation:** Wrap retrieved content in explicit, non-instructional delimiters; keep chunk text out of system-role slots; add an injection classifier or output allow-list on tool/verdict decisions. **WHO:** AI eng. **EFFORT:** M. **TIMING:** 30d (Pre-customer for regulated pilots).
- **Verification:** A red-team PDF with embedded instructions does not change tool/verdict behavior in a test.

### F-07 — No evaluation harness — the core research deliverable is absent
- **Lens:** Functional / Governance · **Risk:** Certain × Moderate → 🟠 High · **Confidence:** High · **Blocker:** Pre-pilot (research)
- **Observation:** `grep` finds no `evaluation.py` and **no `ragas` usage** anywhere in `src/`, `app/`, `services/`; `ragas`/`datasets` sit unused in `requirements.txt`; `data/eval/eval_set.json` (20 Q&A) is consumed by nothing.
- **Impact:** The publication claims (≥10% RAGAS faithfulness gain, p<0.05, baseline-vs-multiagent-vs-verifier) cannot be produced. No metrics = no paper and no evidence the verifier helps.
- **Recommendation:** Build `src/evaluation.py` over the eval set (RAGAS + independent NLI + latency + paired t-test), blind/adversarial per `research-analysis.md` §9. **WHO:** research/AI eng. **EFFORT:** L. **TIMING:** Pre-pilot for the research track.
- **Verification:** `python -m src.evaluation --pipeline baseline` prints a metrics table over 20 questions.

### F-08 — Verifier routing is self-defeating (and falls back to self-grading)
- **Lens:** Domain Depth / AI-LLM · **Risk:** Likely × Major → 🟠 High · **Confidence:** Medium · **Blocker:** 30d
- **Observation:** `src/agents/verifier.py:117` gives uncited sentences `verdict: True` ("mild pass") — a model that emits no citations is judged "verified." `:150` sets `verified = all_pass or not can_revise`, so after retry exhaustion the answer is marked verified regardless of faithfulness. When `transformers` is unavailable, `_llm_faithfulness_score` (`:63`) asks the LLM to rate itself — the exact self-judgement circularity the project claims to fix (the supportedness-vs-faithfulness issue flagged in `research-analysis.md` §8.4).
- **Impact:** The verifier can be trivially defeated (omit citations) and reports success on failure, hollowing out the novelty and any eval numbers derived from it.
- **Recommendation:** Treat uncited factual claims as failures, not passes; never flip `verified=True` on retry exhaustion (surface "unverified" instead); label the LLM fallback a degraded mode, excluded from headline metrics. **WHO:** AI eng. **EFFORT:** M. **TIMING:** 30d.
- **Verification:** Regression test: an uncited claim and a retry-exhausted answer both report `verified=False`.

### F-09 — Two conflicting "canonical" contracts; declared reliance-probe unimplemented
- **Lens:** Code Quality / Governance · **Risk:** Likely × Moderate → 🟠 High · **Confidence:** High · **Blocker:** 30d
- **Observation:** `packages/shared-types/contracts.py:46,71` use `supportedness_score`/`overall_supportedness` + `reliance_flag`; `app/backend/schemas.py:41,62` use `faithfulness_score`/`overall_faithfulness`, no reliance flag. Both are described as the canonical wire format. Frontend (`ChatMessage.tsx:21,95`) consumes `faithfulness_score` — matching the backend, **not** the contract. `reliance_flag` (the H2 counterfactual-reliance novelty) is declared but implemented nowhere.
- **Impact:** Guaranteed integration breakage when the "production" contract is adopted; a stated research novelty exists only on paper.
- **Recommendation:** Choose one vocabulary (recommend `supportedness` + a real `reliance_flag` per the prior analysis); generate TS from the one source; implement or delete the reliance probe. **WHO:** backend + AI eng. **EFFORT:** M. **TIMING:** 30d.
- **Verification:** One contract module; `grep` finds no competing field names; reliance_flag either has a code path or is removed.

### F-10 — No request/cost budget; shallow input validation
- **Lens:** Enterprise / AI-LLM (Q7, Q12) · **Risk:** Likely × Moderate → 🟠 High · **Confidence:** Medium · **Blocker:** 30d · **CONDITIONAL (per-tenant quotas: SaaS multi-tenant)**
- **Observation:** Planner fans out to 3 sub-questions (`planner.py:51`), each → CRAG rewrite + re-search + synth, plus up to `MAX_VERIFIER_RETRIES=2` re-synths (`graph.py`), with no global per-request token/call cap or per-user daily ceiling (`llm_backend.py:48` only retries). `question` has `min_length=3` but **no `max_length`** (`schemas.py:50`, `contracts.py:54`); `corpus_id` is an unvalidated `str`. (Upload bounds *are* present: `MAX_PDFS_PER_CORPUS=20`, `MAX_FILE_MB=50`.)
- **Impact:** A single injected/looping request can fan out into many expensive LLM calls (cost runaway); an unbounded `question` is a cost + DoS vector. Present-tense for input bounds; quotas are conditional on multi-tenant SaaS.
- **Recommendation:** Add a per-request LLM-call/token budget and circuit breaker; add `max_length` to free-text fields and UUID validation to IDs; add per-user quotas before multi-tenant. **WHO:** backend eng. **EFFORT:** M. **TIMING:** 30d.
- **Verification:** A request exceeding the call budget is halted with a clear error; Pydantic rejects a 1 MB `question`.

---

## 6. Medium & Low findings

### F-11 🟡 — docker-compose references nonexistent Dockerfiles + wrong frontend framework
Code Quality · Possible × Moderate → Medium · High · Backlog · **CONDITIONAL (on first deploy attempt).** `infrastructure/docker/docker-compose.yml:36,44` build `api.Dockerfile`/`web.Dockerfile` — neither exists (only the compose file is in the dir); `:46` sets `NEXT_PUBLIC_API_BASE` (Next.js) for a Vite/React app. `docker compose build` fails immediately. **Fix:** add the Dockerfiles or remove build refs; reconcile Next vs Vite. **EFFORT:** M. **Verify:** `docker compose build` succeeds.

### F-12 🟡 — Frontend duplicate JS/TS source pairs
Code Quality / Provenance · Possible × Moderate → Medium · Medium · 30d. `App.jsx`+`App.tsx`, `main.jsx`+`main.tsx`, `api.js`+`api/client.ts` coexist → dead code + wrong-bundle risk. **Fix:** delete the legacy `.jsx`/`.js` set. **EFFORT:** S. **Verify:** one entry per role; `tsc`/`vite build` clean.

### F-13 🟡 — ML weight provenance & licensing undocumented
Governance / AI-LLM (Q5) · Possible × Moderate → Medium · Medium · Pre-customer · **CONDITIONAL (commercial SaaS).** `config.py:44,46` pull `all-MiniLM-L6-v2` and `cross-encoder/nli-deberta-v3-base` from HuggingFace at runtime with no pinned revision/hash and no license note (DeBERTa-v3 training-data terms warrant a check for commercial use). **Fix:** pin model revisions/digests, document licenses, vendor weights for air-gapped mode. **EFFORT:** M. **Verify:** models loaded by pinned revision; license file present.

### F-14 🟡 — API hardening gaps (CORS, login rate-limit, auth-dep default)
Security (5A) · Possible × Moderate → Medium · Medium · Pre-customer · **CONDITIONAL (production).** `app/backend/main.py:45-52` `allow_credentials=True` with `allow_methods/headers=["*"]` (localhost-only now); no rate-limit/lockout on `/api/auth/login` (`auth_router.py:45`); `documents_router.py:72` auth dependency has `= None` default (None-user footgun). **Fix:** env-driven origin allowlist, login rate-limit/lockout, remove the None default. **EFFORT:** M. **Verify:** brute-force test throttled; CORS rejects unlisted origin.

### F-15 🟢 — Build provenance beyond SBOM absent (Q11)
Governance · Possible × Minor → Low · Medium · Backlog · **CONDITIONAL (team/SaaS).** No evidence of commit signing, branch protection, or SBOM generation. **Fix:** enable branch protection + required CI check + signed tags before multi-contributor work. **EFFORT:** S. **Verify:** protected `main`, signed release tags.

---

## 7. Cross-cutting themes (G9 root-cause consolidation)

**Theme 1 — Absence of a green-build CI gate is the meta-root-cause of the Critical column.** F-01 (syntax error), F-03 (model drift), F-04 (API drift), F-11 and F-12 (stale artifacts) are all *integration drift*: edits to one module silently broke its consumers, and nothing failed the build. A single CI job running `python -c "import …"` + `pytest` + `tsc --noEmit` + `docker compose config` would have blocked every one of them. **This is the highest-leverage fix in the report** — it both clears defects and prevents their recurrence. **EFFORT:** S–M.

**Theme 2 — "Mock vs real" duality across the product.** The mock pipeline (F-02), the LLM-fallback verifier (F-08), the unimplemented `reliance_flag` (F-09), and the two contract vocabularies (F-09) all reflect a product where the demo surface and the real engine have diverged. Pick the real path; quarantine demo behavior behind an explicit flag.

**Theme 3 — Research artifact vs SaaS platform are two half-built products in one repo.** The research track (src/ + agents + eval) and the SaaS track (app/backend + frontend + infra) each have gaps the other's docs assume are filled. The horizons in `product-vision.md` (H1/H2/H3) are the right framing; the code should respect them rather than half-building both.

---

## 8. Dependencies, supply chain & AI/LLM blind-spot coverage (Q1–Q12)

| Q | Topic | Status in this review |
|---|---|---|
| Q1 | Prompt injection | **F-06** (open, High) |
| Q2 | RAG render sanitization | **Safe today** — `ChatMessage.tsx` renders plain JSX, no `dangerouslySetInnerHTML`/markdown; add a regression test before adding markdown |
| Q3 | Replay / nonce | **N/A today** — no HMAC/signed-request/webhook paths exist yet; revisit when live-push is added |
| Q4 | Model-server attack surface | **Low today** — NLI runs in-process via `transformers`, not a separate server; revisit if a model server is split out |
| Q5 | ML supply-chain provenance + licensing | **F-13** (Medium) |
| Q6 | Manifest-as-attack-surface | **Low** — no executable manifest; `eval_set.json` is data only |
| Q7 | Cost-runaway / FinOps | **F-10** (High) |
| Q8 | Latency budget / SLO | Targets documented (Groq ≤30s, Ollama ≤90s) but **unverified**; no measurement under retries — see Artifacts §10 |
| Q9 | Data residency | Claimed for EU/pharma in docs, **unimplemented**; single data plane assumed — Artifacts §10 |
| Q10 | Right-to-erasure | DB has tenant/corpus tables; **deletion across vector store + backups unverified** — Artifacts §10 |
| Q11 | Provenance beyond SBOM | **F-15** (Low) |
| Q12 | API input-validation depth | **F-10** (High) |

Secrets handling and SQL are **clean** (verified): `.env` gitignored with dummy values; every `database.py` query uses `?` placeholders (no injection).

---

## 9. Compliance / standards impact (G12 framing)

The product is **not** in production and claims **no** active certification, so nothing here is an audit "failure" — these are gaps that **would block** the named frameworks **if pursued**:
- **SOC 2 (would block if pursued):** no CI/change-management evidence, no audit-log completeness proof, JWT default-secret (F-05), no access reviews.
- **GDPR / data-residency (would block if pursued):** right-to-erasure across stores unverified (Q10), residency unimplemented (Q9).
- **Pharma/legal sector use (would block if pursued):** prompt-injection exposure (F-06) and the mock/self-grading verifier (F-02/F-08) are incompatible with "demonstrably faithful citations."

---

## 10. Artifacts not provided / could not verify

- **Live end-to-end run:** `langgraph`, `transformers`, `httpx`, `sentence-transformers`, `groq` are not installed in the review env, so agent-graph execution, NLI scoring, and embedding were not exercised. (Pydantic, faiss, numpy, pymupdf, pytest, pydantic-settings present; ai-service tests 9/9.)
- **Frontend build:** `tsc`/`vite build` not run; duplicate-source resolution (F-12) is inferred.
- **Latency (Q8), residency (Q9), erasure (Q10):** no measurements/artifacts; would need a running stack + load test + a deletion test across Postgres/vector/backups.
- **Dockerfiles / k8s / terraform:** absent on disk — no container/IaC build verifiable.
- **Real API keys:** `.env` shows dummy placeholders only; not inspected further.

---

## 11. Remediation roadmap

*Effort assumes one full-time senior engineer (G14).*

**Pre-pilot (must fix before anyone runs the research pipeline):**
1. F-01 fix syntax error (S) · 2. Theme-1 add CI green-build gate (S–M) · 3. F-03 restore Pydantic `Chunk` + fix tests (M) · 4. F-04 reconcile VectorStore API (M) · 5. F-07 build `evaluation.py` (L).

**Pre-customer (before the first external/paying user):**
6. F-02 wire the real verifier; quarantine the mock (M) · 7. F-05 JWT fail-fast secret (S) · 8. F-06 prompt-injection guard (M) · 9. F-08 fix verifier routing (M) · 10. F-13 pin/license models (M) · 11. F-14 API hardening (M).

**30 days:**
12. F-09 unify contracts + implement/remove reliance probe (M) · 13. F-10 cost budget + input bounds (M) · 14. F-12 delete duplicate frontend sources (S).

**Backlog (conditional on deploy/scale):**
15. F-11 Dockerfiles + Next/Vite reconcile (M) · 16. F-15 commit signing + branch protection (S).

---

## 12. Independent-review note (methodology transparency)

- **Evidence-Gatherer subagent:** run 2026-06-14; produced 21 file:line-grounded observations consolidated here into 15 findings. Its severity labels were **not** inherited — every finding was re-graded under the Risk × Confidence matrix.
- **Devil's-Advocate subagent: NOT run.** Rationale: audience is the builder doing engineering triage, not a launch/board/regulator deliverable (the trigger condition for the mandatory DA pass). If you intend to use this report for a Review-02 submission, an academic committee, or a customer/security assurance conversation, say so and I will run the DA pass and (optionally) regenerate this as a styled Word deliverable per the v3.6 visual contract.
- **Risk distribution:** 33% Critical is slightly above the skill's 15–25% guidance; it is justified here because three Criticals are *objectively observed* non-functional defects (the pipeline does not import), not severity inflation. All Critical tags use Pre-pilot/Pre-customer blockers, coherent with the prototype maturity (G10).
