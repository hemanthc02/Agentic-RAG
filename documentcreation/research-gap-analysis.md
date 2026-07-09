# Research Gap Analysis (Per-Paper)
**Phase:** 2/4 (step 2 deepened) · **Version:** 1.0 · **Date:** 2026-06-07
**Companion to:** `research-analysis.md`, `gap-analysis.md`. This file satisfies the execution-order requirement for `research-gap-analysis.md` with the per-paper schema (Architecture · Dataset · Methodology · Metrics · Weaknesses) and the superiority argument.

> Sources verified June 2026 (links in `research-analysis.md` §12). Foundational papers (RAG, Self-RAG, CRAG, RAGAS, Adaptive-RAG) summarised from established knowledge; 2025 works (SQuAI, MA-RAG, MAIN-RAG, Wallat) verified against arXiv/ACL/CIKM.

## 1. Per-paper teardown

### RAG — Lewis et al., NeurIPS 2020
- **Architecture:** Parametric seq2seq generator (BART) + non-parametric DPR retriever over a dense index; RAG-Sequence / RAG-Token marginalisation.
- **Dataset:** Open-domain QA (NQ, TriviaQA, WebQuestions), FEVER, Jeopardy generation.
- **Methodology:** Retrieve top-k passages, condition generation; end-to-end trained retriever+generator.
- **Metrics:** EM/F1 (QA), accuracy (fact verification).
- **Weaknesses:** Single-shot; no relevance correction; **no attribution/verification**; trained, not modular.

### Self-RAG — Asai et al., ICLR 2024
- **Architecture:** Single LM trained to emit reflection tokens (`Retrieve`, `IsRelevant`, `IsSupported`, `IsUseful`); adaptive retrieval + self-critique + segment-level beam selection.
- **Dataset:** Open-domain QA, long-form generation, fact verification (PopQA, ARC, bio generation, etc.).
- **Methodology:** Train on data augmented with reflection tokens; at inference, critique own segments.
- **Metrics:** Accuracy, FactScore, citation precision/recall (self-reported).
- **Weaknesses:** **Self-judgement** (generator critiques itself → post-rationalisation risk); requires **fine-tuning**; general-domain; no CPU/privacy story.

### CRAG — Yan et al., 2024
- **Architecture:** Lightweight retrieval **evaluator** (T5-based) scoring retrieved docs → {Correct, Incorrect, Ambiguous} → corrective actions (decompose-recompose, query rewrite, web fallback).
- **Dataset:** PopQA, Biography, PubHealth, Arc-Challenge.
- **Methodology:** Plug-in evaluator over any RAG; corrective retrieval pre-generation.
- **Metrics:** Accuracy/FactScore.
- **Weaknesses:** Corrects **retrieval**, not **attribution**; web fallback breaks air-gap; no per-claim verification.

### SQuAI — Besrour, He, Schreieder, Färber; CIKM 2025  *(closest prior work)*
- **Architecture:** Four collaborative agents; **hybrid sparse-dense retrieval**; adaptive document filtering; in-line citations + supporting sentences; UI with selectable LLM backend + retrieval config.
- **Dataset:** **2.3M full-text arXiv papers**; scientific open-domain QA.
- **Methodology:** Decompose → hybrid retrieve → filter → generate with citations + supporting sentences.
- **Metrics:** Answer quality + citation/attribution quality (precision-style), human/LLM judged.
- **Weaknesses:** Supporting sentences are **display, not a verification gate**; **no entailment scoring, no accept/reject threshold, no reject-and-revise loop**; cloud-scale, **no CPU/air-gapped mode**; value is scale, not verifiability.

### Agentic RAG Survey — Singh et al., 2025
- **Architecture/Dataset/Methodology:** N/A (survey); taxonomy of agentic patterns.
- **Use:** Positioning. **Weakness for us:** confirms multi-agent decomposition is now table-stakes → our differentiation must be the verifier, not the agents.

### Correctness ≠ Faithfulness — Wallat, Heuss, de Rijke, Anand; 2024  *(motivation)*
- **Architecture:** Analysis framework, not a system; distinguishes **correctness** (cited doc supports statement) vs **faithfulness** (model genuinely relied on it vs post-rationalised).
- **Dataset:** Attribution/QA settings with citation annotations.
- **Methodology:** Measure correctness and faithfulness separately; expose post-rationalisation.
- **Metrics:** Citation correctness, citation faithfulness; **finding: up to 57% unfaithful**.
- **Weaknesses (our opening):** **Diagnoses, does not remediate** — no runtime system. Also: faithfulness is a *counterfactual* property NLI alone cannot measure.

