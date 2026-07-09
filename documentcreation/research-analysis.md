# Research Analysis Report
**Project:** Multi-Agent RAG System for Academic Research Assistance — A CPU-Friendly Agentic Pipeline with Citation Faithfulness Verification
**Phase:** 1 — Research & Analysis
**Document version:** 1.0
**Date:** 2026-06-07
**Status:** Authored (this is the Phase-1 headline deliverable; produced before any application code)
**Sources analysed:** `review-01/Abstract.docx`, `review-01/Project_Explainer.docx`, `review-01/Project_Review_01.pptx` (15 slides), `review-01/References.docx` (10 works), plus primary-source verification of the referenced papers via web search (see §12).

---

## 1. Executive summary

The project targets a real and well-documented failure mode of Retrieval-Augmented Generation (RAG): **citations that look right but are not actually supported by the cited evidence.** Wallat et al. (2024) measured this at *up to 57% of citations being unfaithful*. The proposed system answers questions over a user's own PDF corpus with a four-agent pipeline (Planner → Retriever → Synthesizer → Verifier) and adds — as its headline novelty — a **dedicated Natural Language Inference (NLI) verifier** that scores each claim against its cited evidence and triggers revision when the score is low. It runs CPU-only and offers two interchangeable LLM backends (Groq cloud / Ollama local).

After reading all review-01 materials and verifying the cited literature against primary sources, this report's central findings are:

