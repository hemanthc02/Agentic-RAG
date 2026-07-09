"""Unit tests for src/ingestion.py — semantic sentence-based chunker."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.ingestion import Chunk, _is_header, _sentences, chunk_text


def test_chunk_text_returns_chunks_and_tail():
    chunks, tail = chunk_text(
        "First sentence here. Second sentence here. Third one.",
        source="a.pdf", page=2,
    )
    assert isinstance(chunks, list) and isinstance(tail, str)
    assert all(isinstance(c, Chunk) for c in chunks)
    # short text fits in a single chunk under the default target
    assert len(chunks) == 1


def test_metadata_propagated():
    chunks, _ = chunk_text("Alpha. Beta. Gamma.", source="paper.pdf", page=5, section="INTRO")
    c = chunks[0]
    assert c.source == "paper.pdf"
    assert c.page == 5
    assert c.section == "INTRO"
    assert len(c.chunk_id) == 16  # md5 hex truncated to 16


def test_splits_when_exceeding_target():
    text = " ".join(f"Sentence number {i} is right here." for i in range(200))
    chunks, _ = chunk_text(text, source="a.pdf", page=1, target_chars=200, overlap_chars=20)
    assert len(chunks) > 1
    # sentences are never split mid-way, so a chunk may slightly exceed target,
    # but not by more than one sentence + overlap
    assert all(len(c.text) <= 200 + 60 for c in chunks)


def test_overlap_tail_carried_between_chunks():
    text = " ".join(f"Sentence {i} content." for i in range(100))
    chunks, tail = chunk_text(text, source="a.pdf", page=1, target_chars=120, overlap_chars=30)
    assert len(chunks) >= 2
    # the returned tail is the suffix of the final chunk
    assert chunks[-1].text.endswith(tail)


def test_empty_text_returns_empty_and_preserves_tail():
    chunks, tail = chunk_text("   ", source="a.pdf", page=1, overlap_tail="carry")
    assert chunks == []
    assert tail == "carry"


def test_chunk_validation_page_must_be_ge_1():
    with pytest.raises(ValidationError):
        Chunk(chunk_id="x", text="t", source="a.pdf", page=0)


def test_is_header_detects_common_styles():
    assert _is_header("1. Introduction")
    assert _is_header("2) Methods")
    assert _is_header("ABSTRACT")
    assert not _is_header("This is ordinary body text.")


def test_sentences_splitter():
    assert _sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]
