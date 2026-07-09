# Changelog
All notable changes to the project's design documents and implementation are recorded here.
Format: reverse-chronological. Versioning: semantic-ish `MAJOR.MINOR` per document set.
**Rule (per project instructions): every change is recorded here — NOT in `prompt.md`. Each phase updates its relevant document and adds an entry here.**

---

## [0.8.0] — 2026-06-14 — Product UX: two-model app, login→Experiment, enterprise theme, paper draft
Format: **Date · Change · Reason · Impact.**

- **2026-06-14 · Restricted the app to exactly TWO models.** Online: Groq `meta-llama/llama-4-scout-17b-16e-instruct`; offline: Ollama `phi3:mini`. Updated `config.py` (removed gemini/openrouter/nvidia vars + docstring), `llm_backend.py` (docstring/error), `system_router.py` `/config` (`available_providers` = groq+ollama, trimmed `provider_models` + `_PING_URLS`), `pipeline.py` `_backend_label`, root `.env.example` (now reflects the two models + `JWT_SECRET`, not the stale gemini default / unused Postgres), frontend `types.ProviderName`→`groq|ollama`, and `ExperimentPage` provider dropdown (2 options). The `services/ai-service` library keeps broader provider support for future work.
  - *Reason:* User requirement — Groq Llama 4 Scout (online) + Ollama Phi-3 mini (offline), nothing else.
  - *Impact:* `/config` and the UI now expose exactly two models; agents call Llama 4 Scout via Groq by default. Verified: config loads the new IDs; backend + frontend typecheck; 30 py tests pass.
- **2026-06-14 · Offline auto-detect.** Choosing "Ollama · Phi-3 mini (offline)" in `ExperimentPage` re-probes `/api/status`, auto-connects if the daemon is up, and otherwise shows actionable guidance (`ollama run phi3:mini` / `ollama pull phi3:mini`).
  - *Reason:* "runs only in local when user runs ollama and it automatically checks models and connects."
  - *Impact:* Local mode connects without manual config when Ollama is running.
- **2026-06-14 · Post-login routing → Experiment, Home + About retained.** `LoginPage`/`RegisterPage` navigate to `/experiment`; `App.PublicRoute` redirects authenticated users to `/experiment`. Navbar keeps Home / Experiment / About; Landing page remains the public entry.
  - *Reason:* "User login show Experimental page… keep Home and About page after login."
  - *Impact:* Sign-in lands on the workspace; Home/About still reachable.
- **2026-06-14 · Enterprise theme.** Re-mapped the Tailwind `brand` palette from consumer indigo to a professional teal scale; added a `navy` scale; replaced violet wordmark/hero gradients with teal→sky / navy washes (per-agent accent colors retained). Updated Landing/About copy to the two models.
  - *Reason:* "update a UI as better theme color / enterprise-grade application."
  - *Impact:* Consistent enterprise navy+teal look across all pages via the `brand` token. Production build succeeds.
- **2026-06-14 · Frontend hygiene + build fix.** Removed dead legacy frontend trio earlier; this pass removed duplicate `vite.config.js` (kept `.ts`) and orphaned `styles.css`, and **added the missing `src/vite-env.d.ts`** that was breaking `npm run build` (`tsc` could not type `import.meta.env`).
  - *Reason:* Duplicate/dead files + a pre-existing build blocker.
  - *Impact:* `npx tsc --noEmit` is clean and `npm run build` succeeds (2812 modules, dist emitted).
- **2026-06-14 · Authored `documentcreation/research-contributions-paper.md`** — a publication-support draft: abstract, prior-work limitations, the four systemic gaps, contributions C1–C3, architecture, an old→new improvement table, the reproducible evaluation protocol, and a **results template with `‹fill›` placeholders** (no fabricated numbers) plus threats-to-validity. Grounded in `research-gap-analysis.md` + the real implementation.
  - *Reason:* "make a document of what we build new from old research papers, how improvement we gave… they are going to publish."
  - *Impact:* A defensible, honest contributions/methods writeup. External Wallat figures (57% / 43%) are flagged for source re-verification (network access was unavailable); results cells must be filled from `python -m src.evaluation --compare`.
