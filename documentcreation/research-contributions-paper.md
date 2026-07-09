# Verified-Citation Multi-Agent RAG — Contributions, Improvements over Prior Work, and Evaluation Protocol

**Document type:** MTech project research writeup (publication-support draft)
**Status:** v1.0 — 2026-06-14
**Companion sources (in `documentcreation/`):** `research-analysis.md`, `research-gap-analysis.md`, `gap-analysis.md`, `changelog.md`
**Implementation:** `src/agents/` (pipeline), `src/agents/verifier.py` (novelty), `src/evaluation.py` (benchmark)

> **Honesty notice for the authoring student.** This document states the
> *methodology* and the *contributions* and gives a *results template*. It does
> **not** contain measured improvement numbers, because the benchmark has not yet
> been run on a real corpus (see §7). Every cell marked `‹fill›` must be filled
> from your own run of `python -m src.evaluation --compare` before this goes into
> a thesis or paper. Do not publish target numbers as if they were measured. Two
> external figures attributed to Wallat et al. (2024) — "up to 57% unfaithful"
> and the "~43% faithful" baseline — are taken from the project's prior
> `research-gap-analysis.md`; **re-confirm them against the primary source
> (arXiv:2412.18004) before camera-ready.**

---

## 1. Abstract

Retrieval-Augmented Generation (RAG) grounds language-model answers in retrieved
evidence, but recent analysis shows that a large fraction of the citations such
systems emit are *unfaithful* — they look correct yet are not actually entailed
by the cited passage (Wallat et al., 2024 — figure to be confirmed). Existing
multi-agent and corrective RAG systems either verify *retrieval relevance* (CRAG,
MAIN-RAG), rely on the generator to *self-critique* (Self-RAG), or *display*
supporting sentences without enforcing them (SQuAI). None treats per-claim
citation verification as an independent, enforcing control step.

We present a four-agent RAG system (Planner → Retriever → Synthesizer → Verifier)
in which **citation verification is a first-class agent**: a Natural-Language-
Inference (NLI) cross-encoder scores whether each cited sentence is entailed by
its cited evidence, and a **bounded reject-and-revise loop** sends low-scoring
answers back to the Synthesizer (up to *N* retries) instead of returning them.
The entire retrieval + verification stack runs **CPU-only** under an 11 GB RAM
budget, with a swappable LLM that is either a fast cloud model (Groq · Llama 4
Scout 17B) or a fully on-device model (Ollama · Phi-3 mini) — making the system
usable in privacy-constrained, GPU-free settings. We release a reproducible
benchmark that compares a vanilla single-shot RAG baseline against the multi-agent
pipeline on a fixed question set, scoring both with the *same* NLI metric and
testing the difference with a paired *t*-test.

---

## 2. Problem & motivation

- **RAG hallucinates *attributions*, not just facts.** A citation can point at a
  real, on-topic passage that nonetheless does not support the specific claim.
  Wallat et al. (2024) separate **citation correctness** (does the cited document
  support the statement?) from **citation faithfulness** (did the model genuinely
  rely on it, vs. post-rationalise it after deciding the answer?) and report a
  high unfaithful rate (figure to confirm). This is the failure we target.
- **Prior verification is in the wrong place.** Corrective methods grade *retrieved
  documents* before generation; they never check the *final sentence → evidence*
  link. Self-critique keeps the judge inside the same model that produced the
  answer, which is exactly the post-rationalisation loop Wallat warns about.
- **Verification is shown, not enforced.** Where systems surface supporting
  sentences (SQuAI), it is a UI affordance, not an accept/reject gate with a
  threshold and a remediation path.
- **Scale-first, not access-first.** The strongest systems assume cloud scale and
  GPUs; none offers an honest, fully-local privacy mode.

---

## 3. Related work and its limitations (condensed from `research-gap-analysis.md`)

| System (year) | What it does | Limitation we exploit |
|---|---|---|
| **RAG** — Lewis et al., 2020 | Parametric generator + dense retriever, single-shot | No attribution or verification at all |
| **Self-RAG** — Asai et al., 2024 | LM emits reflection tokens incl. `IsSupported` | **Self-judged** (post-rationalisation risk); needs fine-tuning |
| **CRAG** — Yan et al., 2024 | Lightweight evaluator grades *retrieval*, rewrites/queries web | Corrects retrieval, **not claim attribution**; web fallback breaks air-gap |
| **Adaptive-RAG** — Jeong et al., 2024 | Complexity router → no/single/multi-step retrieval | Routing only; no attribution (we adopt it as future Planner routing) |
| **RAGAS** — Es et al., 2024 | Reference-light faithfulness/relevance metric | **LLM-judged**, potentially circular; a metric, not an inline gate |
| **MAIN-RAG** — Chang et al., 2025 | Predictor/Judge/Final-Predictor filter documents | Filters **documents for relevance**, not **claims for entailment** |
| **MA-RAG** — Nguyen et al., 2025 | Planner/Step-Definer/Extractor/QA, CoT | **No citation verification**; open-benchmark, not private corpus |
| **SQuAI** — Besrour et al., 2025 *(closest)* | Four agents, hybrid retrieval, inline citations + supporting sentences | Supporting sentences are **display, not a gate**; no entailment score, no threshold, **no reject-and-revise**; no CPU/air-gap mode |

