"""Research Guide, Viva, Paper Finder, and Knowledge Graph endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.backend import auth
from app.backend import database as db
from app.backend.security.guardrails import check_query

router = APIRouter(prefix="/api/research", tags=["research"])


# ── Research Guide ────────────────────────────────────────────────────────────

class GuideRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    corpus_id: str
    conversation_id: str | None = None
    mode: str = "cloud"
    provider: str = "groq"
    top_k: int = Field(default=8, ge=1, le=20)
    use_react: bool = False  # ReAct multi-step reasoning mode


@router.post("/guide")
def research_guide(
    req: GuideRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Ask the Research Guide agent a question about your corpus."""
    guard = check_query(req.question)
    if guard.blocked:
        raise HTTPException(400, f"Query blocked: {guard.reason}")

    corpus = db.get_corpus(req.corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    # Load conversation history
    history = []
    if req.conversation_id:
        conv = db.get_conversation(req.conversation_id, user["id"])
        if conv:
            history = db.list_messages(req.conversation_id)

    if req.use_react:
        from src.agents.research_guide import run_react_guide
        result = run_react_guide(
            question=req.question,
            corpus_id=req.corpus_id,
            conversation_history=history,
            mode=req.mode,
            provider=req.provider,
        )
    else:
        from src.agents.research_guide import run_research_guide
        result = run_research_guide(
            question=req.question,
            corpus_id=req.corpus_id,
            conversation_history=history,
            mode=req.mode,
            provider=req.provider,
            top_k=req.top_k,
        )

    # Persist to conversation
    if req.conversation_id:
        conv = db.get_conversation(req.conversation_id, user["id"])
        if conv:
            db.add_message(req.conversation_id, "user", req.question)
            db.add_message(req.conversation_id, "assistant", result["answer"],
                           metadata={"latency_ms": result["latency_ms"], "agent": "guide"})
            db.touch_conversation(req.conversation_id)

    return result


@router.post("/gap-analysis")
def gap_analysis(
    user: Annotated[dict, Depends(auth.get_current_user)],
    corpus_id: str = Query(...),
    mode: str = Query("cloud"),
    provider: str = Query("groq"),
):
    """Analyse the corpus for research gaps and improvement opportunities."""
    corpus = db.get_corpus(corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    from src.agents.research_guide import run_gap_analysis
    return run_gap_analysis(corpus_id=corpus_id, mode=mode, provider=provider)


# ── Knowledge Graph ───────────────────────────────────────────────────────────

# In-memory build status per corpus so the UI can poll and watch it grow.
_KG_STATUS: dict[str, str] = {}


@router.post("/knowledge-graph/build")
def build_kg(
    user: Annotated[dict, Depends(auth.get_current_user)],
    corpus_id: str = Query(...),
    mode: str = Query("cloud"),
    provider: str = Query("groq"),
    max_chunks: int = Query(40, ge=1, le=200),
):
    """Kick off a background knowledge-graph build and return immediately.

    Nodes/edges are written to the DB incrementally, so the client polls
    GET /knowledge-graph/{corpus_id} and watches the graph grow live.
    """
    corpus = db.get_corpus(corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    if _KG_STATUS.get(corpus_id) == "building":
        return {"status": "building", "message": "A build is already in progress."}

    import threading
    from src.retrieval import load_vector_store
    from src.knowledge_graph.builder import build_knowledge_graph
    from src.llm_backend import get_backend

    vs = load_vector_store(corpus_id)
    if vs is None:
        raise HTTPException(400, "No index found — upload and index documents first")
    chunks = [
        {"chunk_id": c.chunk_id, "text": c.text, "source": c.source, "page": c.page}
        for c in vs.chunks
    ]
    llm = get_backend(mode, provider)
    _KG_STATUS[corpus_id] = "building"

    def _run():
        try:
            build_knowledge_graph(corpus_id, chunks, llm, max_chunks=max_chunks)
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning("KG build failed: %s", exc)
        finally:
            _KG_STATUS[corpus_id] = "done"

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "building", "message": "Knowledge graph is building in the background."}


@router.get("/knowledge-graph/{corpus_id}")
def get_kg(
    corpus_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Get knowledge graph nodes and edges for a corpus, plus build status."""
    corpus = db.get_corpus(corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    nodes = db.get_kg_nodes(corpus_id)
    edges = db.get_kg_edges(corpus_id)
    return {
        "nodes": nodes, "edges": edges,
        "node_count": len(nodes), "edge_count": len(edges),
        "building": _KG_STATUS.get(corpus_id) == "building",
    }


# ── Viva Agent ────────────────────────────────────────────────────────────────

class VivaSessionCreate(BaseModel):
    corpus_id: str
    difficulty: str = Field(default="masters",
        pattern="^(undergraduate|masters|phd)$")


class VivaQuestionRequest(BaseModel):
    corpus_id: str
    question_type: str = Field(default="depth",
        pattern="^(breadth|depth|defense|novelty|future)$")
    asked_questions: list[str] = []
    session_id: str | None = None
    mode: str = "cloud"
    provider: str = "groq"


class VivaAnswerRequest(BaseModel):
    corpus_id: str
    question: str = Field(..., min_length=5)
    student_answer: str = Field(..., min_length=5)
    session_id: str | None = None
    question_type: str = "depth"
    mode: str = "cloud"
    provider: str = "groq"


@router.post("/viva/sessions", status_code=201)
def create_viva_session(
    req: VivaSessionCreate,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Create a new viva session and return its ID."""
    if not db.get_corpus(req.corpus_id, user["id"]):
        raise HTTPException(404, "Corpus not found")
    return db.create_viva_session(user["id"], req.corpus_id, req.difficulty)


@router.get("/viva/sessions")
def list_viva_sessions(user: Annotated[dict, Depends(auth.get_current_user)]):
    return db.list_viva_sessions(user["id"])


@router.get("/viva/sessions/{session_id}")
def get_viva_session(
    session_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    s = db.get_viva_session(session_id, user["id"])
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.post("/viva/question")
def viva_question(
    req: VivaQuestionRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Generate a viva examination question from the corpus."""
    corpus = db.get_corpus(req.corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    from src.agents.viva_agent import generate_question
    result = generate_question(
        corpus_id=req.corpus_id,
        question_type=req.question_type,
        asked_questions=req.asked_questions,
        mode=req.mode,
        provider=req.provider,
    )

    # Persist question to session if session_id provided
    if req.session_id and not result.get("error"):
        session = db.get_viva_session(req.session_id, user["id"])
        if session:
            qs = session.get("questions", [])
            qs.append({"type": req.question_type, "text": result["question"]})
            db.update_viva_session(req.session_id, user["id"], questions=qs)
            result["session_id"] = req.session_id

    return result


@router.post("/viva/evaluate")
def viva_evaluate(
    req: VivaAnswerRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Evaluate a student's viva answer against the corpus."""
    guard = check_query(req.student_answer)
    if guard.blocked:
        raise HTTPException(400, f"Answer blocked: {guard.reason}")

    corpus = db.get_corpus(req.corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    from src.agents.viva_agent import evaluate_answer
    result = evaluate_answer(
        corpus_id=req.corpus_id,
        question=req.question,
        student_answer=req.student_answer,
        mode=req.mode,
        provider=req.provider,
    )

    # Persist answer + score to session
    if req.session_id:
        session = db.get_viva_session(req.session_id, user["id"])
        if session:
            answers = session.get("answers", [])
            scores = session.get("scores", [])
            answers.append({"question": req.question, "answer": req.student_answer})
            scores.append(result.get("score", 0))
            db.update_viva_session(req.session_id, user["id"],
                                   answers=answers, scores=scores)

    return result


@router.patch("/viva/sessions/{session_id}/complete")
def complete_viva_session(
    session_id: str,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    session = db.update_viva_session(session_id, user["id"], completed=True)
    if not session:
        raise HTTPException(404, "Session not found")
    avg = sum(session["scores"]) / len(session["scores"]) if session["scores"] else 0
    return {**session, "average_score": round(avg, 1)}


# ── Paper Finder ──────────────────────────────────────────────────────────────

class PaperSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    limit: int = Field(default=10, ge=1, le=20)
    expand_query: bool = True
    mode: str = "cloud"
    provider: str = "groq"


class PaperDownloadRequest(BaseModel):
    pdf_url: str = Field(..., min_length=10)
    corpus_id: str
    title: str = ""


@router.post("/papers/search")
async def search_papers(
    req: PaperSearchRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Search Semantic Scholar + arXiv for research papers."""
    from src.paper_search.searcher import search_papers as _search
    from src.llm_backend import get_backend

    llm = None
    if req.expand_query:
        try:
            llm = get_backend(req.mode, req.provider)
        except Exception:
            pass

    results = await _search(
        query=req.query,
        limit=req.limit,
        expand_query=req.expand_query,
        llm_backend=llm,
    )
    return {"papers": results, "count": len(results), "query": req.query}


@router.post("/papers/download")
async def download_paper(
    req: PaperDownloadRequest,
    user: Annotated[dict, Depends(auth.get_current_user)],
):
    """Download a paper PDF and auto-ingest it into a corpus."""
    corpus = db.get_corpus(req.corpus_id, user["id"])
    if not corpus:
        raise HTTPException(404, "Corpus not found")

    from src.paper_search.downloader import download_and_ingest
    result = await download_and_ingest(
        pdf_url=req.pdf_url,
        corpus_id=req.corpus_id,
        title=req.title,
    )

    if result.get("success"):
        db.update_corpus_counts(req.corpus_id, doc_delta=1,
                                chunk_delta=result.get("chunk_count", 0))

    return result