1. **The problem is real and commercially relevant.** Citation hallucination is the single biggest blocker to trustworthy AI research assistants, and the markets (scholarly publishing, legal, pharma) are large and already paying for RAG.
2. **The architecture is sound but not, by itself, novel.** Multi-agent decomposition, CRAG-style relevance grading, in-line citations with supporting sentences, and even swappable LLM backends *all already exist* — notably in SQuAI (CIKM'25), which is the closest prior work and which the project itself names.
3. **The defensible novelty is narrower and sharper than stated** — and is stronger once stated precisely: *operationalising citation verification as an independent, model-based entailment gate with a reject-and-revise loop inside an agentic RAG pipeline, on commodity CPU hardware, with an honest dual-mode privacy story.* No referenced system does this.
4. **There is a conceptual risk the project must address head-on:** an NLI entailment score measures **citation *supportedness*** (≈ Wallat's "correctness"), not **citation *faithfulness*** in Wallat's precise sense (whether the model *genuinely relied* on the source rather than post-rationalising). Conflating the two would be the easiest point for a reviewer to attack. §8.4 and the gap analysis turn this risk into the project's most publishable contribution.

The work is viable as (a) a reproducible open-source reference implementation, (b) a SaaS product for privacy-sensitive literature review, and (c) a short publishable paper — *provided* the faithfulness/supportedness distinction is handled rigorously and the evaluation is honest about it.

---

## 2. Problem statement

**As framed by the project (verbatim intent from the deck, slide 4):**
> How can we build a research-assistant system that answers complex academic questions from a local PDF corpus with citations that are *demonstrably faithful* to the cited evidence, while running on consumer-grade CPU hardware?

This decomposes into four sub-problems, each mapped to an agent:

| # | Sub-problem | Agent | ML task type |
|---|---|---|---|
| 1 | Decompose multi-hop questions into atomic sub-queries | Planner | Seq2seq / prompting |
| 2 | Retrieve relevant chunks and detect when they are inadequate | Retriever | Dense IR + relevance grading (CRAG) |
| 3 | Generate grounded answers with structured inline citations | Synthesizer | Conditional LM |
| 4 | Verify each claim is entailed by its cited evidence | Verifier | Natural Language Inference |

**Root causes the project identifies (slide 4):** LLMs hallucinate; vanilla RAG over-trusts retrieval; citations get post-rationalised; cloud RAG ≠ private RAG.

**Reframed for a SaaS/research context.** The market problem is *trust and compliance*, not just answer quality. A research assistant that cannot prove its citations is unusable in exactly the high-value domains (pharma, legal, regulated research) where literature review is most expensive. The technical problem is therefore: **produce answers whose every claim carries a verifiable, machine-checked evidence link, cheaply enough to run without a GPU and privately enough to run air-gapped.** That is a sharper, more defensible problem than "build a better RAG."

---

## 3. The research landscape

Using the taxonomy from the Agentic RAG survey (Singh et al., 2025), the relevant lineage is:

- **Foundational RAG** — Lewis et al. (2020): retrieve-then-generate; no self-correction, no verification.
- **Self-reflective RAG** — Self-RAG (Asai et al., 2024): the generator emits *reflection tokens* (e.g., `IsSupported`) to decide when to retrieve and to self-critique. Verification is *internal to the generator*.
- **Corrective RAG** — CRAG (Yan et al., 2024): a lightweight retrieval *evaluator* grades retrieved docs and triggers query rewriting / corrective actions when retrieval is weak. Corrects *retrieval*, not *attribution*.
- **Adaptive RAG** — Adaptive-RAG (Jeong et al., 2024): routes questions by complexity (no-retrieval / single-step / multi-step) to balance cost and accuracy.
- **Multi-agent RAG** — SQuAI (Besrour et al., CIKM'25), MA-RAG (Nguyen et al., 2025), MAIN-RAG (Chang et al., ACL'25): decompose the task across collaborating agents.
- **The faithfulness diagnosis** — Wallat et al. (2024): defines and *measures* the post-rationalisation problem but does not build a system to fix it.
- **Evaluation** — RAGAS (Es et al., 2024): standardised faithfulness / answer-relevance / context metrics.

The project sits at the intersection of *multi-agent RAG* + *corrective RAG* + *the faithfulness diagnosis*, and proposes to close the loop the diagnosis opened.

---

## 4. Per-paper analysis: what each implemented, strengths, weaknesses

> Authorship/venue verified against primary sources where the project's `References.docx` was ambiguous or contained errors (see §12 corrections).

### [1] RAG — Lewis et al., NeurIPS 2020
- **Implemented:** The retrieve-then-generate paradigm; a parametric generator conditioned on non-parametric retrieved passages.
- **Strengths:** Foundational; grounds generation in external knowledge; reduces (not eliminates) hallucination.
- **Weaknesses (vs this project):** No self-assessment, no relevance correction, **no citation verification**. Single-shot. This is exactly the "vanilla RAG" baseline the project intends to beat.

### [2] Self-RAG — Asai et al., ICLR 2024
- **Implemented:** A single LM trained to emit reflection tokens controlling retrieval and self-critique (`Retrieve?`, `IsRelevant`, `IsSupported`, `IsUseful`).
- **Strengths:** Introduces *supportedness* as a first-class signal; controllable at inference; strong results.
- **Weaknesses:** The critic **is the generator judging itself** — structurally vulnerable to the same post-rationalisation Wallat describes. Requires *training* the reflection behaviour (the project is explicitly no-fine-tuning). General-domain, not CPU-budgeted.
- **Relevance:** Self-RAG's `IsSupported` token is the *closest existing idea* to the project's verifier — and the key difference (independent NLI model vs self-judgement, prompted vs trained) is precisely where the project must plant its flag.

### [3] CRAG — Yan et al., 2024
- **Implemented:** A lightweight retrieval evaluator that scores retrieved docs and triggers corrective query rewriting / decompose-recompose; can fall back to web search.
- **Strengths:** Cheap, plug-in; meaningfully improves retrieval quality.
- **Weaknesses:** Corrects **retrieval**, never **attribution** — a perfectly retrieved chunk can still be mis-cited. The project correctly adopts CRAG-style grading for the Retriever but must not claim it as the faithfulness fix.

### [4] SQuAI — Besrour, He, Schreieder, Färber; CIKM 2025 (CLOSEST PRIOR WORK)
- **Implemented:** A **four-agent** scientific QA system over **2.3M full-text arXiv papers**; question decomposition; **hybrid sparse-dense retrieval**; **adaptive document filtering**; **in-line citations with supporting sentences**; an end-to-end UI with **selectable LLM backend and retrieval config**.
- **Strengths:** Production-scale corpus; strong engineering; already provides traceability (supporting sentences) and backend choice.
- **Weaknesses (the opening):** Traceability via supporting sentences is **display, not verification** — there is no independent entailment score, no accept/reject threshold, and **no reject-and-revise loop** that forces the synthesizer to fix unfaithful claims. No CPU/air-gapped story; the value proposition is scale, not privacy or verifiability.
- **Implication for novelty:** The project **cannot** claim multi-agent decomposition, citations, or swappable backends as novel — SQuAI has all three. It **can** claim the verification gate and the local-privacy posture.

### [5] Agentic RAG Survey — Singh et al., 2025
- **Implemented:** A taxonomy of agentic RAG patterns (reflection, planning, tool-use, multi-agent).
- **Use:** Framing/positioning only. Confirms that "agent specialisation" is now standard — reinforcing that the project's differentiation must be the *verifier*, not the *multi-agent* structure.

### [6] Correctness ≠ Faithfulness — Wallat, Heuss, de Rijke, Anand; 2024 (MOTIVATION)
- **Implemented:** A formal distinction between citation **correctness** (does the cited doc substantiate the statement?) and citation **faithfulness** (did the model *genuinely rely* on the source vs post-rationalise?); measurement showing **up to 57% of citations unfaithful**.
- **Strengths:** Names and quantifies the exact gap the project targets; high citation value as motivation.
- **Weaknesses / what it leaves open:** It **diagnoses, it does not remediate** — no system, no runtime fix. *This is the project's opening.*
- **Critical caveat for the project:** Wallat-*faithfulness* is a *counterfactual/attribution* property (would the model have said this without the source?). An NLI entailment check measures *supportedness* (does the text support the claim?), which is closer to Wallat-*correctness*. **The project must not claim to verify Wallat-faithfulness with NLI alone** (see §8.4).

### [7] MA-RAG — Nguyen, Chin, Tai; 2025
- **Implemented:** Agents Planner / Step-Definer / Extractor / QA, communicating via chain-of-thought; strong on multi-hop QA (HotpotQA, 2WikiMQA, etc.); training-free.
- **Strengths:** Clean modular interpretability; good multi-hop reasoning.
- **Weaknesses:** No citation verification; evaluated on open benchmarks, not on a user's private corpus; no privacy/CPU story.

### [8] RAGAS — Es et al., EACL 2024
- **Implemented:** Reference-light automated RAG metrics (faithfulness, answer relevance, context precision/recall).
- **Use:** The project's evaluation backbone.
- **Caveat:** RAGAS "faithfulness" is itself **LLM-judged** and can be noisy; the project should not treat it as ground truth and should triangulate with its own NLI metric and human spot-checks.

### [9] Adaptive-RAG — Jeong et al., NAACL 2024
- **Implemented:** Complexity-aware routing across no/single/multi-step retrieval.
- **Use:** A natural *future* enhancement for the Planner (cost-adaptive routing) — currently out of scope.

### [10] MAIN-RAG — Chang, Jiang, Rakesh, et al.; ACL 2025
- **Implemented:** Three agents (Predictor / Judge / Final-Predictor); training-free **document filtering** with an adaptive score threshold; +2–11% answer accuracy.
- **Strengths:** Elegant adaptive thresholding; reduces irrelevant context.
- **Weaknesses:** The "Judge" filters **documents for relevance**, not **claims for entailment** — it never checks whether the final answer's sentences are supported by what was cited. Confirms the field verifies *inputs*, not *attributions*.

---

## 5. Limitations of current research (synthesis)

Across the ten works, four systemic gaps recur:

1. **Verification targets retrieval, not attribution.** CRAG and MAIN-RAG grade *documents*; nobody gates the *claim→evidence* link with an independent model.
2. **Self-judgement, not independent judgement.** Self-RAG's supportedness signal comes from the generator itself — the very source of post-rationalisation.
3. **Diagnosis without remediation.** Wallat proves the problem exists; no referenced system closes the loop at runtime.
4. **Scale-first, not access-first.** SQuAI/MA-RAG assume cloud-scale corpora and GPUs; none offers a CPU-only, air-gapped, reproducible deployment — which is exactly what regulated and low-resource users need.

---

## 6. Research gaps (the openings)

- **G1 — No runtime claim-level entailment gate.** A dedicated verifier that scores each claim against cited evidence and *rejects* low-scoring claims is absent from all referenced systems.
- **G2 — No reject-and-revise control loop driven by verification.** Even where supportedness is signalled (Self-RAG), it is not wired into a bounded retry that *forces* the synthesizer to repair specific failed claims.
- **G3 — Faithfulness ≠ supportedness is unoperationalised.** No system distinguishes "the evidence supports the claim" from "the model actually used the evidence." This is wide open and *publishable*.
- **G4 — No honest, mode-specific privacy posture.** No referenced system delivers a verifiable local/air-gapped mode with a precise statement of what does and does not leave the device.
- **G5 — Reproducibility on commodity hardware is unaddressed.** CPU-only, sub-11GB-RAM, free-tier reproducibility is itself a contribution for the long tail of researchers and small labs.

---

## 7. Opportunities for innovation (summary; detailed in `gap-analysis.md`)

1. **Independent NLI entailment verifier** as a first-class agent (closes G1).
2. **Verifier-driven reject-and-revise loop** with bounded retries and targeted feedback (closes G2).
3. **Supportedness *and* a reliance probe** — e.g., leave-one-out / counterfactual citation testing to approximate Wallat-faithfulness, not just entailment (closes G3; the strongest publication angle).
4. **Honest dual-mode backend** (Groq/Ollama) with a precise data-flow privacy statement (closes G4).
5. **CPU-only reproducible reference implementation** with a pinned, free, open-source stack (closes G5).
6. **Calibrated, per-claim faithfulness UI** — surfacing scores and letting users reject, turning verification into explainability (XAI-by-design).

---

## 8. How our solution can outperform prior work

### 8.1 Positioning matrix (verified against primary sources)

| Capability | RAG | Self-RAG | CRAG | SQuAI | MA-RAG | MAIN-RAG | **This project** |
|---|---|---|---|---|---|---|---|
| Multi-agent decomposition | — | — | — | ✅ | ✅ | ✅ | ✅ |
| Retrieval relevance correction | — | partial | ✅ | ✅ | partial | ✅ | ✅ (CRAG-style) |
| Inline citations | — | partial | — | ✅ | — | — | ✅ |
| Supportedness signal | — | ✅ (self) | — | display only | — | — | ✅ (**independent NLI**) |
| Claim-level reject **+ revise loop** | — | — | — | — | — | — | ✅ **(novel)** |
| Faithfulness vs supportedness handled | — | — | — | — | — | — | ✅ (proposed, G3) |
| CPU-only / air-gapped mode | — | — | — | — | — | — | ✅ **(novel posture)** |
| No fine-tuning required | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ |

The two columns no prior system fills — **claim-level reject+revise** and **CPU/air-gapped verifiable mode** — are the defensible contribution.

### 8.2 Expected quantitative edge
The project's own KPIs (slide 5): NLI entailment ≥ 0.6 for ≥ 80% of claims (vs ~43% baseline implied by Wallat); ≥ 10% RAGAS faithfulness gain; ≥ 5% answer-relevance gain; Groq ≤ 30s, Ollama ≤ 90s; paired t-test p < 0.05 on a 20-question benchmark. These are reasonable *if* the benchmark is honest (see §9).

### 8.3 Why the verifier should actually help
An independent NLI model breaks the self-judgement circularity of Self-RAG: the entity scoring the claim is not the entity that wrote it, so it cannot post-rationalise its own output. Combined with a bounded revise loop, low-support claims are either repaired or surfaced — strictly dominating "cite and hope."

### 8.4 The one thing that must be right (faithfulness vs supportedness)
**This is the most important finding in this report.** An NLI premise→hypothesis entailment score answers *"does the cited text support this claim?"* — i.e. **supportedness / Wallat-correctness.** It does **not** answer *"did the model genuinely rely on this source?"* — i.e. **Wallat-faithfulness.** A claim can be fully entailed yet post-rationalised (model knew it anyway and bolted on a citation). Therefore:

- The verifier, as specified, is best and most honestly described as a **Citation Supportedness Verifier** (it catches the *unsupported* citations, which are the majority and the most harmful).
- To genuinely address Wallat-faithfulness, add a **reliance probe** (G3): re-generate the claim with the cited chunk removed; if the claim is unchanged, the citation was likely post-rationalised. Reporting *both* supportedness and a reliance signal is a clean, novel, publishable result — and it pre-empts the sharpest reviewer objection.

Getting this naming and measurement right *increases* credibility; overclaiming "we verify faithfulness" with NLI alone *destroys* it.

---

## 9. Threats to validity (must be controlled)

- **Benchmark bias.** 20 self-authored Q&A pairs are tiny and prone to confirmation bias. Mitigate: pre-register questions, blind the grading, include adversarial/multi-hop and "answer-not-in-corpus" cases, and report human inter-annotator agreement on a subset.
- **NLI domain mismatch.** DeBERTa-v3-MNLI is general-domain; scientific claims are dense and technical. Mitigate: calibrate the 0.6 threshold on a held-out set, sentence-segment premises, and report verifier precision/recall against human labels — not just downstream RAGAS.
- **Circular evaluation.** RAGAS faithfulness is LLM-judged; if the same family judges and generates, gains may be illusory. Mitigate: triangulate RAGAS + independent NLI + human spot-check.
- **Latency under retries.** Each revise pass adds a full synthesize+verify cycle; Ollama mode could blow the 90s budget. Mitigate: cap retries (2), measure worst-case, and report retry distribution.

---

## 10. SaaS productization lens

The research artifact maps cleanly onto a product:
- **Wedge:** privacy-first, verifiable literature review for regulated teams (pharma/legal/gov) — the segment SQuAI and Scopus AI (cloud, closed) do **not** serve.
- **Moat:** the verification + reject/revise loop and the calibrated faithfulness UI are hard to fake and directly address buyer trust.
- **Pricing logic:** CPU/free-tier inference → near-zero marginal cost → viable freemium with a paid "local/air-gapped + audit log" tier.
- **Gaps to close for product (out of current scope, tracked for Phase 2):** multi-user/RBAC, persistence (Postgres/Redis), observability, evaluation-as-a-service, and the full Next.js SaaS shell described in the project's Phase-4 stack.

## 11. Publication potential

A focused short paper is realistic: *"An Independent NLI Verifier with Reject-and-Revise for Faithful, CPU-Only Agentic RAG — and why supportedness ≠ faithfulness."* Contributions: (a) the verifier-in-the-loop architecture; (b) the supportedness/reliance distinction operationalised; (c) a reproducible CPU benchmark. Venue fit: workshop or short-paper tracks at *EACL/ACL/CIKM/SIGIR* or an LLM-systems workshop. The honest dual contribution (it works *and* here's what it does/doesn't measure) is more publishable than an overclaimed "we solved faithfulness."

---

## 12. Source verification & corrections to `References.docx`

Primary-source checks (web, June 2026) surfaced citation errors the project should fix before any write-up:

- **[6] Wallat et al.** — correct authors are **Jonas Wallat, Maria Heuss, Maarten de Rijke, Avishek Anand** (arXiv:2412.18004, Dec 2024). The References.docx author list ("M. Heinrich, J. Singh, A. Anand") is **incorrect**. The 57%-unfaithful figure is **confirmed**.
- **[4] SQuAI** — verified as **Besrour, He, Schreieder, Färber**, **CIKM 2025** (arXiv:2510.15682). Confirmed features: 2.3M arXiv papers, 4 agents, hybrid retrieval, adaptive filtering, in-line citations + supporting sentences, **selectable LLM backend**. (Project's author list differs; reconcile against the published version.)
- **[10] MAIN-RAG** — **Chang et al., ACL 2025** (long paper; arXiv:2501.00332). The References.docx labels it "Findings of ACL" — verify against the ACL Anthology entry (2025.acl-long.131) before citing.
- **[7] MA-RAG** — verified **Nguyen, Chin, Tai** (arXiv:2505.20096); agents Planner/Step-Definer/Extractor/QA. Confirmed: no citation verifier.

**Sources (verification):**
- SQuAI — https://arxiv.org/abs/2510.15682 ; https://dl.acm.org/doi/10.1145/3746252.3761471
- Wallat et al. — https://arxiv.org/abs/2412.18004
- MA-RAG — https://arxiv.org/abs/2505.20096
- MAIN-RAG — https://aclanthology.org/2025.acl-long.131/ ; https://arxiv.org/abs/2501.00332

---

## 13. Conclusion & recommendation

The project addresses a real, valuable, well-motivated problem and its architecture is competent. Its originality, stated loosely ("multi-agent RAG with a verifier"), is **partially pre-empted by SQuAI**. Stated precisely — **an independent, model-based claim-entailment gate with a bounded reject-and-revise loop, on reproducible CPU hardware, with an honest local-privacy mode, and a principled treatment of supportedness vs faithfulness** — it is **defensible, useful, and publishable.**

**Recommendation:** proceed to Phase 2 (SDD) with three non-negotiables baked in: (1) rename/reframe the verifier as *supportedness* and add a *reliance probe* for true faithfulness; (2) design the benchmark to be adversarial and blind from day one; (3) keep the privacy claims mode-specific and precise. These choices convert the project's biggest vulnerability into its biggest contribution.

*Next document: `gap-analysis.md` (Phase 3 — per-enhancement contribution table).*
