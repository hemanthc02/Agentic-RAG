# Gap Analysis & Novel Contribution Proposal
**Project:** Multi-Agent RAG System for Academic Research Assistance
**Phase:** 3 — Research-Based Innovation
**Document version:** 1.0
**Date:** 2026-06-07
**Depends on:** `research-analysis.md` v1.0

---

## How to read this document

Each enhancement follows the required template:
**Existing approach → Limitation → Proposed improvement → Expected impact → Research contribution.**
Enhancements are ranked by *defensibility × publishability × product value*. E1–E3 are the core contribution; E4–E6 strengthen the product and the paper; E7–E9 are Phase-2 stretch items kept here for traceability.

Legend — **Status:** `CORE` (build now, Weeks 1–4) · `STRETCH` (Phase 2) · **Risk:** L/M/H.

---

## E1 — Independent NLI claim-entailment verifier  `CORE` · Risk L
- **Existing approach:** Self-RAG (Asai 2024) emits an `IsSupported` reflection token; SQuAI (Besrour 2025) displays supporting sentences for traceability; CRAG/MAIN-RAG grade *documents* for relevance.
- **Limitation:** Supportedness is either (a) judged by the generator itself — the very source of post-rationalisation — or (b) merely *displayed*, never *scored* or *enforced*; document-level filtering never checks the final claim→evidence link.
- **Proposed improvement:** A separate agent runs an off-the-shelf NLI model (DeBERTa-v3-MNLI) with each claim as hypothesis and its cited chunks as premise, taking the **entailment probability** as a per-claim supportedness score, thresholded (default 0.6) to a verdict.
- **Expected impact:** Catches the dominant failure class — citations that don't actually support their claim — with an *independent* judge, breaking Self-RAG's self-judgement circularity. Target: ≥ 80% of claims at entailment ≥ 0.6 vs ~43% baseline.
- **Research contribution:** First referenced agentic-RAG system to wire an *independent, model-based* claim-entailment gate into the pipeline (closes gap **G1**).

## E2 — Verifier-driven reject-and-revise control loop  `CORE` · Risk M
- **Existing approach:** Self-RAG can re-generate based on its own tokens; no multi-agent system uses verification to drive a *targeted* repair loop.
- **Limitation:** A supportedness signal that isn't wired into control is advisory only — unfaithful claims still reach the user.
- **Proposed improvement:** A LangGraph conditional edge: if any claim fails the threshold and `retry_count < MAX_VERIFIER_RETRIES (2)`, route back to the Synthesizer with structured feedback (the specific failed claim + its cited evidence) for targeted revision; otherwise finalize.
- **Expected impact:** Converts detection into correction; bounded retries keep latency predictable. Strictly dominates "cite and hope."
- **Research contribution:** A *closed verification loop* — the operational remedy Wallat's diagnosis implies but no referenced system builds (closes **G2**).

## E3 — Supportedness ≠ faithfulness: add a reliance probe  `CORE (lite) / STRETCH (full)` · Risk M
- **Existing approach:** Wallat et al. (2024) *distinguish* correctness (supportedness) from faithfulness (genuine reliance) but provide no runtime mechanism; everyone else conflates or ignores the distinction.
- **Limitation:** An NLI entailment score measures **supportedness**, not Wallat-**faithfulness**. A claim can be fully entailed yet post-rationalised (the model knew it independently and attached a citation afterward). Claiming NLI "verifies faithfulness" is technically wrong and the easiest reviewer takedown.
- **Proposed improvement:** (lite) Rename the metric **Citation Supportedness** and state the distinction explicitly. (full) Add a **counterfactual reliance probe**: re-generate each claim with its cited chunk *removed*; if the claim is essentially unchanged, flag it as *likely post-rationalised* even though entailed. Report supportedness **and** a reliance flag per claim.
- **Expected impact:** Honest, defensible claims; a *second* faithfulness signal no prior system reports; pre-empts the sharpest objection.
- **Research contribution:** Operationalises the Wallat correctness/faithfulness split inside a working system — the single most **publishable** element (closes **G3**).

## E4 — Honest, mode-specific dual backend (Groq / Ollama)  `CORE` · Risk L
- **Existing approach:** SQuAI offers a selectable backend; cloud systems (Scopus AI) are closed/cloud-only.
- **Limitation:** "Selectable backend" is presented as a convenience, with no precise data-flow privacy statement; no air-gapped guarantee.
- **Proposed improvement:** A single backend abstraction; a precise, per-mode data-flow statement (PDFs never leave the device in either mode; in Groq mode the question + retrieved chunks transit HTTPS; in Ollama mode nothing leaves; retriever + verifier always local). Surfaced in UI and docs.
- **Expected impact:** A defensible compliance story for regulated buyers; a clean speed/privacy trade-off quantified on the same benchmark.
- **Research contribution:** A reproducible, *honestly bounded* privacy posture for agentic RAG (closes **G4**).

