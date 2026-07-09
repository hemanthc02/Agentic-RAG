# Software Design Document (SDD)
**Project:** VeritasRAG · **Phase:** 5 (step 5) · **Version:** 1.0 · **Date:** 2026-06-07
**Depends on:** `prd.md` v1.0 · **Companions:** `architecture.md`, `database-design.md`, `api-design.md`, `security-design.md`

## 1. Purpose
Define how the PRD is realised in software: domain model, module decomposition, key interfaces, control flows, and UML. This document **precedes implementation** (documentation-driven development).

## 2. Domain model (DDD)
**Bounded contexts:** Identity & Access · Corpus & Ingestion · Querying (agentic) · Verification · Evaluation · Billing/Usage.

**Core aggregates / entities:**
- `Tenant` (org) — root for isolation.
- `User` — belongs to Tenant; has Role.
- `Corpus` — owns Documents; has index stats + embedding config.
- `Document` → `Chunk` (value-rich entity: text, source, page, chunk_id, embedding).
- `QueryRun` — a single ask; holds mode, provider, sub_questions, latency, retries, status.
- `Claim` (value object within run) — text, cited_chunk_ids, supportedness_score, reliance_flag, verdict.
- `EvaluationRun` — pipeline×mode metrics + significance.
- `AuditEvent` — actor, action, target, timestamp.

**Ports (interfaces) — Domain depends on these, Infrastructure implements:**
`LLMProvider`, `EmbeddingModel`, `VectorStore`, `NLIVerifier`, `DocumentParser`, `CorpusRepository`, `RunRepository`, `Clock`, `EventBus`.

## 3. Module decomposition (per service, clean architecture)
```
domain/        entities, value objects, ports, domain services (pure, no I/O)
application/   use cases (AskQuestion, IngestCorpus, RunEvaluation), DTOs
infrastructure/ repos (SQLAlchemy), providers (ai-service), parsers, vector store, event bus
interface/     FastAPI routers / CLI / workers
```

## 4. Key use cases (application services)
- **AskQuestion(query, corpus_id, mode, provider?) → AnswerDTO**: orchestrates the LangGraph pipeline; persists `QueryRun` + `Claim`s; streams tokens; emits metrics.
- **IngestCorpus(files, corpus_id, config)**: async; parse→chunk→embed→upsert vectors; emits progress + `CorpusIndexed`.
- **VerifyClaims(claims, evidence) → VerifierReport**: NLI entailment per claim; threshold verdicts; (H2) reliance probe.
- **RunEvaluation(benchmark, pipelines, modes) → EvaluationReport**: RAGAS + NLI + latency + paired t-test.

## 5. Critical control flow — ask → verify → revise (sequence)
```
User → web → api.POST /v1/queries → AskQuestion use case → rag-service graph:
  Planner.generate()            [ai-service → provider]
  Retriever.search()+grade()    [local vector store + ai-service grade]
  Synthesizer.generate()        [ai-service] → claims[]
  Verifier.score()              [local NLI]  → report
  if any verdict fail and retry<2: → Synthesizer.generate(feedback)   (loop)
  else: persist run+claims; stream final answer + per-claim scores
```

## 6. Interface contracts (selected)
```python
class LLMProvider(Protocol):
    name: str; model: str; supports_streaming: bool
    async def generate(self, messages: list[Message], *, temperature: float = 0.0,
                       max_tokens: int = 1024, stream: bool = False) -> Completion | AsyncIterator[str]: ...

class NLIVerifier(Protocol):
    def score(self, premise: str, hypothesis: str) -> float: ...   # entailment prob

class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk]) -> None: ...
    def search(self, embedding: list[float], k: int, corpus_id: UUID) -> list[ScoredChunk]: ...
```
DTOs are defined once in `packages/shared-types` (Pydantic → generated TS) to keep web/api in lockstep.

## 7. Non-functional design tactics
Performance: async I/O, streaming, connection pooling, vector index tuning, retry caps. Scalability: stateless services + HPA, async workers, per-tenant index partitioning. Reliability: backoff, circuit breaker, idempotent ingest, bounded retries. Security: see `security-design.md`. Testability: ports/adapters allow pure-domain unit tests + adapter integration tests.

## 8. UML deliverables (to be generated as PNG/PDF, then linked)
Use-case, class (domain aggregates + ports), sequence (ask/verify/revise above), component (services), deployment (local + cloud k8s). The diagram pass uses the project's diagram tooling; placeholders tracked in `changelog.md`.

## 9. Traceability (requirement → design → test)
FR-8/FR-9 (verifier + revise) → rag-service Verifier node + conditional edge → regression test "known unfaithful claim rejected". FR-12 (providers) → `LLMProvider` + factory → provider contract tests. FR-2 (ingest) → IngestCorpus use case → integration test on sample PDFs.

*Changes logged in `changelog.md`.*
