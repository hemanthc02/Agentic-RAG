"""Canonical API contracts (single source of truth for wire format).

These Pydantic v2 models define the wire format between ``apps/api`` and
``apps/web``. TypeScript types can be generated from these (e.g. via
``datamodel-code-generator`` / ``pydantic2ts``) so the frontend and backend
cannot drift. Mirrors ``documentcreation/api-design.md``.

Shared primitives (LLMMode, ProviderName, CitedChunk) live in
``common/types.py`` — imported and re-exported here so this file remains the
single import point for consumers.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make repo root importable when this file is run directly or loaded via
# sys.path (the packages/shared-types dir has a hyphen so it is not itself a
# valid Python package name).
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pydantic import BaseModel, Field  # noqa: E402

from common.types import CitedChunk, LLMMode, ProviderName  # noqa: E402

# Re-export so callers only need to import from this module.
__all__ = [
    "LLMMode",
    "ProviderName",
    "CitedChunk",
    "Claim",
    "QueryRequest",
    "QueryResponse",
]


class Claim(BaseModel):
    """One synthesized claim with its NLI-grounded faithfulness verdict."""

    claim_text: str
    cited_chunk_ids: list[str]
    cited_chunks: list[CitedChunk]
    supportedness_score: float = Field(ge=0.0, le=1.0)
    reliance_flag: bool | None = None  # H2: counterfactual reliance probe
    verdict: bool


class QueryRequest(BaseModel):
    """Production API request — richer than the research-stack prototype."""

    question: str = Field(min_length=3)
    corpus_id: str
    mode: LLMMode = LLMMode.cloud
    provider: ProviderName | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    stream: bool = True


class QueryResponse(BaseModel):
    """Production API response."""

    id: str
    question: str
    answer: str
    sub_questions: list[str]
    claims: list[Claim]
    sources: list[CitedChunk]
    overall_supportedness: float = Field(ge=0.0, le=1.0)
    mode: LLMMode
    provider: str
    model: str
    latency_ms: int
    retries: int
