"""Knowledge graph builder — extracts entities and relations from corpus chunks.

Uses the configured LLM to extract structured (entity, type, description) nodes
and (subject, relation, object) triples from each chunk, then persists them to
the SQLite knowledge_graph_nodes / knowledge_graph_edges tables.
"""

from __future__ import annotations

import json
import logging

import config
from app.backend import database as db

logger = logging.getLogger(__name__)

ENTITY_PROMPT = """You are a research knowledge extraction system.
Extract entities from the following text chunk from a research paper.

Text:
{text}

Return a JSON object with this exact structure:
{{
  "entities": [
    {{"entity": "name", "type": "Method|Dataset|Metric|Model|Author|Finding|Limitation|Concept", "description": "one sentence"}}
  ]
}}

Rules:
- Only extract entities explicitly mentioned in the text
- Limit to 8 entities max
- Keep descriptions under 100 characters
- Return valid JSON only, no markdown
"""

RELATION_PROMPT = """You are a research knowledge extraction system.
Extract relationships between entities from the following text chunk.

Text:
{text}

Known entities from this text: {entities}

Return a JSON object:
{{
  "relations": [
    {{"subject": "entity name", "relation": "verb phrase", "object": "entity name"}}
  ]
}}

Rules:
- Only use entities from the known list
- Relation should be a short verb phrase (e.g., "improves", "uses", "outperforms", "is evaluated on")
- Limit to 10 relations max
- Return valid JSON only, no markdown
"""


def build_knowledge_graph(corpus_id: str, chunks: list[dict],
                          llm_backend, max_chunks: int = 50) -> dict:
    """Extract entities and relations from corpus chunks and persist to DB.

    Processes up to max_chunks to avoid excessive LLM calls. For large corpora
    it samples every Nth chunk to spread coverage.
    """
    if not chunks:
        return {"nodes": 0, "edges": 0}

    # Sample evenly if corpus is large
    step = max(1, len(chunks) // max_chunks)
    sampled = chunks[::step][:max_chunks]

    total_nodes = 0
    total_edges = 0

    for chunk in sampled:
        text = chunk.get("text", "") if isinstance(chunk, dict) else getattr(chunk, "text", "")
        chunk_id = chunk.get("chunk_id", "") if isinstance(chunk, dict) else getattr(chunk, "chunk_id", "")

        if len(text) < 100:
            continue

        # Extract entities
        try:
            raw = llm_backend.generate(
                ENTITY_PROMPT.format(text=text[:1500]),
                temperature=0.0,
                max_tokens=512,
            )
            data = _parse_json(raw)
            entities = data.get("entities", [])
        except Exception as e:
            logger.warning("Entity extraction failed for chunk %s: %s", chunk_id, e)
            continue

        if not entities:
            continue

        # Persist nodes
        node_ids: dict[str, str] = {}
        for ent in entities:
            name = ent.get("entity", "").strip()
            etype = ent.get("type", "Concept").strip()
            desc = ent.get("description", "").strip()
            if name:
                nid = db.upsert_kg_node(corpus_id, name, etype, desc, chunk_id)
                node_ids[name] = nid
                total_nodes += 1

        # Extract relations
        try:
            raw2 = llm_backend.generate(
                RELATION_PROMPT.format(
                    text=text[:1500],
                    entities=", ".join(node_ids.keys()),
                ),
                temperature=0.0,
                max_tokens=512,
            )
            data2 = _parse_json(raw2)
            relations = data2.get("relations", [])
        except Exception as e:
            logger.warning("Relation extraction failed for chunk %s: %s", chunk_id, e)
            relations = []

        for rel in relations:
            subj = rel.get("subject", "").strip()
            obj = rel.get("object", "").strip()
            relation = rel.get("relation", "").strip()
            if subj in node_ids and obj in node_ids and relation:
                db.upsert_kg_edge(corpus_id, node_ids[subj], node_ids[obj], relation, chunk_id)
                total_edges += 1

    logger.info("KG built for corpus %s: %d nodes, %d edges", corpus_id, total_nodes, total_edges)
    return {"nodes": total_nodes, "edges": total_edges}


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


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
