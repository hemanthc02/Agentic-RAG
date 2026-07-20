"""Knowledge graph builder — extracts entities and relations from corpus chunks.

Uses the configured LLM to extract structured (entity, type, description) nodes
and (subject, relation, object) triples from each chunk, then persists them to
the SQLite knowledge_graph_nodes / knowledge_graph_edges tables.
"""

from __future__ import annotations

import logging

import config
from app.backend import database as db
from src.json_utils import extract_json

logger = logging.getLogger(__name__)

# One combined call per chunk (entities + relations) — halves the LLM calls and
# keeps subjects/objects consistent with the extracted entity names.
EXTRACT_PROMPT = """Extract a knowledge graph from this research-paper text.

Text:
{text}

Return ONLY a JSON object (no markdown, no prose) with this exact shape:
{{
  "entities": [
    {{"entity": "name", "type": "Method|Dataset|Metric|Model|Author|Finding|Limitation|Concept", "description": "one short sentence"}}
  ],
  "relations": [
    {{"subject": "entity name", "relation": "short verb phrase", "object": "entity name"}}
  ]
}}

Rules:
- Only entities/relations explicitly supported by the text.
- Max 8 entities, max 10 relations. Descriptions under 100 characters.
- Every relation's subject and object MUST be one of the listed entities.
- Output valid JSON only. Start with {{ and end with }}.
"""


def _kg_backend(llm_backend):
    """Prefer a fast model for the many small extraction calls. If the app is
    configured for Anthropic, use Haiku (fast + cheap) regardless of the main
    pipeline model; otherwise reuse the provided backend."""
    try:
        if config.LLM_PROVIDER.lower() == "anthropic" and config.ANTHROPIC_API_KEY:
            from src.llm_backend import AnthropicBackend
            return AnthropicBackend(model="claude-haiku-4-5-20251001")
    except Exception:
        pass
    return llm_backend


def build_knowledge_graph(corpus_id: str, chunks: list[dict],
                          llm_backend, max_chunks: int = 50) -> dict:
    """Extract entities and relations from corpus chunks and persist to DB.

    Processes up to max_chunks to avoid excessive LLM calls. For large corpora
    it samples every Nth chunk to spread coverage. One LLM call per chunk.
    """
    if not chunks:
        return {"nodes": 0, "edges": 0}

    backend = _kg_backend(llm_backend)
    step = max(1, len(chunks) // max_chunks)
    sampled = chunks[::step][:max_chunks]

    total_nodes = 0
    total_edges = 0
    failed = 0

    for chunk in sampled:
        text = chunk.get("text", "") if isinstance(chunk, dict) else getattr(chunk, "text", "")
        chunk_id = chunk.get("chunk_id", "") if isinstance(chunk, dict) else getattr(chunk, "chunk_id", "")
        if len(text) < 100:
            continue

        try:
            raw = backend.generate(
                EXTRACT_PROMPT.format(text=text[:1500]),
                temperature=0.0,
                max_tokens=1500,  # enough headroom so JSON is never truncated
            )
            data = extract_json(raw)
            entities = data.get("entities", []) if isinstance(data, dict) else []
            relations = data.get("relations", []) if isinstance(data, dict) else []
        except Exception as e:
            failed += 1
            logger.warning("KG extraction failed for chunk %s: %s", chunk_id, e)
            continue

        node_ids: dict[str, str] = {}
        for ent in entities:
            name = (ent.get("entity") or "").strip()
            etype = (ent.get("type") or "Concept").strip()
            desc = (ent.get("description") or "").strip()
            if name:
                nid = db.upsert_kg_node(corpus_id, name, etype, desc, chunk_id)
                node_ids[name] = nid
                total_nodes += 1

        for rel in relations:
            subj = (rel.get("subject") or "").strip()
            obj = (rel.get("object") or "").strip()
            relation = (rel.get("relation") or "").strip()
            if subj in node_ids and obj in node_ids and relation:
                db.upsert_kg_edge(corpus_id, node_ids[subj], node_ids[obj], relation, chunk_id)
                total_edges += 1

    logger.info("KG built for corpus %s: %d nodes, %d edges (%d chunks failed)",
                corpus_id, total_nodes, total_edges, failed)
    return {"nodes": total_nodes, "edges": total_edges}


def get_kg_summary(corpus_id: str) -> str:
    """Return a compact text summary of the knowledge graph for LLM prompts."""
    nodes = db.get_kg_nodes(corpus_id)
    edges = db.get_kg_edges(corpus_id)

    if not nodes:
        return "No knowledge graph available for this corpus."

    by_type: dict[str, list[str]] = {}
    for n in nodes:
        by_type.setdefault(n["entity_type"], []).append(n["entity"])

    lines = ["Knowledge graph summary:"]
    for etype, ents in sorted(by_type.items()):
        lines.append(f"  {etype}: {', '.join(ents[:10])}" + (" ..." if len(ents) > 10 else ""))

    if edges:
        lines.append(f"\nKey relationships ({min(len(edges), 20)} shown):")
        for e in edges[:20]:
            lines.append(f"  {e['source_entity']} --[{e['relation']}]--> {e['target_entity']}")

    return "\n".join(lines)
