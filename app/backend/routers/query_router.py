"""Query endpoint: run the agentic RAG pipeline."""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.backend import auth, cache as cache_mod
from app.backend import database as db
from app.backend.security.guardrails import check_query

router = APIRouter(prefix="/api", tags=["query"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3)
    corpus_id: str
    mode: str = "cloud"        # "cloud" | "local"
    provider: str = "groq"     # "groq" | "ollama"
    top_k: int = Field(default=5, ge=1, le=20)
    use_cache: bool = True
    conversation_id: str | None = None  # attach to a persistent conversation


@router.post("/query")
def query(
    req: QueryRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Run the agentic RAG pipeline (Planner→Retriever→Synthesizer→Verifier)."""
    # Security: check for prompt injection / policy violations
    guard = check_query(req.question)
    if guard.blocked:
        raise HTTPException(400, f"Query blocked: {guard.reason}")

    corpus = db.get_corpus(req.corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    # Check cache
    if req.use_cache:
        cached = cache_mod.get(req.question, req.corpus_id, req.mode, req.provider, req.top_k)
        if cached:
            cached["is_cached"] = True
            return cached

    # Run pipeline
    from src.agents.graph import run as run_pipeline
    state = run_pipeline(
        question=req.question,
        corpus_id=req.corpus_id,
        mode=req.mode,
        provider=req.provider,
        top_k=req.top_k,
    )

    response = {
        "question": req.question,
        "answer": state.get("answer", ""),
        "sub_questions": state.get("sub_questions", []),
        "claims": state.get("claims", []),
        "sources": state.get("chunks", []),
        "overall_faithfulness": state.get("overall_faithfulness", 0.0),
        "mode": req.mode,
        "provider": req.provider,
        "latency_ms": state.get("latency_ms", 0),
        "retries": state.get("revision_count", 0),
        "stage_log": state.get("stage_log", []),
        "is_cached": False,
        "error": state.get("error"),
    }

    # Persist query
    saved = db.save_query(
        user_id=user["id"],
        corpus_id=req.corpus_id,
        question=req.question,
        answer=response["answer"],
        mode=req.mode,
        provider=req.provider,
        latency_ms=response["latency_ms"],
        overall_faithfulness=response["overall_faithfulness"],
        sub_questions=response["sub_questions"],
        claims=response["claims"],
        stage_log=response["stage_log"],
    )

    # Attach to conversation if provided
    if req.conversation_id:
        conv = db.get_conversation(req.conversation_id, user["id"])
        if conv:
            db.add_message(req.conversation_id, "user", req.question)
            db.add_message(
                req.conversation_id, "assistant", response["answer"],
                query_id=saved["id"],
                metadata={
                    "overall_faithfulness": response["overall_faithfulness"],
                    "latency_ms": response["latency_ms"],
                    "sub_questions": response["sub_questions"],
                },
            )
            db.touch_conversation(req.conversation_id)

    if req.use_cache and not state.get("error"):
        cache_mod.put(req.question, req.corpus_id, req.mode, req.provider, req.top_k, response)

    return {**response, "query_id": saved["id"]}


@router.get("/query/history")
def history(
    user: Annotated[dict, Depends(auth.get_current_user)],
    limit: int = 20,
):
    return db.list_queries(user["id"], limit=min(limit, 100))
