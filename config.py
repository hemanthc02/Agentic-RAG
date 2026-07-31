"""Central configuration: all paths, model names, and tunable thresholds.

This module is the ONLY place where paths, model identifiers, and magic numbers
live. Agent code must import from here rather than hard-coding values.

The application ships with exactly TWO selectable models:
    * online  — Groq (cloud). In cloud mode the question and the retrieved chunk
      excerpts are sent to Groq's US API over HTTPS.
    * offline — Ollama (fully on-device). ONLY in local/offline mode does nothing
      leave the laptop; the "private, on-device" guarantee is mode-specific.

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
# Where uploads, the SQLite DB and FAISS indexes are written. Defaults to
# ``<project>/data`` for local runs. On a host where the app folder is
# read-only or wiped on redeploy (e.g. Azure App Service, whose ``/home`` is the
# persistent, writable area), set DATA_DIR=/home/data so user data survives
# restarts and redeploys. All sub-paths below derive from this.
_DATA_DIR_ENV = os.getenv("DATA_DIR")
DATA_DIR: Path = Path(_DATA_DIR_ENV).expanduser() if _DATA_DIR_ENV else PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
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

# Online provider selector: "anthropic" (Claude) or "groq" (Llama). Set in .env.
# Online: Groq — default matches .env (Llama 3.3 70B versatile). Override via GROQ_MODEL.
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Online: Anthropic — Claude. Requires ANTHROPIC_API_KEY. Model overridable via ANTHROPIC_MODEL.
ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

# Offline: Ollama — default matches .env (phi4-mini; CPU-only, nothing leaves the device).
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "phi4-mini")
# HTTP timeout per Ollama generate call. CPU prompt processing on long grounded
# prompts can exceed 120 s on low-RAM machines, so this is deliberately generous.
OLLAMA_TIMEOUT_S: int = int(os.getenv("OLLAMA_TIMEOUT_S", "480"))


# --------------------------------------------------------------------------- #
# Backend selection — local (default) vs Azure managed services
# Each is independent and defaults to the local implementation, so the app runs
# unchanged on a laptop. On Azure, flip the ones you use via environment vars.
#   STORAGE_BACKEND  "local" (disk)   | "azure_blob"   — where uploaded PDFs live
#   DB_BACKEND       "sqlite" (file)  | "azure_sql"    — users/corpora/history
#   SEARCH_BACKEND   "faiss" (file)   | "azure_search" — the vector index
# --------------------------------------------------------------------------- #
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local").lower()
DB_BACKEND: str = os.getenv("DB_BACKEND", "sqlite").lower()
SEARCH_BACKEND: str = os.getenv("SEARCH_BACKEND", "faiss").lower()

# --- Azure Blob Storage (STORAGE_BACKEND=azure_blob) ---
AZURE_STORAGE_CONNECTION_STRING: str | None = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
AZURE_BLOB_CONTAINER: str = os.getenv("AZURE_BLOB_CONTAINER", "veritasrag-pdfs")

# --- Azure SQL Database (DB_BACKEND=azure_sql) ---
# A full ODBC connection string, e.g.
#   Driver={ODBC Driver 18 for SQL Server};Server=tcp:<srv>.database.windows.net,1433;
#   Database=<db>;Uid=<user>;Pwd=<pwd>;Encrypt=yes;TrustServerCertificate=no;
AZURE_SQL_CONNECTION_STRING: str | None = os.getenv("AZURE_SQL_CONNECTION_STRING")

# --- Azure AI Search (SEARCH_BACKEND=azure_search) ---
# Free tier = 3 indexes / 50 MB, so ONE shared index filtered by corpus_id.
AZURE_SEARCH_ENDPOINT: str | None = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY: str | None = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "veritasrag-chunks")


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
# If the best cosine score for a question is below this floor, nothing in the
# corpus is even loosely related — the pipeline is skipped with an honest
# "not in your PDFs" answer instead of letting the LLM hallucinate.
# (Measured on the reference corpus: real questions score 0.49+, greetings
# and off-topic questions 0.16-0.40.)
OFFTOPIC_SCORE_FLOOR: float = float(os.getenv("OFFTOPIC_SCORE_FLOOR", "0.35"))


# --------------------------------------------------------------------------- #
# Verifier
# --------------------------------------------------------------------------- #
CITATION_FAITHFULNESS_THRESHOLD: float = 0.6
# Revision loop budget. Each revision re-runs synthesis (an LLM call) AND a full
# NLI verification pass, so on a CPU host (e.g. Azure App Service B2) this is the
# biggest latency lever. Lower it (e.g. 0 or 1) on slow hosts to stay under the
# platform request timeout.
MAX_VERIFIER_RETRIES: int = int(os.getenv("MAX_VERIFIER_RETRIES", "2"))
# NLI premise windows scored per claim. Fewer windows = faster CPU verification.
NLI_MAX_WINDOWS: int = int(os.getenv("NLI_MAX_WINDOWS", "6"))
# Citation repair (when a cited chunk fails, look for a better one) checks at
# most this many alternative chunks, and stops early once one supports the
# claim. Bounds CPU-side NLI work so verification stays fast.
MAX_REPAIR_ALTERNATIVES: int = int(os.getenv("MAX_REPAIR_ALTERNATIVES", "2"))
# An answer is only "verified" if its cited claims pass AND uncited sentences do
# not dominate. Without this, an answer made mostly of uncited sentences (which
# are excluded from the faithfulness mean) could be flagged verified=True with a
# high score — gaming the very metric the verifier exists to protect. The cited
# fraction must be at least this high for the answer to be considered verified.
MIN_CITED_RATIO: float = float(os.getenv("MIN_CITED_RATIO", "0.5"))


# --------------------------------------------------------------------------- #
# LLM call behaviour
# --------------------------------------------------------------------------- #
DEFAULT_TEMPERATURE: float = 0.0
DEFAULT_MAX_TOKENS: int = 1024
RETRY_BACKOFF_SECONDS: tuple[int, ...] = (1, 2, 4)
MAX_LLM_ATTEMPTS: int = 3

# --------------------------------------------------------------------------- #
# Offline (local model) speed optimisation
# The local model runs on a CPU, so latency is dominated by (a) prompt length,
# (b) tokens generated, and (c) the number of synthesizer revision passes.
# These tighter limits are used ONLY in offline mode to cut answer time
# roughly in half with minimal quality loss.
# --------------------------------------------------------------------------- #
OFFLINE_TOP_K: int = int(os.getenv("OFFLINE_TOP_K", "3"))          # fewer chunks -> shorter prompt
OFFLINE_MAX_TOKENS: int = int(os.getenv("OFFLINE_MAX_TOKENS", "512"))  # shorter answer -> faster
OFFLINE_MAX_REVISIONS: int = int(os.getenv("OFFLINE_MAX_REVISIONS", "1"))  # at most 1 rewrite


# --------------------------------------------------------------------------- #
# Latency targets (seconds) — used for reporting, not enforcement
# --------------------------------------------------------------------------- #
LATENCY_TARGET_GROQ_S: int = 30
LATENCY_TARGET_OLLAMA_S: int = 90