**Four systemic gaps** (cross-paper synthesis): (1) verification targets retrieval
inputs, not claim attributions; (2) where supportedness exists it is self-judged
or display-only; (3) the faithfulness problem is diagnosed but unremediated; (4)
systems are scale-first, never access/privacy-first.

---

## 4. What is new in this work (contributions)

**C1 — Citation verification as a first-class, enforcing agent.**
An independent NLI cross-encoder (`cross-encoder/nli-deberta-v3-base`) scores the
entailment of each cited answer-sentence against its cited chunk(s). Crucially,
this is *external* to the generator (breaking the self-judgement circularity of
Self-RAG) and it *gates* the output via a threshold (`CITATION_FAITHFULNESS_THRESHOLD`),
rather than merely displaying support (SQuAI).

**C2 — A bounded reject-and-revise control loop.**
The pipeline is a LangGraph state machine with a conditional edge: if the answer
fails verification and the retry budget (`MAX_VERIFIER_RETRIES`) is not exhausted,
the Verifier returns the failed claims to the Synthesizer with targeted feedback;
otherwise it stops. The answer's `verified` status reflects the *true* outcome —
an answer that never passes is returned **honestly marked unverified**, not
silently accepted.

**C3 — A reproducible, CPU-only, dual-mode benchmark and reference implementation.**
A single command runs the vanilla baseline and the multi-agent pipeline over a
fixed question set, scores both with the *same* NLI metric, and reports a paired
*t*-test on per-question faithfulness. The whole retrieval + verification stack is
CPU-only (MiniLM embeddings, FAISS, DeBERTa NLI) under an 11 GB budget; only the
LLM is remote, and only in cloud mode.

**Explicitly NOT claimed as novel** (to keep the contribution defensible):
multi-agent decomposition, inline citations, and swappable LLM backends (SQuAI
already has these); and the use of NLI itself for attribution checking (prior
attribution-evaluation work does entailment checks). The defensible novelty is the
**architecture** — entailment verification as a bounded, looping control agent
*inside* the system — and the **honest CPU/dual-mode** engineering, not NLI per se.

> **Faithfulness vs. supportedness — a precise claim.** NLI measures whether the
> evidence *entails* the claim (**supportedness**). True **faithfulness** in
> Wallat's sense (did the model *rely* on the source?) is counterfactual and NLI
> alone cannot establish it. We therefore claim to enforce **supportedness** and
> to *probe* reliance separately; do not overclaim "faithfulness" in the paper.

---

## 5. System architecture

```
Question
   │
   ▼
[Planner]      decomposes into ≤3 focused sub-questions (LLM, JSON-constrained)
   │
   ▼
[Retriever]    FAISS semantic search per sub-question + CRAG-style query rewrite
   │            when top relevance < threshold; merge + dedupe + rank
   ▼
[Synthesizer]  grounded answer with inline [n] citations; untrusted source text
   │            is delimited and treated as data (prompt-injection hardening)
   ▼
[Verifier] ◄── NLI entailment per cited sentence → per-claim score + verdict;
   │   │        overall_faithfulness = mean over CITED claims only
   │   └─ revise (failed + retry budget left) ─► back to Synthesizer
   ▼ done
Answer + per-claim faithfulness + verified flag + stage log
```

Local-only components (both modes): MiniLM embeddings (`all-MiniLM-L6-v2`, 384-d),
FAISS (flat ≤5k chunks, IVF above), DeBERTa-v3 NLI verifier, LangGraph
orchestration, PyMuPDF ingestion. Swappable LLM: **Groq · Llama 4 Scout 17B**
(cloud) or **Ollama · Phi-3 mini** (offline, auto-detected).

**Implementation correctness note (relevant to reviewers).** The metric is the
mean NLI entailment over *cited* claims; uncited sentences carry no score and an
answer with zero citations scores 0.0 (it cannot be "verified"). The premise
(evidence) and hypothesis (claim) are passed to the NLI model as a proper
**text pair**, not a concatenated string — a subtle but essential detail for the
entailment score to be meaningful. See `src/agents/verifier.py:verify_answer`.

---

## 6. Old → New: what we improved (qualitative)

| Dimension | Prior best | This work | Nature of improvement |
|---|---|---|---|
| Verification target | Retrieval relevance (CRAG/MAIN-RAG) | Per-claim sentence→evidence entailment | Moves the check to where the failure occurs |
| Judge independence | Self-critique (Self-RAG) | External NLI model | Removes self-judgement circularity |
| Enforcement | Display supporting sentences (SQuAI) | Threshold gate + reject-and-revise | Enforces, not merely shows |
| Outcome honesty | Accept on retry-exhaustion (common) | `verified=False` retained if never passes | No silent pass-through |
| Compute / privacy | Cloud + GPU | CPU-only, <11 GB, on-device offline mode | Usable in GPU-free / air-gapped settings |
| Evaluation rigour | LLM-judged (RAGAS) | NLI metric + paired *t*-test, baseline vs multi-agent | Independent, statistically tested |

