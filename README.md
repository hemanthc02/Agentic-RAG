# Multi-Agent RAG with Verified Citations

A research-paper Q&A assistant with a **verified-citation guarantee** that runs on a
normal CPU laptop. It answers academic questions from a local PDF corpus and
verifies its own citations with a Natural Language Inference (NLI) entailment model.

The full design, constraints, and 4-week plan live in [`prompt.md`](./prompt.md) —
**read that first** before changing any code.

## Why this exists

Existing multi-agent RAG systems lack a dedicated citation verifier. Wallat et al.
(2024) found up to **57%** of RAG citations are unfaithful — they look correct but
aren't actually entailed by the cited evidence. The novelty here is treating
**citation verification as a first-class agent** with NLI-based entailment scoring.

## Architecture

Four agents orchestrated by LangGraph:

```
Question → Planner → Retriever → Synthesizer → Verifier → Answer
                                       ▲            │
                                       └─ retry ◄───┘  (low faithfulness, max 2)
```

The LLM is the only swappable, potentially-remote component. Everything else —
embeddings, FAISS, the NLI verifier — runs locally in both modes.

## Two modes

| Mode | Backend | Model | Notes |
|------|---------|-------|-------|
| `groq` (default) | Groq API | Llama 3.3 70B | Fast + high quality; sends question + retrieved chunks over HTTPS |
| `ollama` (local) | Ollama @ localhost | Phi-3-mini | Fully on-device; slower, slightly lower quality |

## Privacy (read carefully — claims are mode-specific)

- **Your PDFs never leave the device** in either mode.
- **`groq` mode:** your question and the retrieved chunks (excerpts of your PDFs)
  are sent to Groq's API over HTTPS. This mode is **not** suitable for air-gapped
  or strict data-residency workflows.
- **`ollama` mode:** nothing leaves the device — the LLM runs locally.
- The **retriever and verifier are local in both modes.**

Never describe this system as "fully local" or claim "data never leaves the device"
without naming the mode it applies to.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Unix: source .venv/bin/activate

# Install CPU torch first, then the rest:
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp .env.example .env        # then add your GROQ_API_KEY
```

Drop 30–50 arXiv PDFs into `data/pdfs/` (gitignored).

## Usage (filled in as weeks ship)

```bash
# Week 1 — vanilla baseline
python -m src.baseline "What is Self-RAG?"
python -m src.evaluation --pipeline baseline

# Week 2+ — full multi-agent pipeline
python -m src.graph "What is the difference between Self-RAG and CRAG?"

# Week 4 — UI
streamlit run app/streamlit_app.py
```

## Hard constraints

CPU only, < 11 GB active RAM, no fine-tuning, no paid APIs (Groq free tier only),
free/open-source deps, no real PDFs or keys in git. See `prompt.md` §2 and §8.

## Layout

See `prompt.md` §4 for the full tree. Tunables live in `config.py` (the only place
for paths, model names, and thresholds). Prompt templates live in `src/prompts/`.

## Status

The full research pipeline is implemented and tested:

- **Ingestion / retrieval / baseline** — `src/ingestion.py`, `src/retrieval.py`,
  `src/baseline.py`.
- **Multi-agent pipeline** — `src/agents/` (Planner→Retriever→Synthesizer→
  Verifier with the NLI citation verifier and a bounded revise loop). Run it
  with `python -m src.graph "..." --corpus default`.
- **Evaluation harness** — `src/evaluation.py`: per-claim NLI faithfulness,
  baseline-vs-multiagent comparison, and a paired t-test
  (`python -m src.evaluation --compare`).
- **App** — a FastAPI + React/TS prototype under `app/` whose authenticated
  `/api/query` runs the real pipeline (see `app/RUNNING.md`).

To run anything end-to-end you must first drop arXiv PDFs into `data/pdfs/` and
build an index: `python -m src.retrieval --build --corpus default`.

For the honest scope of the larger "production monorepo" (most of `apps/`,
`services/rag-service`, `infrastructure/k8s`, etc. are still scaffolding), see
[`MONOREPO.md`](./MONOREPO.md) → "What runs today".