## E5 — CPU-only, sub-11 GB, fine-tune-free reference implementation  `CORE` · Risk L
- **Existing approach:** SQuAI/MA-RAG assume cloud-scale corpora and GPU inference.
- **Limitation:** Inaccessible to students, small labs, and air-gapped sites; hard to reproduce.
- **Proposed improvement:** Pinned free/open-source stack; MiniLM embeddings, FAISS-CPU, quantised Phi-3-mini, DeBERTa-v3-MNLI — total active memory ~10–11 GB; no fine-tuning.
- **Expected impact:** Anyone can reproduce results on a 16 GB laptop with no cloud bill.
- **Research contribution:** Reproducibility-as-contribution for the long tail (closes **G5**).

## E6 — Calibrated, per-claim faithfulness UI (XAI-by-design)  `CORE` · Risk L
- **Existing approach:** Citations shown as `[1][2]`; SQuAI shows supporting sentences.
- **Limitation:** No calibrated confidence; users can't see *where* the system is uncertain or act on it.
- **Proposed improvement:** Per-claim cards with colour-coded supportedness (green/amber/red), source chip (file+page), the cited text, and a reliance flag; user can reject a claim.
- **Expected impact:** Verification becomes explainability; trust is earned visibly. (A working shell of this UI already exists in `app/frontend`.)
- **Research contribution:** Turns a metric into an interaction pattern; supports a small user-trust study.

## E7 — Calibrated, domain-adapted verification threshold  `STRETCH` · Risk M
- **Existing approach:** Fixed/implicit thresholds.
- **Limitation:** General-domain MNLI miscalibrated on dense scientific claims; a single 0.6 cutoff is arbitrary.
- **Proposed improvement:** Calibrate the threshold on a held-out labelled set; report verifier precision/recall vs human labels; consider per-sentence premise segmentation.
- **Expected impact:** Fewer false rejects/accepts; credible verifier-quality numbers.
- **Research contribution:** Verifier *evaluation*, not just verifier *use* — strengthens the paper.

## E8 — Complexity-adaptive planning (Adaptive-RAG routing)  `STRETCH` · Risk M
- **Existing approach:** Adaptive-RAG (Jeong 2024) routes by question complexity; the project's Planner always decomposes.
- **Limitation:** Decomposing simple questions wastes latency/tokens (worse in Ollama mode).
- **Proposed improvement:** Route no-retrieval / single-step / multi-step before planning.
- **Expected impact:** Lower median latency; better Ollama-mode budgets.
- **Research contribution:** Cost-adaptive agentic RAG under a CPU budget.

## E9 — SaaS hardening: multi-tenant, persistence, observability  `STRETCH` · Risk H
- **Existing approach:** Research prototypes are single-user, stateless.
- **Limitation:** Not deployable as a commercial product.
- **Proposed improvement:** Postgres (corpora, runs, audit logs), Redis (cache/queues), JWT/OAuth + RBAC, API versioning, eval-as-a-service, the Next.js SaaS shell.
- **Expected impact:** Path from prototype to product.
- **Research contribution:** N/A (engineering); enables the startup/product track.

---

## Contribution summary (what we will actually claim)

> **Primary claim (defensible):** We introduce an *independent NLI claim-entailment verifier* with a *bounded reject-and-revise loop* in a CPU-only, dual-mode agentic RAG pipeline, and we *distinguish citation supportedness from faithfulness*, reporting both. No referenced system (RAG, Self-RAG, CRAG, SQuAI, MA-RAG, MAIN-RAG) does this.

> **What we will NOT claim:** that multi-agent decomposition, inline citations, or swappable backends are novel (SQuAI has them); or that NLI alone "verifies faithfulness" in Wallat's sense (it verifies supportedness; reliance is probed separately).

## Mapping: gaps → enhancements → KPIs

| Gap | Enhancement(s) | KPI evidence |
|---|---|---|
| G1 no runtime entailment gate | E1 | ≥ 80% claims entailment ≥ 0.6 |
| G2 no reject+revise loop | E2 | ≥ 10% RAGAS faithfulness gain over baseline, p<0.05 |
| G3 supportedness ≠ faithfulness | E3, E7 | report supportedness + reliance flags; verifier P/R vs human |
| G4 no honest privacy posture | E4 | Groq ≤ 30s / Ollama ≤ 90s; per-mode data-flow statement |
| G5 reproducibility on CPU | E5, E6 | runs on i7/16 GB, < 11 GB active RAM, no GPU |

*Each enhancement that ships must update `software-design-document.md` and `changelog.md` (per the documentation rules).*
