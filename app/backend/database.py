"""SQLite persistence layer (stdlib sqlite3 — no ORM required).

Tables
------
users          — registered accounts
corpora        — named document collections per user
documents      — indexed PDFs inside a corpus
queries        — query history with agent output
query_cache    — response cache with TTL
embedding_cache — persistent embedding cache (avoids re-encoding known texts)
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import config

DB_PATH: Path = config.DATA_DIR / "app.db"


def _use_azure() -> bool:
    return config.DB_BACKEND == "azure_sql"


# --------------------------------------------------------------------------- #
# Azure SQL (pyodbc) — a thin wrapper so the rest of this module can keep using
# ``conn.execute(sql, params)`` and rows that behave like sqlite3.Row (both
# ``dict(row)`` and ``row["col"]`` work). pyodbc is imported lazily so the app
# runs with no ODBC packages installed while DB_BACKEND stays "sqlite".
# --------------------------------------------------------------------------- #

class _AzureRow(dict):
    """dict subclass: supports dict(row), row["col"], and row.pop(...)."""


class _AzureResult:
    def __init__(self, cursor) -> None:
        self._cursor = cursor
        self.rowcount = cursor.rowcount

    def _cols(self) -> list[str]:
        return [c[0] for c in self._cursor.description]

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        return _AzureRow(zip(self._cols(), row))

    def fetchall(self):
        rows = self._cursor.fetchall()
        if not rows:
            return []
        cols = self._cols()
        return [_AzureRow(zip(cols, r)) for r in rows]


class _AzureConn:
    def __init__(self, raw) -> None:
        self._raw = raw

    def execute(self, sql: str, params: tuple = ()):
        cur = self._raw.cursor()
        if params:
            cur.execute(sql, tuple(params))
        else:
            cur.execute(sql)
        return _AzureResult(cur)

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()


def _azure_connect() -> _AzureConn:
    import pyodbc  # lazy

    if not config.AZURE_SQL_CONNECTION_STRING:
        raise RuntimeError("DB_BACKEND=azure_sql but AZURE_SQL_CONNECTION_STRING is not set")
    raw = pyodbc.connect(config.AZURE_SQL_CONNECTION_STRING, autocommit=False)
    return _AzureConn(raw)


@contextmanager
def get_conn():
    if _use_azure():
        conn = _azure_connect()
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Azure SQL schema (T-SQL). Same tables as the SQLite schema below, with
# SQL-Server types and idempotent IF-NOT-EXISTS guards. KG edge FKs are dropped
# (the KG is unused, and dual cascade paths to one table are illegal in SQL
# Server); purge_corpus_data() handles their cleanup explicitly.
# --------------------------------------------------------------------------- #
_AZURE_DDL: list[str] = [
    """IF OBJECT_ID(N'dbo.users', N'U') IS NULL CREATE TABLE dbo.users (
        id NVARCHAR(64) PRIMARY KEY, email NVARCHAR(320) UNIQUE NOT NULL,
        name NVARCHAR(256) NOT NULL, password_hash NVARCHAR(256) NOT NULL,
        created_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.corpora', N'U') IS NULL CREATE TABLE dbo.corpora (
        id NVARCHAR(64) PRIMARY KEY,
        user_id NVARCHAR(64) NOT NULL REFERENCES dbo.users(id) ON DELETE CASCADE,
        name NVARCHAR(400) NOT NULL, doc_count INT DEFAULT 0,
        chunk_count INT DEFAULT 0, created_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.documents', N'U') IS NULL CREATE TABLE dbo.documents (
        id NVARCHAR(64) PRIMARY KEY,
        corpus_id NVARCHAR(64) NOT NULL REFERENCES dbo.corpora(id) ON DELETE CASCADE,
        user_id NVARCHAR(64) NOT NULL, filename NVARCHAR(400) NOT NULL,
        original_name NVARCHAR(400) NOT NULL, page_count INT DEFAULT 0,
        chunk_count INT DEFAULT 0, file_size INT DEFAULT 0,
        indexed_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.queries', N'U') IS NULL CREATE TABLE dbo.queries (
        id NVARCHAR(64) PRIMARY KEY, user_id NVARCHAR(64) NOT NULL,
        corpus_id NVARCHAR(64) NULL, question NVARCHAR(MAX) NOT NULL,
        answer NVARCHAR(MAX) DEFAULT '', mode NVARCHAR(20) DEFAULT 'cloud',
        provider NVARCHAR(40) DEFAULT 'groq', latency_ms INT DEFAULT 0,
        overall_faithfulness FLOAT DEFAULT 0,
        sub_questions_json NVARCHAR(MAX) DEFAULT '[]',
        claims_json NVARCHAR(MAX) DEFAULT '[]',
        stage_log_json NVARCHAR(MAX) DEFAULT '[]', is_cached INT DEFAULT 0,
        created_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.query_cache', N'U') IS NULL CREATE TABLE dbo.query_cache (
        cache_key NVARCHAR(200) PRIMARY KEY, response_json NVARCHAR(MAX) NOT NULL,
        created_at NVARCHAR(40) NOT NULL, expires_at NVARCHAR(40) NOT NULL,
        hit_count INT DEFAULT 0)""",
    """IF OBJECT_ID(N'dbo.embedding_cache', N'U') IS NULL CREATE TABLE dbo.embedding_cache (
        text_hash NVARCHAR(80) PRIMARY KEY, embedding_blob VARBINARY(MAX) NOT NULL,
        created_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.conversations', N'U') IS NULL CREATE TABLE dbo.conversations (
        id NVARCHAR(64) PRIMARY KEY,
        user_id NVARCHAR(64) NOT NULL REFERENCES dbo.users(id) ON DELETE CASCADE,
        corpus_id NVARCHAR(64) NULL,
        title NVARCHAR(400) NOT NULL DEFAULT 'New conversation',
        mode NVARCHAR(20) NOT NULL DEFAULT 'rag', created_at NVARCHAR(40) NOT NULL,
        updated_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.messages', N'U') IS NULL CREATE TABLE dbo.messages (
        id NVARCHAR(64) PRIMARY KEY,
        conversation_id NVARCHAR(64) NOT NULL REFERENCES dbo.conversations(id) ON DELETE CASCADE,
        role NVARCHAR(20) NOT NULL, content NVARCHAR(MAX) NOT NULL,
        query_id NVARCHAR(64) NULL, metadata_json NVARCHAR(MAX) DEFAULT '{}',
        created_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.user_settings', N'U') IS NULL CREATE TABLE dbo.user_settings (
        user_id NVARCHAR(64) PRIMARY KEY REFERENCES dbo.users(id) ON DELETE CASCADE,
        llm_mode NVARCHAR(20) NOT NULL DEFAULT 'cloud',
        provider NVARCHAR(40) NOT NULL DEFAULT 'groq',
        ollama_host NVARCHAR(200) NOT NULL DEFAULT 'http://localhost',
        ollama_port INT NOT NULL DEFAULT 11434,
        ollama_model NVARCHAR(80) NOT NULL DEFAULT 'phi4-mini',
        groq_model NVARCHAR(80) NOT NULL DEFAULT 'llama-3.3-70b-versatile',
        groq_api_key NVARCHAR(200) DEFAULT '', updated_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.knowledge_graph_nodes', N'U') IS NULL CREATE TABLE dbo.knowledge_graph_nodes (
        id NVARCHAR(64) PRIMARY KEY, corpus_id NVARCHAR(64) NOT NULL,
        entity NVARCHAR(400) NOT NULL, entity_type NVARCHAR(80) NOT NULL,
        description NVARCHAR(MAX) DEFAULT '', source_chunk_id NVARCHAR(80) DEFAULT '',
        created_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.knowledge_graph_edges', N'U') IS NULL CREATE TABLE dbo.knowledge_graph_edges (
        id NVARCHAR(64) PRIMARY KEY, corpus_id NVARCHAR(64) NOT NULL,
        source_id NVARCHAR(64) NOT NULL, target_id NVARCHAR(64) NOT NULL,
        relation NVARCHAR(200) NOT NULL, source_chunk_id NVARCHAR(80) DEFAULT '',
        created_at NVARCHAR(40) NOT NULL)""",
    """IF OBJECT_ID(N'dbo.viva_sessions', N'U') IS NULL CREATE TABLE dbo.viva_sessions (
        id NVARCHAR(64) PRIMARY KEY,
        user_id NVARCHAR(64) NOT NULL REFERENCES dbo.users(id) ON DELETE CASCADE,
        corpus_id NVARCHAR(64) NOT NULL,
        difficulty NVARCHAR(40) NOT NULL DEFAULT 'masters',
        questions_json NVARCHAR(MAX) DEFAULT '[]', answers_json NVARCHAR(MAX) DEFAULT '[]',
        scores_json NVARCHAR(MAX) DEFAULT '[]', completed INT DEFAULT 0,
        created_at NVARCHAR(40) NOT NULL, updated_at NVARCHAR(40) NOT NULL)""",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_conversations_user' AND object_id=OBJECT_ID('dbo.conversations')) CREATE INDEX idx_conversations_user ON dbo.conversations(user_id)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_messages_conv' AND object_id=OBJECT_ID('dbo.messages')) CREATE INDEX idx_messages_conv ON dbo.messages(conversation_id)",
    "IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='idx_viva_user' AND object_id=OBJECT_ID('dbo.viva_sessions')) CREATE INDEX idx_viva_user ON dbo.viva_sessions(user_id)",
]


def init_db() -> None:
    if _use_azure():
        with get_conn() as conn:
            for stmt in _AZURE_DDL:
                conn.execute(stmt)
        return
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            email       TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS corpora (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            doc_count   INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0,
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id            TEXT PRIMARY KEY,
            corpus_id     TEXT NOT NULL REFERENCES corpora(id) ON DELETE CASCADE,
            user_id       TEXT NOT NULL,
            filename      TEXT NOT NULL,
            original_name TEXT NOT NULL,
            page_count    INTEGER DEFAULT 0,
            chunk_count   INTEGER DEFAULT 0,
            file_size     INTEGER DEFAULT 0,
            indexed_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS queries (
            id                  TEXT PRIMARY KEY,
            user_id             TEXT NOT NULL,
            corpus_id           TEXT,
            question            TEXT NOT NULL,
            answer              TEXT DEFAULT '',
            mode                TEXT DEFAULT 'cloud',
            provider            TEXT DEFAULT 'groq',
            latency_ms          INTEGER DEFAULT 0,
            overall_faithfulness REAL DEFAULT 0.0,
            sub_questions_json  TEXT DEFAULT '[]',
            claims_json         TEXT DEFAULT '[]',
            stage_log_json      TEXT DEFAULT '[]',
            is_cached           INTEGER DEFAULT 0,
            created_at          TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS query_cache (
            cache_key    TEXT PRIMARY KEY,
            response_json TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            expires_at   TEXT NOT NULL,
            hit_count    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS embedding_cache (
            text_hash      TEXT PRIMARY KEY,
            embedding_blob BLOB NOT NULL,
            created_at     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            corpus_id   TEXT,
            title       TEXT NOT NULL DEFAULT 'New conversation',
            mode        TEXT NOT NULL DEFAULT 'rag',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            query_id        TEXT,
            metadata_json   TEXT DEFAULT '{}',
            created_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id         TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            llm_mode        TEXT NOT NULL DEFAULT 'cloud',
            provider        TEXT NOT NULL DEFAULT 'groq',
            ollama_host     TEXT NOT NULL DEFAULT 'http://localhost',
            ollama_port     INTEGER NOT NULL DEFAULT 11434,
            ollama_model    TEXT NOT NULL DEFAULT 'phi4-mini',
            groq_model      TEXT NOT NULL DEFAULT 'llama-3.3-70b-versatile',
            groq_api_key    TEXT DEFAULT '',
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
            id          TEXT PRIMARY KEY,
            corpus_id   TEXT NOT NULL,
            entity      TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            source_chunk_id TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
            id          TEXT PRIMARY KEY,
            corpus_id   TEXT NOT NULL,
            source_id   TEXT NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
            target_id   TEXT NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
            relation    TEXT NOT NULL,
            source_chunk_id TEXT DEFAULT '',
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS viva_sessions (
            id              TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            corpus_id       TEXT NOT NULL,
            difficulty      TEXT NOT NULL DEFAULT 'masters',
            questions_json  TEXT DEFAULT '[]',
            answers_json    TEXT DEFAULT '[]',
            scores_json     TEXT DEFAULT '[]',
            completed       INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_kg_nodes_corpus ON knowledge_graph_nodes(corpus_id);
        CREATE INDEX IF NOT EXISTS idx_kg_edges_corpus ON knowledge_graph_edges(corpus_id);
        CREATE INDEX IF NOT EXISTS idx_viva_user ON viva_sessions(user_id);
        """)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.utcnow().isoformat()

