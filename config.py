"""Central configuration: all paths, model names, and tunable thresholds.

This module is the ONLY place where paths, model identifiers, and magic numbers
live. Agent code must import from here rather than hard-coding values.

The application ships with exactly TWO selectable models:
    * online  — Groq ``meta-llama/llama-4-scout-17b-16e-instruct`` (cloud, fast)
    * offline — Ollama ``phi3:mini`` (fully on-device; nothing leaves the laptop)

Key environment variables (loaded from ``.env`` if present):
    LLM_MODE      "cloud" (default, → Groq) | "local" (→ Ollama, auto-detected)
    LLM_PROVIDER  "groq" (default) | "ollama"
    GROQ_API_KEY  API key for the Groq cloud backend (free tier is sufficient).
    GROQ_MODEL / OLLAMA_MODEL  override the two model identifiers if needed.

(The standalone ``services/ai-service`` library retains broader provider support
for future work; the running research app deliberately exposes only the two
models above.)
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT: Path = Path(__file__).resolve().parent
DATA_DIR: Path = PROJECT_ROOT / "data"
PDF_DIR: Path = DATA_DIR / "pdfs"
EVAL_DIR: Path = DATA_DIR / "eval"
EVAL_SET_PATH: Path = EVAL_DIR / "eval_set.json"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"

# Per-corpus indexes live under data/corpora/<corpus_id>/. This is the single
# path scheme used by BOTH the standalone retrieval CLI and the agentic
# pipeline (planner→retriever) and the FastAPI app, so an index built one way
# is always visible to the other. ``default`` is the corpus the research CLIs
# (``python -m src.retrieval --build``, ``python -m src.graph``) use unless a
# ``--corpus`` id is given.
CORPORA_DIR: Path = DATA_DIR / "corpora"
DEFAULT_CORPUS_ID: str = "default"


def corpus_paths(corpus_id: str = DEFAULT_CORPUS_ID) -> tuple[Path, Path]:
    """Return ``(faiss_index_path, chunk_store_path)`` for a corpus id."""
    base = CORPORA_DIR / corpus_id
    return base / "faiss.index", base / "chunks.pkl"


# Back-compat aliases — the default corpus's paths. Prefer ``corpus_paths()``.
FAISS_INDEX_PATH, CHUNK_STORE_PATH = corpus_paths()
INDEX_DIR: Path = CORPORA_DIR / DEFAULT_CORPUS_ID


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"  # ~80 MB, 384-dim
EMBEDDING_DIM: int = 384
NLI_MODEL: str = "cross-encoder/nli-deberta-v3-base"  # ~180 MB, CPU


# --------------------------------------------------------------------------- #
# LLM backend selection — TWO models only
# LLM_MODE     : "cloud" (default) → Groq | "local" → Ollama
# LLM_PROVIDER : "groq" (default)  | "ollama"
# --------------------------------------------------------------------------- #
LLM_MODE: str = os.getenv("LLM_MODE", "cloud")        # "cloud" | "local"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")  # "groq" | "ollama"


# --------------------------------------------------------------------------- #
# The two models
# --------------------------------------------------------------------------- #

# Online: Groq — Llama 4 Scout (17B active, 16-expert MoE; fast, free tier).
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Offline: Ollama — Phi-3 mini (~2.2 GB Q4; CPU-only, nothing leaves the device).
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "phi3:mini")
# HTTP timeout per Ollama generate call. CPU prompt processing on long grounded
# prompts can exceed 120 s on low-RAM machines, so this is deliberately generous.
OLLAMA_TIMEOUT_S: int = int(os.getenv("OLLAMA_TIMEOUT_S", "480"))


# --------------------------------------------------------------------------- #
# Ingestion / chunking
# --------------------------------------------------------------------------- #
CHUNK_SIZE: int = 512      # characters
CHUNK_OVERLAP: int = 64    # characters


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
TOP_K: int = 5
FAISS_FLAT_MAX_CHUNKS: int = 5_000
RETRIEVAL_RELEVANCE_THRESHOLD: float = 0.5


# --------------------------------------------------------------------------- #
# Verifier
# --------------------------------------------------------------------------- #
CITATION_FAITHFULNESS_THRESHOLD: float = 0.6
MAX_VERIFIER_RETRIES: int = 2


# --------------------------------------------------------------------------- #
# LLM call behaviour
# --------------------------------------------------------------------------- #
DEFAULT_TEMPERATURE: float = 0.0
DEFAULT_MAX_TOKENS: int = 1024
RETRY_BACKOFF_SECONDS: tuple[int, ...] = (1, 2, 4)
MAX_LLM_ATTEMPTS: int = 3


# --------------------------------------------------------------------------- #
# Latency targets (seconds) — used for reporting, not enforcement
# --------------------------------------------------------------------------- #
LATENCY_TARGET_GROQ_S: int = 30
LATENCY_TARGET_OLLAMA_S: int = 90