These are *design* improvements. Their *measured* magnitude is the subject of §7
and must be filled in from a real run.

---

## 7. Evaluation protocol and results template

### 7.1 Protocol (reproducible)
1. Place the arXiv PDFs for the benchmark topic in `data/pdfs/`.
2. Build the index: `python -m src.retrieval --build --corpus default`.
3. Run the head-to-head experiment:
   `python -m src.evaluation --compare --corpus default` (add `--ragas` for the
   RAGAS cross-check; `--mode local --provider ollama` for the offline model).
4. The harness writes per-question CSVs and a summary JSON to `reports/`, and
   prints a paired *t*-test on per-question faithfulness (multi-agent − baseline).

**Metrics reported per pipeline:** mean citation faithfulness (mean NLI entailment
over cited claims), mean citation pass-rate (fraction of cited claims ≥ threshold),
verified-answer count, mean latency. **Comparison:** paired *t*-test (SciPy
`ttest_rel`) with mean improvement, *t*, df, and *p*-value.

### 7.2 Results — TO BE FILLED FROM YOUR RUN (do not publish placeholders)

| Metric | Baseline (vanilla RAG) | Multi-agent (+verifier) | Δ (improvement) |
|---|---|---|---|
| Mean citation faithfulness | `‹fill›` | `‹fill›` | `‹fill›` |
| Mean citation pass-rate | `‹fill›` | `‹fill›` | `‹fill›` |
| Verified answers (of 20) | `‹fill›` | `‹fill›` | `‹fill›` |
| Mean latency (s) — cloud | `‹fill›` | `‹fill›` | `‹fill›` |
| Mean latency (s) — local | `‹fill›` | `‹fill›` | `‹fill›` |

**Paired *t*-test (faithfulness, multi-agent − baseline):** mean Δ = `‹fill›`,
*t*(`‹df›`) = `‹fill›`, *p* = `‹fill›`. Report significance at α = 0.05.

**Targets (hypotheses, NOT results):** the prior `research-gap-analysis.md` sets a
target of "≥ 80% of claims at ≥ 0.6 supportedness," motivated against the Wallat
"~43% faithful" baseline (figure to confirm). State these as *hypotheses to test*,
and report whatever the run actually yields — including a null or negative result,
which is still publishable and honest.

---

## 8. Threats to validity / limitations (state these in the paper)

- **Supportedness ≠ faithfulness** (see §4): the verifier enforces entailment, not
  counterfactual reliance. The reliance probe is partial/future work.
- **NLI domain mismatch:** a general-domain NLI model on scientific text may
  mis-score; calibrate the threshold and report verifier precision/recall against
  a small human-labelled set before trusting the headline number.
- **Small benchmark:** 20 hand-curated questions is enough for a paired test but is
  not a large-scale claim; describe it as a controlled study, and consider a blind/
  adversarial subset (known-unfaithful items) to test rejection directly.
- **LLM variance:** Groq/Ollama outputs vary run-to-run; fix temperature (0.0–0.1),
  report mean ± std over ≥3 runs, and pin the model IDs in the paper.
- **External figures unverified here:** the Wallat statistics must be confirmed
  against the source (network access was unavailable when this draft was written).

---

## 9. Conclusion

The contribution is architectural and engineering, not a new model: a multi-agent
RAG system that makes **per-claim citation supportedness an enforced, looping
control step** rather than a self-judgement or a display, delivered on a
**CPU-only, dual-mode** stack that works offline. The accompanying benchmark makes
the improvement over a vanilla baseline **measurable and statistically testable**;
filling §7.2 from a real run completes the empirical story for publication.

---

## References (verify each against the primary source before submission)

Asai et al. 2024, *Self-RAG* (ICLR), arXiv:2310.11511 · Yan et al. 2024,
*Corrective RAG (CRAG)*, arXiv:2401.15884 · Lewis et al. 2020, *RAG* (NeurIPS) ·
Es et al. 2024, *RAGAS* (EACL) · Jeong et al. 2024, *Adaptive-RAG* (NAACL) ·
Wallat et al. 2024, *correctness vs faithfulness of citations*, arXiv:2412.18004
(**confirm the 57% / 43% figures**) · Besrour et al. 2025, *SQuAI* (CIKM),
arXiv:2510.15682 · Chang et al. 2025, *MAIN-RAG* (ACL), arXiv:2501.00332 · Nguyen
et al. 2025, *MA-RAG*, arXiv:2505.20096 · Singh et al. 2025, *agentic RAG survey*.

*(Full annotated bibliography in `documentcreation/research-analysis.md` §12.)*