def _uid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def create_user(email: str, name: str, password_hash: str) -> dict:
    row = dict(id=_uid(), email=email, name=name,
               password_hash=password_hash, created_at=_now())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id,email,name,password_hash,created_at) VALUES (?,?,?,?,?)",
            (row["id"], row["email"], row["name"], row["password_hash"], row["created_at"]),
        )
    return row


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(r) if r else None


def get_user_by_id(user_id: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(r) if r else None


# ---------------------------------------------------------------------------
# Corpora
# ---------------------------------------------------------------------------

def create_corpus(user_id: str, name: str) -> dict:
    row = dict(id=_uid(), user_id=user_id, name=name,
               doc_count=0, chunk_count=0, created_at=_now())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO corpora (id,user_id,name,doc_count,chunk_count,created_at) VALUES (?,?,?,0,0,?)",
            (row["id"], row["user_id"], row["name"], row["created_at"]),
        )
    return row


def list_corpora(user_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM corpora WHERE user_id=? ORDER BY created_at DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_corpus(corpus_id: str, user_id: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM corpora WHERE id=? AND user_id=?", (corpus_id, user_id)
        ).fetchone()
        return dict(r) if r else None


def get_corpus_any(corpus_id: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM corpora WHERE id=?", (corpus_id,)).fetchone()
        return dict(r) if r else None


def update_corpus_counts(corpus_id: str, doc_delta: int = 0, chunk_delta: int = 0) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE corpora SET doc_count=doc_count+?, chunk_count=chunk_count+? WHERE id=?",
            (doc_delta, chunk_delta, corpus_id),
        )


def delete_corpus(corpus_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        r = conn.execute(
            "DELETE FROM corpora WHERE id=? AND user_id=?", (corpus_id, user_id)
        )
        return r.rowcount > 0


def purge_corpus_data(corpus_id: str) -> None:
    """Delete all rows keyed by corpus_id that lack an ON DELETE CASCADE FK
    (knowledge graph, query history, viva sessions). Called on corpus delete so
    a deleted corpus leaves no orphaned content — a right-to-erasure gap
    otherwise. `documents`/`conversations` cascade via their FK already."""
    with get_conn() as conn:
        conn.execute("DELETE FROM knowledge_graph_edges WHERE corpus_id=?", (corpus_id,))
        conn.execute("DELETE FROM knowledge_graph_nodes WHERE corpus_id=?", (corpus_id,))
        conn.execute("DELETE FROM queries WHERE corpus_id=?", (corpus_id,))
        conn.execute("DELETE FROM viva_sessions WHERE corpus_id=?", (corpus_id,))


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def create_document(corpus_id: str, user_id: str, filename: str, original_name: str,
                    page_count: int, chunk_count: int, file_size: int) -> dict:
    row = dict(id=_uid(), corpus_id=corpus_id, user_id=user_id, filename=filename,
               original_name=original_name, page_count=page_count,
               chunk_count=chunk_count, file_size=file_size, indexed_at=_now())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO documents (id,corpus_id,user_id,filename,original_name,"
            "page_count,chunk_count,file_size,indexed_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (row["id"], row["corpus_id"], row["user_id"], row["filename"],
             row["original_name"], row["page_count"], row["chunk_count"],
             row["file_size"], row["indexed_at"]),
        )
    return row


def list_documents(corpus_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE corpus_id=? ORDER BY indexed_at DESC", (corpus_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_document(doc_id: str, user_id: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM documents WHERE id=? AND user_id=?",
                         (doc_id, user_id)).fetchone()
        if r:
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            return dict(r)
        return None


# ---------------------------------------------------------------------------
# Query history
# ---------------------------------------------------------------------------

def save_query(user_id: str, corpus_id: str | None, question: str, answer: str,
               mode: str, provider: str, latency_ms: int, overall_faithfulness: float,
               sub_questions: list, claims: list, stage_log: list,
               is_cached: bool = False) -> dict:
    row = dict(id=_uid(), user_id=user_id, corpus_id=corpus_id,
               question=question, answer=answer, mode=mode, provider=provider,
               latency_ms=latency_ms, overall_faithfulness=overall_faithfulness,
               sub_questions_json=json.dumps(sub_questions),
               claims_json=json.dumps(claims),
               stage_log_json=json.dumps(stage_log),
               is_cached=int(is_cached), created_at=_now())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO queries (id,user_id,corpus_id,question,answer,mode,provider,"
            "latency_ms,overall_faithfulness,sub_questions_json,claims_json,stage_log_json,"
            "is_cached,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (row["id"], row["user_id"], row["corpus_id"], row["question"], row["answer"],
             row["mode"], row["provider"], row["latency_ms"], row["overall_faithfulness"],
             row["sub_questions_json"], row["claims_json"], row["stage_log_json"],
             row["is_cached"], row["created_at"]),
        )
    return _expand_query_row(row)


