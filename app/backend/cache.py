"""Two-level response cache: in-memory LRU + SQLite-backed TTL cache."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any


class _LRU:
    def __init__(self, maxsize: int = 256):
        self._d: OrderedDict[str, Any] = OrderedDict()
        self._max = maxsize

    def get(self, key: str) -> Any | None:
        if key not in self._d:
            return None
        self._d.move_to_end(key)
        return self._d[key]

    def set(self, key: str, value: Any) -> None:
        if key in self._d:
            self._d.move_to_end(key)
        self._d[key] = value
        if len(self._d) > self._max:
            self._d.popitem(last=False)


_mem = _LRU(maxsize=256)


def cache_key(question: str, corpus_id: str, mode: str, provider: str, top_k: int) -> str:
    raw = f"{question}|{corpus_id}|{mode}|{provider}|{top_k}"
    return hashlib.md5(raw.encode()).hexdigest()


def get(question: str, corpus_id: str, mode: str, provider: str, top_k: int) -> Any | None:
    key = cache_key(question, corpus_id, mode, provider, top_k)
    hit = _mem.get(key)
    if hit is not None:
        return hit
    from app.backend.database import get_cached_response
    result = get_cached_response(key)
    if result is not None:
        _mem.set(key, result)
    return result


def put(question: str, corpus_id: str, mode: str, provider: str, top_k: int,
        response: Any) -> None:
    key = cache_key(question, corpus_id, mode, provider, top_k)
    _mem.set(key, response)
    from app.backend.database import set_cached_response
    set_cached_response(key, response)


def invalidate_corpus(corpus_id: str) -> None:
    """Invalidate cached answers after a corpus changes.

    Cache keys are MD5 hashes, so the in-memory layer can't be filtered by
    corpus id reliably; we clear the whole in-memory LRU AND purge the SQLite
    query_cache. Otherwise a repeat question returns a pre-change answer for up
    to the 24h TTL (stale-answer bug)."""
    _mem._d.clear()
    from app.backend.database import clear_query_cache
    clear_query_cache()
