"""Pluggable runtime pipeline.

``Pipeline`` is the protocol the FastAPI layer depends on. ``MockPipeline``
implements it with canned, correctly-shaped responses so the frontend is fully
functional before the real LangGraph pipeline (Weeks 1-3) exists. When the real
pipeline is ready, implement the same protocol in ``src/graph.py`` and swap it
in ``main.py`` — the API and frontend do not change.

The mock deliberately includes a lower-faithfulness claim so the UI's
green/amber/red scoring is visible in a demo.
"""

from __future__ import annotations

import time
from typing import Protocol

import config
from app.backend.schemas import (
    CitedChunk,
    ClaimVerification,
    LLMMode,
    ProviderName,
    QueryResponse,
)


class Pipeline(Protocol):
    """Contract the API depends on. The real LangGraph graph will implement this."""

    is_mock: bool

    def answer(
        self, question: str, mode: LLMMode, top_k: int,
        provider: ProviderName | None = None,
    ) -> QueryResponse: ...


# ---------------------------------------------------------------------------
# Fake corpus: four chunks from the Self-RAG / CRAG papers.
# ---------------------------------------------------------------------------
_FAKE_CHUNKS: dict[str, CitedChunk] = {
    "selfrag_p3_c1": CitedChunk(
        chunk_id="selfrag_p3_c1",
        source="asai_2024_self_rag.pdf",
        page=3,
        text=(
            "Self-RAG trains a single LM to adaptively retrieve passages on-demand and to "
            "generate and reflect on retrieved passages and its own generations using special "
            "reflection tokens."
        ),
        score=0.83,
    ),
    "selfrag_p4_c2": CitedChunk(
        chunk_id="selfrag_p4_c2",
        source="asai_2024_self_rag.pdf",
        page=4,
        text=(
            "Reflection tokens signal the need for retrieval and critique whether the output is "
            "supported by and relevant to the retrieved evidence, enabling controllable behavior "
            "at inference time."
        ),
        score=0.79,
    ),
    "crag_p2_c1": CitedChunk(
        chunk_id="crag_p2_c1",
        source="yan_2024_crag.pdf",
        page=2,
        text=(
            "Corrective RAG (CRAG) introduces a lightweight retrieval evaluator that assesses the "
            "quality of retrieved documents and triggers corrective actions such as query "
            "rewriting when retrieval is judged incorrect or ambiguous."
        ),
        score=0.81,
    ),
    "crag_p5_c3": CitedChunk(
        chunk_id="crag_p5_c3",
        source="yan_2024_crag.pdf",
        page=5,
        text=(
            "When retrieval confidence is low, CRAG decomposes and recomposes retrieved knowledge "
            "and can fall back to web search to supplement the corpus."
        ),
        score=0.6,
    ),
}


def _green_amber(threshold: float) -> tuple[float, float]:
    """UI bands: green >= 0.8, amber >= threshold (0.6), else red."""
    return 0.8, threshold


def _backend_label(mode: LLMMode, provider: ProviderName | None) -> str:
    """Human-readable backend label shown in the UI / logs.

    The app exposes only two models: Groq Llama 4 Scout (cloud) and Ollama
    Phi-3 mini (local). Any other provider value falls back to a generic label.
    """
    resolved = provider or ProviderName(config.LLM_PROVIDER)
    if mode == LLMMode.local or resolved == ProviderName.ollama:
        return f"OllamaBackend[{config.OLLAMA_MODEL}]"
    if resolved == ProviderName.groq:
        return f"GroqBackend[{config.GROQ_MODEL}]"
    return f"{resolved.value}Backend"