- **2026-06-14 · Verified all four agents.** Planner/Retriever/Synthesizer/Verifier import cleanly and pass their unit + regression tests (mocked LLM/NLI); graph wiring intact; model change propagates through `get_backend`. Full end-to-end execution requires the user's machine (langgraph/faiss/groq installed + a built index + GROQ_API_KEY, or a running Ollama).

## [0.7.0] — 2026-06-14 — High/Medium-gap remediation (research-core correctness + honesty)
Format: **Date · Change · Reason · Impact.** Follows v0.6.0; closes the OPEN High/Medium findings and the research-deliverable gap.

- **2026-06-14 · G1 — fixed the NLI verifier text-pair bug** (`src/agents/verifier.py`): premise + hypothesis are now passed as `{"text": premise, "text_pair": hypothesis}` instead of the concatenated `f"{premise} [SEP] {hypothesis}"` string.
  - *Reason:* A cross-encoder NLI model tokenised the joined string as one premise with an empty hypothesis → meaningless entailment scores, silently breaking the project's core "verified citation" novelty.
  - *Impact:* Entailment is now scored correctly per cited claim. Verified by `tests/test_verifier.py` (entailed→pass, contradicted→fail).
- **2026-06-14 · G3 / F-08 — removed faithfulness-metric inflation and fixed verifier routing** (`verifier.py`): uncited sentences are no longer scored `0.6`/auto-passed — they carry no score, are excluded from the mean, and never count as "verified". `overall_faithfulness` is the mean NLI entailment over **cited** claims only; a citation-free answer scores `0.0`. `should_revise` now stops when the retry budget is exhausted **without** flipping an unfaithful answer to `verified=True`. Factored the scorer into reusable `verify_answer(answer, chunks)`.
  - *Reason:* The old 0.6 mild-pass let a zero-citation answer report ~0.6 faithfulness; retry-exhausted answers were silently marked verified.
  - *Impact:* The headline metric can no longer be gamed; verification status is honest. Verified by `tests/test_verifier.py`.
- **2026-06-14 · F-07 — built the evaluation harness** (`src/evaluation.py`): runs the 20-question benchmark through baseline and/or multi-agent pipelines, scores them with the *same* `verify_answer`, and (`--compare`) runs a **paired t-test** on per-question faithfulness; optional best-effort RAGAS (`--ragas`); writes CSV + JSON to `reports/`. CLI: `python -m src.evaluation --compare --corpus default`.
  - *Reason:* The core research deliverable was missing — none of the Week-1/2/3 acceptance criteria (RAGAS, ≥10% improvement, paired t-test) could be measured.
  - *Impact:* Baseline-vs-multiagent improvement is now quantifiable. Pure-metric helpers verified by `tests/test_evaluation.py` (scipy p-value path included).
- **2026-06-14 · G4 / G5 — unified the corpus index path and added the documented graph CLI.** All readers/writers (retrieval CLI, agent retriever, FastAPI app) now go through `config.corpus_paths(corpus_id)` under `data/corpora/<id>/`, so a CLI-built index is visible to the pipeline. Added `src/graph.py` shim + a `__main__` CLI to `src/agents/graph.py` so the documented `python -m src.graph "..."` works.
  - *Reason:* The retrieval CLI wrote `data/index/` while the pipeline read `data/corpora/<id>/`; `python -m src.graph` did not exist.
  - *Impact:* Build-once/query-anywhere works; the Week-2 acceptance command runs.
- **2026-06-14 · F-06 / G7 — prompt-injection hardening + lazy graph compile.** Untrusted source/document text is wrapped in `<sources>`/`<context>` delimiters with an explicit "treat as data, not instructions" directive (`synthesizer.py`, `prompts/baseline.py`). The LangGraph pipeline now compiles lazily in `get_pipeline()` instead of at import time.
  - *Reason:* Raw PDF text flowed into prompts unbounded; importing `src.agents.graph` crashed without `langgraph`.
  - *Impact:* `import src.agents.graph` now succeeds without langgraph (verified); prompts are injection-resistant.
