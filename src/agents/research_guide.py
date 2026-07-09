"""Research Guide agent — acts as an academic research mentor.

Given a user's question and their uploaded corpus, this agent:
1. Retrieves relevant chunks (same FAISS pipeline as core RAG)
2. Loads the knowledge graph summary
3. Generates a grounded response focused on gaps, improvements, and methodology
   comparison — not just question answering

Used by the Research Guide chat interface (/api/research/guide).
"""

from __future__ import annotations

import logging
import time

import config
from src.llm_backend import get_backend
from src.retrieval import VectorStore, load_vector_store

def _load_store(corpus_id: str) -> VectorStore | None:
    return load_vector_store(corpus_id)

logger = logging.getLogger(__name__)

GUIDE_SYSTEM = """You are an expert academic research guide helping a student understand
and improve their research. You have access to the papers they uploaded.

Your role:
- Ground every claim in the retrieved chunks with inline [N] citations
- Identify gaps, limitations, and open problems from the literature
- Compare methodologies across papers when relevant
- Suggest concrete improvements the student can make to their work
- Point to specific evidence — never make up citations

When asked about improvements:
- Look for methods proposed but not validated on certain datasets
- Look for missing ablation studies or comparisons
- Look for explicitly stated "future work" or limitations sections
- Suggest how techniques from different papers could be combined

Always be specific. "Consider using method X from [3] instead of Y because [3] shows
a 12% improvement on dataset Z" is better than "you could improve your methodology".

If you cannot find evidence for something in the retrieved chunks, say so explicitly.
"""

# ReAct-style multi-turn search prompt
REACT_SYSTEM = """You are a research guide that reasons step-by-step before answering.

You have access to one tool:
  SEARCH(query) — search the corpus for relevant chunks

Reason in this format:
Thought: <what you need to find>
Action: SEARCH(<search query>)
Observation: <results will be provided>
... (repeat Thought/Action/Observation up to 3 times if needed)
Thought: I have enough information now.
Answer: <final grounded answer with [N] citations>

Start with a Thought. Only issue SEARCH actions. Do not fabricate Observations.
"""

GUIDE_PROMPT = """Research context from uploaded papers:

{chunks_text}

Knowledge graph of this research domain:
{kg_summary}

Conversation history:
{history}

Student's question: {question}

Provide a detailed, grounded research guidance response with [N] citations for every claim.
"""

GAP_ANALYSIS_PROMPT = """You are analyzing a research corpus to identify gaps and improvement opportunities.

Knowledge graph:
{kg_summary}

Retrieved sections about gaps and limitations:
{chunks_text}

Identify and list:
1. Methods proposed but not evaluated on [specific dataset types]
2. Claims made without ablation studies
3. Direct comparisons missing from evaluations
4. Open problems explicitly stated by authors
5. Combinations of techniques that haven't been tried

Format each gap as:
- Gap: [description]
  Evidence: [chunk citation]
  Opportunity: [what the student could do]
"""


def run_research_guide(
    question: str,
    corpus_id: str,
    conversation_history: list[dict],
    mode: str = "cloud",
    provider: str = "groq",
    top_k: int = 8,
) -> dict:
    """Run the research guide agent and return a structured response."""
    t0 = time.time()

    llm = get_backend(mode, provider)

    # Load vector store
    vs = _load_store(corpus_id)
    if vs is None:
        return {
            "answer": "No documents have been indexed for this corpus yet. Please upload research PDFs first.",
            "chunks": [],
            "latency_ms": int((time.time() - t0) * 1000),
        }

    # Retrieve more chunks than standard RAG for research guidance
    results = vs.search(question, k=top_k)
    chunks = [
        {
            "chunk_id": r.chunk.chunk_id,
            "text": r.chunk.text,
            "source": r.chunk.source,
            "page": r.chunk.page,
            "score": float(r.score),
            "section": getattr(r.chunk, "section", ""),
        }
        for r in results
    ]

    # Build chunks context with numbered citations
    chunks_text = "\n\n".join(
        f"[{i+1}] Source: {c['source']}, p.{c['page']}\n{c['text'][:600]}"
        for i, c in enumerate(chunks)
    )

    # Load knowledge graph summary
    try:
        from src.knowledge_graph.builder import get_kg_summary
        kg_summary = get_kg_summary(corpus_id)
    except Exception:
        kg_summary = "Knowledge graph not yet built for this corpus."

    # Format conversation history (last 6 turns)
    history_text = ""
    for msg in conversation_history[-6:]:
        role = "Student" if msg.get("role") == "user" else "Guide"
        history_text += f"{role}: {msg.get('content', '')}\n\n"

    # Generate response
    prompt = GUIDE_PROMPT.format(
        chunks_text=chunks_text,
        kg_summary=kg_summary,
        history=history_text or "No prior conversation.",
        question=question,
    )

    try:
        answer = llm.generate(
            f"{GUIDE_SYSTEM}\n\n{prompt}",
            temperature=0.3,
            max_tokens=1500,
        )
    except Exception as e:
        logger.error("Research guide LLM error: %s", e)
        answer = f"I encountered an error generating a response: {e}"

    latency_ms = int((time.time() - t0) * 1000)
    return {
        "answer": answer,
        "chunks": chunks,
        "kg_summary": kg_summary,
        "latency_ms": latency_ms,
    }


