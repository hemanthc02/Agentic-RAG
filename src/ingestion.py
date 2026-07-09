"""PDF ingestion with hierarchical semantic chunking.

Chunking strategy (best-practice hybrid)
-----------------------------------------
1. Load PDF page-by-page with PyMuPDF (preserves page numbers).
2. Detect section headers (ALL-CAPS lines, numbered headings, "Title:" style)
   and tag subsequent text with that section label.
3. Split page text into sentences using a regex splitter.
4. Greedily merge sentences until chunk reaches TARGET_CHARS (~2048 chars
   ≈ 512 tokens for typical text). Never split a sentence mid-way.
5. Add OVERLAP_CHARS (~256 chars) tail from previous chunk for context
   continuity across chunk boundaries.
6. Store rich metadata: source filename, page, section header, char offsets,
   and a stable chunk_id (MD5 of source+page+offset).

Each Chunk carries: chunk_id, text, source, page, section, char_start, char_end.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from pydantic import BaseModel, Field

import config

TARGET_CHARS: int = 2_048   # ~512 tokens
OVERLAP_CHARS: int = 256    # tail of prev chunk prepended to next


class Chunk(BaseModel):
    """A retrievable unit of text plus provenance metadata.

    Pydantic (not a bare dataclass) so it validates and provides
    ``model_dump()`` / ``Chunk(**d)`` for the FAISS chunk-store round-trip.
    """

    chunk_id: str
    text: str
    source: str
    page: int = Field(ge=1, description="1-based page number")
    section: str = ""
    char_start: int = 0
    char_end: int = 0


# ---------------------------------------------------------------------------
# PDF loading
# ---------------------------------------------------------------------------

def _load_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return [(page_1based, text), ...] for every page that has text."""
    try:
        import fitz
    except ImportError as exc:
        raise ImportError("PyMuPDF required: pip install PyMuPDF") from exc

    doc = fitz.open(str(pdf_path))
    pages = [(i + 1, page.get_text("text")) for i, page in enumerate(doc)]
    doc.close()
    return [(p, t) for p, t in pages if t.strip()]


# ---------------------------------------------------------------------------
# Section header detection
# ---------------------------------------------------------------------------

_HDR_RE = re.compile(
    r'^(?:'
    r'\d+[\.\)]\s+[A-Z]'          # "1. Introduction" / "2) Methods"
    r'|[A-Z][A-Z\s]{4,}$'         # ALL-CAPS line ≥ 5 chars
    r'|[A-Z][^a-z]{0,40}:\s*$'    # "Abstract:" / "RESULTS:"
    r')',
)


def _is_header(line: str) -> bool:
    return bool(_HDR_RE.match(line.strip()))


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

_SENT_RE = re.compile(r'(?<=[.!?])\s+')


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.split(text) if s.strip()]


# ---------------------------------------------------------------------------
# Core chunker
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    source: str,
    page: int,
    section: str = "",
    char_offset: int = 0,
    overlap_tail: str = "",
    *,
    target_chars: int = TARGET_CHARS,
    overlap_chars: int = OVERLAP_CHARS,
) -> tuple[list[Chunk], str]:
    """
    Split *text* into Chunks.

    Returns (chunks, new_overlap_tail).
    """
    sents = _sentences(text)
    if not sents:
        return [], overlap_tail

    chunks: list[Chunk] = []
    buf: list[str] = [overlap_tail] if overlap_tail else []
    buf_len = len(overlap_tail)
    char_pos = char_offset

    def _flush():
        nonlocal char_pos, overlap_tail
        body = " ".join(buf).strip()
        if not body:
            return
        cid = hashlib.md5(f"{source}:{page}:{char_pos}".encode()).hexdigest()[:16]
        chunks.append(Chunk(
            chunk_id=cid, text=body, source=source, page=page,
            section=section, char_start=char_pos, char_end=char_pos + len(body),
        ))
        overlap_tail = body[-overlap_chars:] if len(body) > overlap_chars else body
        char_pos += len(body)

    for sent in sents:
        if buf_len + len(sent) > target_chars and buf:
            _flush()
            buf = [overlap_tail, sent]
            buf_len = len(overlap_tail) + len(sent)
        else:
            buf.append(sent)
            buf_len += len(sent)

    if buf:
        _flush()

    return chunks, overlap_tail


# ---------------------------------------------------------------------------
# High-level ingest
# ---------------------------------------------------------------------------

def ingest_pdf(pdf_path: Path) -> list[Chunk]:
    """Load one PDF and return all semantic chunks with metadata."""
    source = pdf_path.name
    pages = _load_pages(pdf_path)
    all_chunks: list[Chunk] = []
    current_section = ""
    overlap_tail = ""
    global_offset = 0

    for page_num, page_text in pages:
        for line in page_text.splitlines():
            if line.strip() and _is_header(line):
                current_section = line.strip()[:80]
                break

        new_chunks, overlap_tail = chunk_text(
            page_text, source=source, page=page_num,
            section=current_section, char_offset=global_offset,
            overlap_tail=overlap_tail,
        )
        all_chunks.extend(new_chunks)
        global_offset += len(page_text)

    return all_chunks


def ingest_corpus(pdf_dir: Path | None = None) -> list[Chunk]:
    """Ingest every PDF in *pdf_dir* (defaults to config.PDF_DIR)."""
    pdf_dir = pdf_dir or config.PDF_DIR
    all_chunks: list[Chunk] = []
    for pdf in sorted(Path(pdf_dir).glob("*.pdf")):
        all_chunks.extend(ingest_pdf(pdf))
    return all_chunks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else config.PDF_DIR
    chunks = ingest_pdf(target) if target.is_file() else ingest_corpus(target)
    print(f"Ingested {len(chunks)} chunks.")
    for c in chunks[:5]:
        print(f'  [{c.chunk_id}] {c.source} p.{c.page} section={c.section[:30]} "{c.text[:80]}..."')