- **2026-06-14 · G6 — added agent + verifier regression tests** (`tests/test_verifier.py`, `tests/test_agents.py`, `tests/test_evaluation.py`): per-agent happy-path tests (planner/retriever/synthesizer), the verifier's reject-the-unfaithful-claim regression test, and the evaluation math. **30 tests pass, 1 skipped** (faiss-gated) locally.
  - *Reason:* Week-2/3 required per-agent + unfaithful-claim regression tests; none existed.
  - *Impact:* The novelty and retry loop now have a safety net.
- **2026-06-14 · F-11 / F-12 / doc-drift — downscoped docs to reality and fixed broken plumbing.** Rewrote `docker-compose.yml` (removed dangling `api.Dockerfile`/`web.Dockerfile` + unused Postgres; kept usable `ollama`); made the CI compose-config check a real gate (dropped `|| true`) and added the new modules + scipy to CI; corrected `app/RUNNING.md` (real `/api/query`, auth, real endpoints — not "mock-only"); deleted the dead legacy frontend trio (`App.jsx`, `api.js`, `main.jsx`) shadowed by the real `.tsx` app; added a "What runs today" honesty section to `MONOREPO.md` and refreshed the `README.md` status.
  - *Reason:* Docs claimed a production monorepo and a mock-only backend that contradicted the shipped code; compose referenced non-existent files.
  - *Impact:* Documentation now matches the build; `docker compose config` validates; no duplicate/misleading frontend source.
- **Still tracked (not in this pass):** F-09 contract unification (`supportedness`/`reliance_flag` vs live `claims` schema), F-10 request/cost budget + input bounds, F-13 ML weight provenance/licensing, F-14 API hardening (CORS/rate-limit), F-15 build provenance. Wiring `services/ai-service` into the live pipeline also remains future work.

## [0.7.1] — 2026-06-14 — Review-02 explanation / companion document
Format: **Date · Change · Reason · Impact.**

- **2026-06-14 · Authored `review-02/Project_Review_02_Explanation.docx`** — a ~4,050-word Word companion to the deck.
  - *Reason:* User needs a complete explanation of the Review-02 PPT content fused with the project content (the slides carry headings; this carries the reasoning).
  - *Impact:* Self-contained presenter's guide. Sections: how-to-use, project-in-brief, slide-by-slide walkthrough (each slide → On the slide / Explanation / In our project / How-to-present-and-Q&A callout), a 19-term plain-English glossary, 10 anticipated panel Q&A, and the honesty-framing notes. Embeds the same four figures from the deck. Validated (OOXML "All validations PASSED"); visual spot-check of text + figure pages clean.

## [0.7.0] — 2026-06-14 — Review-02 presentation (Phase 2: Data Engineering / EDA / Feature Engineering)
Format: **Date · Change · Reason · Impact.**

- **2026-06-14 · Built `review-02/Project_Review_02.pptx`** — a 20-slide deck covering the schedule's Review-02 scope: §3 Data Engineering & Dataset Overview (3.1–3.7), §4 Exploratory Data Analysis (4.1–4.5), §5 Feature Engineering (5.1–5.5), plus recap and a Status-Report-1/Review-03 closer.
  - *Reason:* User request — Review-02 deck per the AY 2025-26 mini-project schedule image (due 20 Jun 2026).
  - *Impact:* Presentation deliverable ready. Adapted honestly to a no-fine-tuning retrieval system: "train/val/test" reframed as index + calibration + held-out benchmark (3.7); "imbalanced data/SMOTE" reframed as eval-topic + NLI-calibration balance (5.5); "feature selection" reframed as top-k + CRAG (5.4). EDA charts use REAL numbers from running the actual chunker on a 21-doc sample (101 chunks, mean 1,802 chars, 99% on-target).
  - *Assets:* `review-02/assets/{fig_pipeline,fig_eda,fig_features,fig_embedding}.png` (matplotlib).
  - *QA:* rendered to images and inspected by a fresh-eyes subagent; one defect found (pipeline figure clipped at right edge) and fixed by regenerating the figure with correct bounds + true aspect ratio. Re-verified slide 7.

