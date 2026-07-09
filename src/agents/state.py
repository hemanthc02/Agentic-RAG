"""Shared state type for the LangGraph pipeline."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict):
    # ---- inputs ----
    question: str
    corpus_id: str
    mode: str         # "cloud" | "local"
    provider: str     # "groq" | "gemini" | "ollama" | ...
    top_k: int

    # ---- planner output ----
    sub_questions: list[str]

    # ---- retriever output ----
    chunks: list[dict]          # serialised CitedChunk dicts
    retrieval_attempts: int

    # ---- synthesizer output ----
    answer: str

    # ---- verifier output ----
    claims: list[dict]          # serialised ClaimVerification dicts
    overall_faithfulness: float
    revision_count: int
    verified: bool

    # ---- meta ----
    latency_ms: int
    stage_log: list[dict]       # [{stage, latency_ms, ...extra}]
    error: str | None