### MA-RAG — Nguyen, Chin, Tai; 2025
- **Architecture:** Agents Planner / Step-Definer / Extractor / QA with chain-of-thought messaging; training-free.
- **Dataset:** NQ, HotpotQA, 2WikiMQA, TriviaQA (multi-hop/ambiguous).
- **Methodology:** Task decomposition + CoT evidence extraction + synthesis.
- **Metrics:** EM/F1, multi-hop accuracy.
- **Weaknesses:** **No citation verification**; open-benchmark, not private-corpus; no privacy/CPU story.

### RAGAS — Es et al., EACL 2024
- **Architecture:** Reference-light evaluation framework.
- **Methodology:** LLM-assisted decomposition into statements; check support against context; answer/question alignment.
- **Metrics:** Faithfulness, answer relevance, context precision/recall.
- **Weaknesses:** **LLM-judged** → noisy, potentially circular; not ground truth. We triangulate with independent NLI + human labels.

### Adaptive-RAG — Jeong et al., NAACL 2024
- **Architecture:** Complexity classifier routing to no-retrieval / single-step / multi-step.
- **Dataset:** Single- and multi-hop QA.
- **Methodology:** Train a router; adapt retrieval depth to question complexity.
- **Metrics:** Accuracy vs cost/latency.
- **Weaknesses:** Routing only; no attribution. **Adopt as future Planner routing (E8).**

### MAIN-RAG — Chang et al., ACL 2025
- **Architecture:** Three agents — Predictor / Judge / Final-Predictor; training-free adaptive document filtering with distribution-based threshold.
- **Dataset:** Four QA benchmarks.
- **Methodology:** Predict answer → judge doc support → filter/order → final answer.
- **Metrics:** Answer accuracy (+2–11%), retrieval noise reduction.
- **Weaknesses:** **Filters documents for relevance, not claims for entailment**; never checks the final answer's sentence→evidence link.

## 2. Cross-paper synthesis (the four systemic gaps)
1. Verification targets **retrieval inputs**, not **claim attributions** (CRAG, MAIN-RAG).
2. Where supportedness exists it is **self-judged** (Self-RAG) or **display-only** (SQuAI).
3. The faithfulness problem is **diagnosed but unremediated** (Wallat).
4. Systems are **scale-first**, never **access/privacy-first** (SQuAI, MA-RAG).

## 3. Why our approach is superior (claim → mechanism → evidence)

| Dimension | Prior best | Our approach | Why superior |
|---|---|---|---|
| **Method** | Self-RAG self-critique; SQuAI display | Independent NLI gate + reject/revise loop | Breaks self-judgement circularity; *enforces* not displays |
| **Faithfulness** | Wallat diagnoses only | Report supportedness **and** counterfactual reliance | First runtime operationalisation of the distinction |
| **Pipeline** | Static agent chains | LangGraph state machine w/ conditional verify→revise edge | Closes the loop; bounded, measurable |
| **Evaluation** | RAGAS (LLM-judged) | RAGAS **+** independent NLI **+** human-labelled verifier P/R, blind/adversarial benchmark | Less circular, more credible |
| **Accuracy (faithfulness)** | ~43% faithful (Wallat baseline) | ≥ 80% claims ≥ 0.6 supportedness target | Direct attack on the measured failure |
| **Latency** | Cloud-scale, GPU | Cloud ≤30s / local ≤90s on CPU; cap retries | Usable without GPU; predictable |
| **Scalability** | 2.3M papers, cloud (SQuAI) | pgvector HNSW per-tenant + async workers + provider abstraction | Scales as SaaS while preserving local mode |
| **Privacy** | Cloud-only / unqualified | Mode-specific, air-gapped profile, local retriever+verifier | Serves regulated buyers others can't |

## 4. Publishable contributions (restated, honest)
C1: Independent claim-entailment verifier as a first-class agent with a bounded reject-and-revise loop (no referenced system does this). 
C2: Operationalising Wallat's correctness/faithfulness split — report supportedness + a counterfactual reliance signal. 
C3: A reproducible CPU-only, dual-mode benchmark and reference implementation. 
**Explicitly not claimed as novel:** multi-agent decomposition, inline citations, swappable backends (SQuAI has them); "NLI verifies faithfulness" (it verifies supportedness; reliance is probed separately).

*Changes logged in `changelog.md`.*