## [0.6.0] — 2026-06-14 — Critical-gap remediation (fixing the adversarial findings)
Format: **Date · Change · Reason · Impact.** Each item references its finding ID from `adversarial-gap-analysis.md`.

- **2026-06-14 · F-01 — fixed `src/ingestion.py` SyntaxError** (escaped the f-string quotes, removed the U+2026).
  - *Reason:* The module could not be parsed, blocking all of `src/` + tests.
  - *Impact:* `import src.ingestion` now succeeds; the whole research pipeline is importable again. Verified.
- **2026-06-14 · F-03 — restored `Chunk` to a validating Pydantic v2 model** (`page` `Field(ge=1)`), keeping the rich semantic-chunker fields; rewrote `tests/test_ingestion.py` against the real `chunk_text(text, source, page, …) -> (list[Chunk], str)` API.
  - *Reason:* The dataclass downgrade broke `retrieval.save/load` (`.model_dump()`) and every ingestion test.
  - *Impact:* FAISS chunk-store round-trip works; ingestion tests pass. Verified.
- **2026-06-14 · F-04 — reconciled the `VectorStore` callers** (`src/agents/retriever.py`, `app/backend/routers/documents_router.py`) to the real API (classmethod `load`, `search(k=)`, `RetrievalResult` objects); added a public `VectorStore.chunks` property for incremental rebuilds.
  - *Reason:* Callers used a non-existent constructor/method shape → the agent graph and live indexing crashed.
  - *Impact:* `retriever._search` and the router's index rebuild now run; verified with a fake-embedder integration test.
- **2026-06-14 · F-05 — JWT fail-fast** (`app/backend/auth.py`): no hard-coded default in production/staging; accepts `JWT_SECRET` (preferred) or legacy `JWT_PRIVATE_KEY`; dev falls back to a clearly-labeled insecure key with a warning.
  - *Reason:* A public default secret enabled token forgery on any non-dev deploy.
  - *Impact:* App refuses to start in prod without a configured secret. Verified (prod-no-secret raises; dev warns).
- **2026-06-14 · F-02 — quarantined the mock pipeline** (`app/backend/pipeline.py`): `MockPipeline` is now `DEMO_MODE`-gated and emits a loud import-time warning; documented that the real path is `/api/query` (`query_router → src.agents.graph.run`), which already calls the real graph.
  - *Reason:* The legacy demo served canned verdicts that could be mistaken for real verification.
  - *Impact:* The mock is unmistakable; the production router uses the real graph. (Full real-graph execution still needs `langgraph`/`transformers` installed — not run in the review sandbox.)
- **2026-06-14 · Theme-1 — added `.github/workflows/ci.yml` green-build gate** (import check + `compileall` + research & ai-service pytest + frontend typecheck/build + compose config).
  - *Reason:* The meta-root-cause: 3 of 5 Criticals were integration drift no build step caught.
  - *Impact:* This class of defect now fails CI before merge. Gate verified green locally: imports OK, compileall exit 0, **23 tests pass** (14 research + 9 ai-service).
- **Not yet addressed (tracked, next):** F-06 prompt-injection delimiters, F-07 `evaluation.py`, F-08 verifier routing self-defeat, F-09 contract unification, F-10 cost budget + input bounds, F-11–F-15. Reviewer-stance findings remain in `adversarial-gap-analysis.md`.

## [0.5.0] — 2026-06-14 — Adversarial gap analysis (independent review)
Format: **Date · Change · Reason · Impact.**

- **2026-06-14 · Ran the Product Gap Analysis skill (six-lens adversarial review) with an independent Evidence-Gatherer subagent; produced `documentcreation/adversarial-gap-analysis.md` (15 findings: 5 Critical / 5 High / 4 Medium / 1 Low).**
  - *Reason:* User invoked `/product-gap-analysis` for a hostile-by-design review of the current build.
  - *Impact:* Surfaced that the research pipeline is currently **non-functional** — `src/ingestion.py:195` has a hard `SyntaxError` (F-01) that makes all of `src/` + tests un-importable; model/API drift (F-03, F-04) breaks persistence, the agent graph, and live indexing; the headline NLI verifier is **not wired into the product** (F-02, the API serves a `MockPipeline`); JWT default secret enables forgery (F-05). Meta-root-cause (G9): **no green-build CI gate** — a single CI job would have caught 3 of 5 Criticals.
  - *Note:* Findings are diagnostic only (reviewer stance — no code changed this pass). Devil's-Advocate subagent not run (audience = engineering triage); styled Word deliverable + DA pass available on request for a Review-02 / committee / customer audience.