def list_queries(user_id: str, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM queries WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [_expand_query_row(dict(r)) for r in rows[:limit]]


def _expand_query_row(d: dict) -> dict:
    d["sub_questions"] = json.loads(d.pop("sub_questions_json", "[]"))
    d["claims"] = json.loads(d.pop("claims_json", "[]"))
    d["stage_log"] = json.loads(d.pop("stage_log_json", "[]"))
    return d


# ---------------------------------------------------------------------------
# Query cache
# ---------------------------------------------------------------------------

def get_cached_response(cache_key: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM query_cache WHERE cache_key=? AND expires_at > ?",
            (cache_key, _now()),
        ).fetchone()
        if r:
            conn.execute(
                "UPDATE query_cache SET hit_count=hit_count+1 WHERE cache_key=?", (cache_key,)
            )
            return json.loads(r["response_json"])
        return None


def set_cached_response(cache_key: str, response: dict, ttl_hours: int = 24) -> None:
    expires = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat()
    with get_conn() as conn:
        # Portable upsert (works on both SQLite and Azure SQL): delete then insert.
        conn.execute("DELETE FROM query_cache WHERE cache_key=?", (cache_key,))
        conn.execute(
            "INSERT INTO query_cache (cache_key,response_json,created_at,expires_at,hit_count)"
            " VALUES (?,?,?,?,0)",
            (cache_key, json.dumps(response, default=str), _now(), expires),
        )


def clear_query_cache() -> int:
    """Purge the entire persistent query cache. Called when a corpus changes —
    cache keys are hashed so we cannot filter by corpus_id, and nuking the small
    cache is correct (answers just recompute) and avoids serving stale results."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM query_cache")
        return cur.rowcount


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

def create_conversation(user_id: str, corpus_id: str | None, title: str, mode: str = "rag") -> dict:
    now = _now()
    row = dict(id=_uid(), user_id=user_id, corpus_id=corpus_id,
               title=title, mode=mode, created_at=now, updated_at=now)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id,user_id,corpus_id,title,mode,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (row["id"], row["user_id"], row["corpus_id"], row["title"],
             row["mode"], row["created_at"], row["updated_at"]),
        )
    return row


def list_conversations(user_id: str, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows[:limit]]


def get_conversation(conv_id: str, user_id: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM conversations WHERE id=? AND user_id=?", (conv_id, user_id)
        ).fetchone()
        return dict(r) if r else None


def update_conversation_title(conv_id: str, user_id: str, title: str) -> bool:
    with get_conn() as conn:
        r = conn.execute(
            "UPDATE conversations SET title=?, updated_at=? WHERE id=? AND user_id=?",
            (title, _now(), conv_id, user_id),
        )
        return r.rowcount > 0


def touch_conversation(conv_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (_now(), conv_id))


def delete_conversation(conv_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        r = conn.execute(
            "DELETE FROM conversations WHERE id=? AND user_id=?", (conv_id, user_id)
        )
        return r.rowcount > 0


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def add_message(conv_id: str, role: str, content: str,
                query_id: str | None = None, metadata: dict | None = None) -> dict:
    row = dict(id=_uid(), conversation_id=conv_id, role=role, content=content,
               query_id=query_id, metadata_json=json.dumps(metadata or {}),
               created_at=_now())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id,conversation_id,role,content,query_id,metadata_json,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (row["id"], row["conversation_id"], row["role"], row["content"],
             row["query_id"], row["metadata_json"], row["created_at"]),
        )
    row["metadata"] = json.loads(row.pop("metadata_json"))
    return row


def list_messages(conv_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
            (conv_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.pop("metadata_json", "{}"))
            result.append(d)
        return result


# ---------------------------------------------------------------------------
# User settings
# ---------------------------------------------------------------------------

def get_user_settings(user_id: str) -> dict:
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM user_settings WHERE user_id=?", (user_id,)).fetchone()
        if r:
            return dict(r)
        # Return defaults
        return dict(
            user_id=user_id, llm_mode="cloud", provider="groq",
            ollama_host="http://localhost", ollama_port=11434,
            ollama_model="phi4-mini",
            groq_model="llama-3.3-70b-versatile",
            groq_api_key="", updated_at=_now(),
        )


def save_user_settings(user_id: str, llm_mode: str, provider: str,
                       ollama_host: str, ollama_port: int, ollama_model: str,
                       groq_model: str, groq_api_key: str) -> dict:
    now = _now()
    with get_conn() as conn:
        # Portable upsert (SQLite + Azure SQL): update if the row exists, else insert.
        exists = conn.execute(
            "SELECT 1 FROM user_settings WHERE user_id=?", (user_id,)
        ).fetchone()
        if exists:
            conn.execute(
                """UPDATE user_settings SET
                     llm_mode=?, provider=?, ollama_host=?, ollama_port=?,
                     ollama_model=?, groq_model=?, groq_api_key=?, updated_at=?
                   WHERE user_id=?""",
                (llm_mode, provider, ollama_host, ollama_port,
                 ollama_model, groq_model, groq_api_key, now, user_id),
            )
        else:
            conn.execute(
                """INSERT INTO user_settings
                   (user_id,llm_mode,provider,ollama_host,ollama_port,ollama_model,groq_model,groq_api_key,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (user_id, llm_mode, provider, ollama_host, ollama_port,
                 ollama_model, groq_model, groq_api_key, now),
            )
    return get_user_settings(user_id)


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------

def upsert_kg_node(corpus_id: str, entity: str, entity_type: str,
                   description: str = "", source_chunk_id: str = "") -> str:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT id FROM knowledge_graph_nodes WHERE corpus_id=? AND entity=?",
            (corpus_id, entity),
        ).fetchone()
        if r:
            conn.execute(
                "UPDATE knowledge_graph_nodes SET description=?, source_chunk_id=? WHERE id=?",
                (description, source_chunk_id, r["id"]),
            )
            return r["id"]
        node_id = _uid()
        conn.execute(
            "INSERT INTO knowledge_graph_nodes (id,corpus_id,entity,entity_type,description,source_chunk_id,created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (node_id, corpus_id, entity, entity_type, description, source_chunk_id, _now()),
        )
        return node_id


