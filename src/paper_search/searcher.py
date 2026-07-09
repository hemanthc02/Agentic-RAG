"""Research paper search — Semantic Scholar + arXiv (both free, no API key).

Uses the LLM (if available) only for query expansion to improve recall.
All search APIs are free and require no authentication.
"""

from __future__ import annotations

import logging
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
ARXIV_API = "http://export.arxiv.org/api/query"

_HEADERS = {
    "User-Agent": "ResearchRAG/1.0 (academic research tool; contact: research@example.com)"
}


async def search_semantic_scholar(query: str, limit: int = 10) -> list[dict]:
    """Search Semantic Scholar. Returns list of paper dicts."""
    params = {
        "query": query,
        "limit": min(limit, 10),
        "fields": "title,authors,year,abstract,externalIds,openAccessPdf,citationCount,venue",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            r = await client.get(f"{SEMANTIC_SCHOLAR_API}/paper/search", params=params)
            r.raise_for_status()
            data = r.json()
            papers = []
            for p in data.get("data", []):
                pdf_url = None
                if p.get("openAccessPdf"):
                    pdf_url = p["openAccessPdf"].get("url")
                papers.append({
                    "title": p.get("title", ""),
                    "authors": [a["name"] for a in p.get("authors", [])[:4]],
                    "year": p.get("year"),
                    "abstract": (p.get("abstract") or "")[:500],
                    "citations": p.get("citationCount", 0),
                    "venue": p.get("venue", ""),
                    "pdf_url": pdf_url,
                    "source": "semantic_scholar",
                    "external_ids": p.get("externalIds", {}),
                })
            return papers
    except Exception as e:
        logger.warning("Semantic Scholar search failed: %s", e)
        return []


async def search_arxiv(query: str, limit: int = 10) -> list[dict]:
    """Search arXiv. Returns list of paper dicts with direct PDF links."""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(limit, 10),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            r = await client.get(ARXIV_API, params=params)
            r.raise_for_status()
            # Parse Atom XML
            papers = _parse_arxiv_atom(r.text)
            return papers
    except Exception as e:
        logger.warning("arXiv search failed: %s", e)
        return []


def _parse_arxiv_atom(xml_text: str) -> list[dict]:
    import xml.etree.ElementTree as ET

    ns = {"atom": "http://www.w3.org/2005/Atom",
          "arxiv": "http://arxiv.org/schemas/atom"}
    papers = []
    try:
        root = ET.fromstring(xml_text)
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            authors = [
                a.find("atom:name", ns).text
                for a in entry.findall("atom:author", ns)
                if a.find("atom:name", ns) is not None
            ]
            # Find PDF link
            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "").replace("http://", "https://")
                    if not pdf_url.endswith(".pdf"):
                        pdf_url += ".pdf"
                    break

            arxiv_id_el = entry.find("atom:id", ns)
            arxiv_id = ""
            if arxiv_id_el is not None:
                arxiv_id = arxiv_id_el.text.split("/abs/")[-1] if arxiv_id_el.text else ""

            year = None
            if published_el is not None and published_el.text:
                year = int(published_el.text[:4])

            papers.append({
                "title": (title_el.text or "").strip() if title_el is not None else "",
                "authors": authors[:4],
                "year": year,
                "abstract": (summary_el.text or "").strip()[:500] if summary_el is not None else "",
                "citations": 0,
                "venue": "arXiv",
                "pdf_url": pdf_url,
                "source": "arxiv",
                "external_ids": {"ArXiv": arxiv_id},
            })
    except Exception as e:
        logger.warning("arXiv XML parse error: %s", e)
    return papers


async def search_papers(query: str, limit: int = 10,
                        expand_query: bool = False,
                        llm_backend=None) -> list[dict]:
    """Search both Semantic Scholar and arXiv, merge and deduplicate results.

    If expand_query=True and llm_backend is provided, uses LLM to generate
    better search keywords before searching.
    """
    search_query = query
    if expand_query and llm_backend:
        try:
            expansion = llm_backend.generate(
                f"Convert this research idea into 5 specific academic search keywords "
                f"for finding related papers. Return only the keywords separated by spaces, "
                f"no explanation:\n\n{query}",
                temperature=0.0,
                max_tokens=80,
            )
            search_query = expansion.strip()
            logger.info("Expanded query: '%s' -> '%s'", query, search_query)
        except Exception:
            pass  # Fall back to original query

    per_source = max(limit, 8)
    ss_results, arxiv_results = await _parallel_search(search_query, per_source)

    # Merge and deduplicate by title similarity
    all_papers = ss_results + arxiv_results
    seen_titles: set[str] = set()
    merged = []
    for p in all_papers:
        title_key = _normalize_title(p["title"])
        if title_key not in seen_titles and p["title"]:
            seen_titles.add(title_key)
            merged.append(p)

    # Sort: prefer papers with PDFs, then by citation count, then by year
    merged.sort(key=lambda p: (
        0 if p.get("pdf_url") else 1,
        -(p.get("citations") or 0),
        -(p.get("year") or 0),
    ))

    return merged[:limit]


async def _parallel_search(query: str, limit: int) -> tuple[list[dict], list[dict]]:
    import asyncio
    results = await asyncio.gather(
        search_semantic_scholar(query, limit),
        search_arxiv(query, limit),
        return_exceptions=True,
    )
    ss = results[0] if not isinstance(results[0], Exception) else []
    arxiv = results[1] if not isinstance(results[1], Exception) else []
    return ss, arxiv


def _normalize_title(title: str) -> str:
    import re
    return re.sub(r"\W+", " ", title.lower()).strip()