## [0.4.0] — 2026-06-07 — Phase 1 (Week 1): foundation + vanilla baseline (real code)
Format: **Date · Change · Reason · Impact.**

- **2026-06-07 · Implemented `src/ingestion.py`** (PyMuPDF load + 512/64 char chunking + Pydantic `Chunk` with `{source,page,chunk_id}`).
  - *Reason:* Phase 1 task 3 — turn PDFs into retrievable, traceable chunks.
  - *Impact:* Real corpus ingestion now works (verified end-to-end on a synthetic 2-page PDF: pages→chunks, metadata, ≤512-char chunks). 6 unit tests.
- **2026-06-07 · Implemented `src/retrieval.py`** (injectable MiniLM embedder, FAISS flat/IVF index, persist/load, cosine `search(query,k)`).
  - *Reason:* Phase 1 task 4 — semantic retrieval over the corpus.
  - *Impact:* Index build/persist/search functional; embedder is dependency-injected so it is unit-testable without a model download. 4 unit tests (build/search/order/roundtrip).
- **2026-06-07 · Implemented `src/llm_backend.py`** (`LLMBackend` ABC + `GroqBackend` + `OllamaBackend` + `get_backend()` factory + retry/backoff).
  - *Reason:* Honors prompt.md §8 — all LLM access via the abstraction; baseline needs an LLM. (Brings Week-2 task 1 forward, minimally.)
  - *Impact:* Baseline and future agents never call a provider SDK directly; mode switch via `config.LLM_MODE`.
- **2026-06-07 · Implemented `src/baseline.py` + `src/prompts/baseline.py`** (vanilla retrieve→prompt→generate RAG with CLI).
  - *Reason:* Phase 1 task 5 — the comparison baseline the multi-agent system must beat.
  - *Impact:* `python -m src.baseline "..."` works once PDFs + a provider key are present. 2 unit tests (prompt assembly, answer shape) using fakes.
- **2026-06-07 · Authored 20-question `data/eval/eval_set.json`.**
  - *Reason:* Phase 1 task 6 — benchmark for baseline vs multi-agent vs +verifier.
  - *Impact:* Ground-truths grounded in the RAG literature; verifiable once matching arXiv PDFs are added. (`evaluation.py` runner is Phase 1 task remaining.)
- **Verification:** 12/12 unit tests pass (ingestion+retrieval+baseline); ingestion exercised end-to-end through PyMuPDF.
- **Known follow-ups:** `src/evaluation.py` (RAGAS table runner) not yet built; real arXiv PDFs not downloaded (no network in build env); a leftover `data/pdfs/_synthetic_test.pdf` (test artifact) should be deleted on the dev machine.

## [0.3.0] — 2026-06-07 — Architecture & design gate (execution steps 3–10) + monorepo keystone
Format per change-management rule: **Date · Change · Reason · Impact.**

- **2026-06-07 · Added Product Vision, PRD, and v1.0 of SDD / Architecture / Database / API / Security / UI-UX / Development Plan; added `research-gap-analysis.md` (per-paper deep).**
  - *Reason:* Execution order steps 3–10 require documentation before code ("documentation drives development").
  - *Impact:* Implementation is now unblocked and traceable (requirement→design→test). `documentcreation/` is the single doc home; `prompt.md` is no longer updated.
