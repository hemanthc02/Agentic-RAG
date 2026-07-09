"""Pydantic v2 request/response models for the FastAPI backend.

Wire contract between the FastAPI backend and the React frontend.
Shared primitives (LLMMode, ProviderName, CitedChunk) are imported from
``common.types`` — the single definition across the whole monorepo.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pydantic import BaseModel, Field  # noqa: E402

from common.types import CitedChunk, LLMMode, ProviderName  # noqa: E402

# Re-export so pipeline.py / main.py can do ``from app.backend.schemas import LLMMode``
__all__ = [
    "LLMMode",
    "ProviderName",
    "CitedChunk",
    "ClaimVerification",
    "QueryRequest",
    "QueryResponse",
    "IngestResponse",
    "ConfigResponse",
    "HealthResponse",
]


class ClaimVerification(BaseModel):
    """One synthesized claim plus its NLI faithfulness verdict."""

    claim_text: str
    cited_chunk_ids: list[str]
    cited_chunks: list[CitedChunk]
    faithfulness_score: float = Field(
        ..., ge=0.0, le=1.0, description="NLI entailment probability vs cited chunks"
    )
    verdict: bool = Field(..., description="score >= CITATION_FAITHFULNESS_THRESHOLD")


class QueryRequest(BaseModel):
    """Research-stack query — lighter than the production contract (no corpus_id)."""

    question: str = Field(..., min_length=3)
    mode: LLMMode = LLMMode.cloud
    provider: ProviderName | None = None  # None → use LLM_PROVIDER from config
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    question: str
    answer: str = Field(..., description="Grounded answer with inline [1][2] citations")
    sub_questions: list[str]
    claims: list[ClaimVerification]
    sources: list[CitedChunk] = Field(..., description="All chunks retrieved for the answer")
    overall_faithfulness: float = Field(..., ge=0.0, le=1.0)
    mode: LLMMode
    provider: str
    backend_name: str
    latency_s: float
    retries: int = Field(..., description="Verifier-triggered synthesizer retries used")
    is_mock: bool = Field(..., description="True while the real pipeline is not yet wired")


class IngestResponse(BaseModel):
    indexed_documents: int
    indexed_chunks: int
    message: str
    is_mock: bool


class ConfigResponse(BaseModel):
    """Non-secret config surfaced to the UI (thresholds, models, modes)."""

    default_mode: LLMMode
    available_modes: list[LLMMode]
    default_provider: ProviderName
    available_providers: list[ProviderName]
    faithfulness_threshold: float
    retrieval_relevance_threshold: float
    max_verifier_retries: int
    embedding_model: str
    nli_model: str
    groq_model: str
    ollama_model: str
    score_green_min: float
    score_amber_min: float
    is_mock: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    is_mock: bool