def upsert_kg_edge(corpus_id: str, source_id: str, target_id: str,
                   relation: str, source_chunk_id: str = "") -> None:
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM knowledge_graph_edges WHERE corpus_id=? AND source_id=? AND target_id=? AND relation=?",
            (corpus_id, source_id, target_id, relation),
        ).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO knowledge_graph_edges (id,corpus_id,source_id,target_id,relation,source_chunk_id,created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (_uid(), corpus_id, source_id, target_id, relation, source_chunk_id, _now()),
            )


def get_kg_nodes(corpus_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge_graph_nodes WHERE corpus_id=? ORDER BY entity_type, entity",
            (corpus_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_kg_edges(corpus_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.*, s.entity AS source_entity, t.entity AS target_entity
               FROM knowledge_graph_edges e
               JOIN knowledge_graph_nodes s ON e.source_id=s.id
               JOIN knowledge_graph_nodes t ON e.target_id=t.id
               WHERE e.corpus_id=?""",
            (corpus_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Viva sessions
# ---------------------------------------------------------------------------

def create_viva_session(user_id: str, corpus_id: str,
                        difficulty: str = "masters") -> dict:
    now = _now()
    row = dict(id=_uid(), user_id=user_id, corpus_id=corpus_id,
               difficulty=difficulty, questions_json="[]", answers_json="[]",
               scores_json="[]", completed=0, created_at=now, updated_at=now)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO viva_sessions (id,user_id,corpus_id,difficulty,"
            "questions_json,answers_json,scores_json,completed,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (row["id"], row["user_id"], row["corpus_id"], row["difficulty"],
             row["questions_json"], row["answers_json"], row["scores_json"],
             row["completed"], row["created_at"], row["updated_at"]),
        )
    return _expand_viva(row)


def get_viva_session(session_id: str, user_id: str) -> dict | None:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM viva_sessions WHERE id=? AND user_id=?", (session_id, user_id)
        ).fetchone()
        return _expand_viva(dict(r)) if r else None


def list_viva_sessions(user_id: str, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM viva_sessions WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [_expand_viva(dict(r)) for r in rows[:limit]]


def update_viva_session(session_id: str, user_id: str,
                        questions: list | None = None,
                        answers: list | None = None,
                        scores: list | None = None,
                        completed: bool | None = None) -> dict | None:
    with get_conn() as conn:
        r = conn.execute(
            "SELECT * FROM viva_sessions WHERE id=? AND user_id=?", (session_id, user_id)
        ).fetchone()
        if not r:
            return None
        d = dict(r)
        if questions is not None:
            d["questions_json"] = json.dumps(questions)
        if answers is not None:
            d["answers_json"] = json.dumps(answers)
        if scores is not None:
            d["scores_json"] = json.dumps(scores)
        if completed is not None:
            d["completed"] = int(completed)
        d["updated_at"] = _now()
        conn.execute(
            "UPDATE viva_sessions SET questions_json=?,answers_json=?,scores_json=?,"
            "completed=?,updated_at=? WHERE id=?",
            (d["questions_json"], d["answers_json"], d["scores_json"],
             d["completed"], d["updated_at"], session_id),
        )
        return _expand_viva(d)


def _expand_viva(d: dict) -> dict:
    d["questions"] = json.loads(d.pop("questions_json", "[]"))
    d["answers"] = json.loads(d.pop("answers_json", "[]"))
    d["scores"] = json.loads(d.pop("scores_json", "[]"))
    return d