- **2026-06-07 · Adopted working product name "VeritasRAG" and SaaS architecture (Next.js15/React19, FastAPI/Python3.12, Postgres+pgvector, Redis, provider abstraction).**
  - *Reason:* Principal-architect mandate to build a production-ready, scalable SaaS, provider-agnostic (NVIDIA NIM / OpenRouter / Gemini / Ollama).
  - *Impact:* Supersedes the Phase-0 prototype (`app/` FastAPI+React over a mock pipeline) and the Groq-only research config; those remain as Phase-0 reference. Stack changes are ADR-tracked in `architecture.md`.
- **2026-06-07 · Scaffolded production monorepo (`apps/{web,api}`, `services/{ai-service,rag-service,evaluation-service}`, `packages/{shared-types,ui-library}`, `infrastructure/{docker,kubernetes,terraform}`); added `MONOREPO.md`, root `.env.example`, `docker-compose.yml`.**
  - *Reason:* Shared contracts across web/api; atomic cross-cutting changes; deploy targets.
  - *Impact:* Clear home for each service; `app/` prototype explicitly marked superseded. Root `.env.example` now reflects the SaaS stack (was Groq-only) — research `config.py` migration to the provider abstraction is pending.
- **2026-06-07 · Implemented keystone `services/ai-service`: unified `LLMProvider` ABC + Gemini/OpenRouter/NVIDIA-NIM/Ollama adapters + config-driven factory + retry/backoff + typed value objects; 9 unit tests (all passing).**
  - *Reason:* Provider-agnostic AI layer is the architectural contract enabling the dual-mode privacy story and zero-lock-in.
  - *Impact:* Agents will depend only on the abstraction (DIP/OCP); adding a provider = one adapter + one registry entry. Verified: import OK, `pytest` 9 passed.
- **2026-06-07 · Added canonical API contracts in `packages/shared-types/contracts.py` (Pydantic).**
  - *Reason:* Single source of truth for web↔api DTOs (generate TS from these).
  - *Impact:* Prevents frontend/backend drift; `supportedness_score` + `reliance_flag` modelled per the research correction.

## [0.2.0] — 2026-06-07 — Phase 1 research analysis
### Added
- `research-analysis.md` v1.0 — full Phase-1 analysis: problem statement, landscape, per-paper strengths/weaknesses (10 works), limitations, gaps (G1–G5), positioning matrix, threats to validity, SaaS + publication framing.
- `gap-analysis.md` v1.0 — Phase-3 contribution proposal: enhancements E1–E9 in the required template; contribution summary; gap→enhancement→KPI mapping.
- `/documentcreation` folder created with the full required document set (research-analysis, gap-analysis, software-design-document, architecture, database-design, api-design, implementation-plan, deployment-plan, testing-plan, changelog).
- Document stubs (PENDING) created for SDD, architecture, database-design, api-design, implementation-plan, deployment-plan, testing-plan with planned outlines.
### Verified / corrected
- Primary-source verification of referenced papers (SQuAI, Wallat, MA-RAG, MAIN-RAG).
- **Correction:** `review-01/References.docx` mis-cites Wallat et al. authors — correct list is Wallat, Heuss, de Rijke, Anand. SQuAI and MAIN-RAG venue/author details reconciled (see research-analysis §12).
### Key finding
- Distinction surfaced and adopted: NLI entailment measures citation **supportedness** (≈ Wallat-correctness), not Wallat-**faithfulness** (genuine reliance). Verifier reframed accordingly; reliance probe (E3) proposed.

## [0.1.0] — Earlier (pre-Phase-1, implementation scaffold)
> Recorded for continuity. Prior to this changelog, scaffold/UI changes were tracked in `prompt.md §14`. Going forward, all changes are logged here.
### Added
- Repo scaffold, `config.py`, `requirements.txt`, env/gitignore.
- Architecture/workflow diagram + per-module spec (`reports/`).
- FastAPI backend + React/Vite frontend over a mock pipeline; `run.bat` launcher (Windows install hardening).

---

### Pending (next entries will cover)
- `software-design-document.md` v1.0 (Phase 2): functional/non-functional requirements, system architecture, UML.
- `architecture.md`, `database-design.md`, `api-design.md` v1.0 (Phase 2).
- `implementation-plan.md`, `deployment-plan.md`, `testing-plan.md` v1.0.