class MockPipeline:
    """Canned responses with the same shape as the real pipeline output."""

    is_mock: bool = True

    def answer(
        self,
        question: str,
        mode: LLMMode,
        top_k: int,
        provider: ProviderName | None = None,
    ) -> QueryResponse:
        t0 = time.perf_counter()
        q = question.lower()
        resolved_provider = provider or ProviderName(config.LLM_PROVIDER)
        backend_name = _backend_label(mode, provider)

        if "self-rag" in q or "self rag" in q:
            sources = [_FAKE_CHUNKS["selfrag_p3_c1"], _FAKE_CHUNKS["selfrag_p4_c2"]]
            answer = (
                "Self-RAG is a retrieval-augmented framework in which a single language model is "
                "trained to decide when to retrieve passages and to critique its own outputs [1]. "
                "It emits special reflection tokens that mark whether retrieval is needed and "
                "whether a generation is supported by the retrieved evidence, giving controllable "
                "behavior at inference time [2]."
            )
            claims = [
                ClaimVerification(
                    claim_text=(
                        "Self-RAG trains a single LM to adaptively retrieve and reflect on "
                        "passages using reflection tokens."
                    ),
                    cited_chunk_ids=["selfrag_p3_c1"],
                    cited_chunks=[_FAKE_CHUNKS["selfrag_p3_c1"]],
                    faithfulness_score=0.93,
                    verdict=True,
                ),
                ClaimVerification(
                    claim_text=(
                        "Reflection tokens let the model critique whether an output is supported "
                        "by retrieved evidence at inference time."
                    ),
                    cited_chunk_ids=["selfrag_p4_c2"],
                    cited_chunks=[_FAKE_CHUNKS["selfrag_p4_c2"]],
                    faithfulness_score=0.88,
                    verdict=True,
                ),
            ]
            sub_questions = [
                "What is the core mechanism of Self-RAG?",
                "What role do reflection tokens play?",
            ]
        elif "crag" in q or "corrective" in q:
            sources = [_FAKE_CHUNKS["crag_p2_c1"], _FAKE_CHUNKS["crag_p5_c3"]]
            answer = (
                "Corrective RAG (CRAG) adds a lightweight retrieval evaluator that grades the "
                "quality of retrieved documents and triggers corrective actions like query "
                "rewriting when retrieval looks weak [1]. It also recomposes retrieved knowledge "
                "and, in the original paper, can fall back to web search when confidence is low [2]."
            )
            claims = [
                ClaimVerification(
                    claim_text=(
                        "CRAG uses a lightweight retrieval evaluator that triggers query "
                        "rewriting when retrieval quality is low."
                    ),
                    cited_chunk_ids=["crag_p2_c1"],
                    cited_chunks=[_FAKE_CHUNKS["crag_p2_c1"]],
                    faithfulness_score=0.9,
                    verdict=True,
                ),
                ClaimVerification(
                    claim_text="CRAG always improves answer accuracy on every benchmark.",
                    cited_chunk_ids=["crag_p5_c3"],
                    cited_chunks=[_FAKE_CHUNKS["crag_p5_c3"]],
                    faithfulness_score=0.41,  # deliberately unfaithful → red in UI
                    verdict=False,
                ),
            ]
            sub_questions = [
                "What problem does CRAG address?",
                "How does CRAG correct weak retrieval?",
            ]
        else:
            sources = [_FAKE_CHUNKS["selfrag_p3_c1"], _FAKE_CHUNKS["crag_p2_c1"]]
            answer = (
                "[Mock response] The real multi-agent pipeline is not wired yet. Once Weeks 1-3 "
                "are implemented, the Planner, Retriever, Synthesizer, and NLI Verifier will "
                "produce a grounded answer with verified citations for your question [1][2]."
            )
            claims = [
                ClaimVerification(
                    claim_text="This is a mock claim grounded in a sample chunk.",
                    cited_chunk_ids=["selfrag_p3_c1"],
                    cited_chunks=[_FAKE_CHUNKS["selfrag_p3_c1"]],
                    faithfulness_score=0.72,  # amber band
                    verdict=True,
                ),
            ]
            sub_questions = [question]

        overall = round(sum(c.faithfulness_score for c in claims) / len(claims), 3)
        latency = round(time.perf_counter() - t0, 4)
        return QueryResponse(
            question=question,
            answer=answer,
            sub_questions=sub_questions,
            claims=claims,
            sources=sources[:top_k],
            overall_faithfulness=overall,
            mode=mode,
            provider=resolved_provider.value,
            backend_name=backend_name,
            latency_s=latency,
            retries=0,
            is_mock=True,
        )


# The PRODUCTION query path (app/backend/routers/query_router.py -> /api/query)
# runs the REAL agentic graph (src.agents.graph.run). This MockPipeline is the
# legacy demo singleton used by the standalone app/backend/main.py prototype; it
# returns CANNED verdicts and must never be mistaken for real verification.
import logging as _logging
import os as _os

DEMO_MODE = _os.getenv("DEMO_MODE", "true").lower() in ("1", "true", "yes")
get_pipeline: Pipeline = MockPipeline()
if get_pipeline.is_mock:
    _logging.getLogger(__name__).warning(
        "Serving the MOCK demo pipeline (canned verdicts, is_mock=True). Real "
        "NLI verification is served by /api/query (query_router -> graph.run). "
        "Set DEMO_MODE=false and wire the real pipeline before any non-demo use."
    )

GREEN_MIN, AMBER_MIN = _green_amber(config.CITATION_FAITHFULNESS_THRESHOLD)