def run_react_guide(
    question: str,
    corpus_id: str,
    conversation_history: list[dict],
    mode: str = "cloud",
    provider: str = "groq",
    max_steps: int = 3,
) -> dict:
    """ReAct-style research guide: Think → Search(corpus) → Observe → Answer.

    Runs up to max_steps search iterations before generating the final answer,
    allowing the agent to refine its retrieval based on intermediate findings.
    """
    import re as _re

    t0 = time.time()
    llm = get_backend(mode, provider)
    vs = _load_store(corpus_id)

    if vs is None:
        return {"answer": "No documents indexed — upload research PDFs first.",
                "chunks": [], "latency_ms": 0, "react_trace": []}

    try:
        from src.knowledge_graph.builder import get_kg_summary
        kg_summary = get_kg_summary(corpus_id)
    except Exception:
        kg_summary = ""

    all_chunks: list[dict] = []
    trace: list[dict] = []
    chunk_set: set[str] = set()

    history_text = ""
    for msg in conversation_history[-4:]:
        role = "Student" if msg.get("role") == "user" else "Guide"
        history_text += f"{role}: {msg.get('content', '')}\n"

    # Build initial ReAct prompt
    context = (
        f"{REACT_SYSTEM}\n\n"
        f"Knowledge graph summary:\n{kg_summary}\n\n"
        f"Conversation history:\n{history_text or 'None.'}\n\n"
        f"Student question: {question}\n\n"
    )

    partial = context
    for step in range(max_steps + 1):
        raw = llm.generate(partial, temperature=0.2, max_tokens=600)

        # Check if model issued a SEARCH action
        search_match = _re.search(r"Action:\s*SEARCH\((.+?)\)", raw, _re.IGNORECASE)
        if search_match:
            query = search_match.group(1).strip().strip('"\'')
            results = vs.search(query, k=5)
            obs_chunks = [
                {"chunk_id": r.chunk.chunk_id, "text": r.chunk.text,
                 "source": r.chunk.source, "page": r.chunk.page, "score": float(r.score)}
                for r in results
            ]
            # Deduplicate
            for c in obs_chunks:
                if c["chunk_id"] not in chunk_set:
                    chunk_set.add(c["chunk_id"])
                    all_chunks.append(c)

            obs_text = "\n".join(
                f"[{i+1}] {c['source']} p.{c['page']}: {c['text'][:300]}"
                for i, c in enumerate(obs_chunks)
            )
            trace.append({"step": step + 1, "action": query, "obs_count": len(obs_chunks)})
            partial = partial + raw + f"\nObservation: {obs_text}\n"
        else:
            # Model gave final Answer (or exhausted steps)
            answer_match = _re.search(r"Answer:\s*(.+)", raw, _re.DOTALL | _re.IGNORECASE)
            final_answer = answer_match.group(1).strip() if answer_match else raw.strip()
            return {
                "answer": final_answer,
                "chunks": all_chunks,
                "kg_summary": kg_summary,
                "react_trace": trace,
                "latency_ms": int((time.time() - t0) * 1000),
            }

    # Fallback if loop exhausted without final Answer
    return {
        "answer": partial.split("Answer:")[-1].strip() if "Answer:" in partial else partial[-500:],
        "chunks": all_chunks,
        "kg_summary": kg_summary,
        "react_trace": trace,
        "latency_ms": int((time.time() - t0) * 1000),
    }


def run_gap_analysis(
    corpus_id: str,
    mode: str = "cloud",
    provider: str = "groq",
    top_k: int = 10,
) -> dict:
    """Analyse the corpus knowledge graph for research gaps."""
    t0 = time.time()
    llm = get_backend(mode, provider)

    vs = _load_store(corpus_id)
    if vs is None:
        return {"gaps": [], "error": "No index found for this corpus."}

    results = vs.search("limitations future work gaps not evaluated", k=top_k)
    chunks_text = "\n\n".join(
        f"[{i+1}] {r.chunk.source} p.{r.chunk.page}: {r.chunk.text[:500]}"
        for i, r in enumerate(results)
    )

    from src.knowledge_graph.builder import get_kg_summary
    kg_summary = get_kg_summary(corpus_id)

    prompt = GAP_ANALYSIS_PROMPT.format(kg_summary=kg_summary, chunks_text=chunks_text)

    try:
        answer = llm.generate(prompt, temperature=0.2, max_tokens=1500)
    except Exception as e:
        answer = f"Gap analysis failed: {e}"

    return {
        "analysis": answer,
        "chunks": [
            {"chunk_id": r.chunk.chunk_id, "source": r.chunk.source,
             "page": r.chunk.page, "score": float(r.score)}
            for r in results
        ],
        "latency_ms": int((time.time() - t0) * 1000),
    }
