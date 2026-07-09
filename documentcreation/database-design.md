# Database Design
**Project:** VeritasRAG · **Phase:** 7 (step 7) · **Version:** 1.0 · **Date:** 2026-06-07
**Engine:** PostgreSQL 16 + pgvector · **Cache/queue:** Redis 7 · **Migrations:** Alembic

## 1. Design principles
Multi-tenant by `tenant_id` on every owned row (row-level isolation; RLS optional in H3). UUID v7 primary keys. `created_at/updated_at` everywhere. Vectors co-located in Postgres via pgvector (HNSW). Soft-delete on user-facing aggregates; hard-delete path for data-residency (right-to-erasure).

## 2. ER overview
```
tenants 1───* users
tenants 1───* corpora 1───* documents 1───* chunks
users   1───* query_runs 1───* claims *───* chunks (claim_citations)
corpora 1───* query_runs
users   1───* evaluation_runs
tenants 1───* audit_events
tenants 1───* provider_configs
```

## 3. Schema (DDL sketch)
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tenants (
  id UUID PRIMARY KEY, name TEXT NOT NULL,
  data_residency TEXT NOT NULL DEFAULT 'cloud',     -- 'cloud' | 'local'
  created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE users (
  id UUID PRIMARY KEY, tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  email CITEXT UNIQUE NOT NULL, hashed_password TEXT, oauth_sub TEXT,
  role TEXT NOT NULL DEFAULT 'researcher',          -- researcher|admin|owner|service
  created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE corpora (
  id UUID PRIMARY KEY, tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  owner_id UUID REFERENCES users(id), name TEXT NOT NULL,
  embedding_model TEXT NOT NULL, chunk_size INT, chunk_overlap INT,
  status TEXT NOT NULL DEFAULT 'empty', stats JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE documents (
  id UUID PRIMARY KEY, corpus_id UUID REFERENCES corpora(id) ON DELETE CASCADE,
  filename TEXT NOT NULL, num_pages INT, sha256 TEXT, storage_uri TEXT,
  created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE chunks (
  id UUID PRIMARY KEY, corpus_id UUID REFERENCES corpora(id) ON DELETE CASCADE,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  chunk_id TEXT NOT NULL, page INT, content TEXT NOT NULL,
  embedding vector(384) NOT NULL);                  -- MiniLM dim; configurable
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks (corpus_id);

CREATE TABLE query_runs (
  id UUID PRIMARY KEY, tenant_id UUID, user_id UUID REFERENCES users(id),
  corpus_id UUID REFERENCES corpora(id), question TEXT NOT NULL,
  mode TEXT NOT NULL, provider TEXT, model TEXT,
  sub_questions JSONB, answer TEXT, overall_supportedness REAL,
  retries INT DEFAULT 0, latency_ms INT, status TEXT,
  created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE claims (
  id UUID PRIMARY KEY, run_id UUID REFERENCES query_runs(id) ON DELETE CASCADE,
  claim_text TEXT NOT NULL, supportedness_score REAL, reliance_flag BOOLEAN,
  verdict BOOLEAN, ord INT);

CREATE TABLE claim_citations (                       -- claim *──* chunk
  claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
  chunk_id UUID REFERENCES chunks(id), PRIMARY KEY (claim_id, chunk_id));

CREATE TABLE evaluation_runs (
  id UUID PRIMARY KEY, tenant_id UUID, user_id UUID,
  benchmark TEXT, pipeline TEXT, llm_mode TEXT, metrics JSONB,
  significance JSONB, created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE provider_configs (
  id UUID PRIMARY KEY, tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
  provider TEXT NOT NULL, default_model TEXT, enabled BOOLEAN DEFAULT true,
  -- secrets NEVER stored here; only a reference to a secret manager key
  secret_ref TEXT, params JSONB DEFAULT '{}');

CREATE TABLE audit_events (
  id UUID PRIMARY KEY, tenant_id UUID, actor_id UUID, action TEXT NOT NULL,
  target_type TEXT, target_id UUID, metadata JSONB, created_at TIMESTAMPTZ DEFAULT now());
```

## 4. Indexing & performance
- HNSW on `chunks.embedding` (cosine); per-`corpus_id` filtering via partial/composite indexes.
- B-tree on FKs and `created_at` for history queries.
- Partition `chunks` by `corpus_id` (hash) at scale; consider per-tenant schemas in H3.
- Redis: `cfg:*` (provider/threshold config), `rl:*` (rate limits), `job:*` (ingest/eval queue + progress), `q:*` (hot query cache, TTL).

## 5. Privacy & retention
- `data_residency='local'` tenants: chunk `content` retention configurable; PDFs in local FS only; no provider secrets needed (Ollama).
- Right-to-erasure: cascade hard-delete by tenant/corpus; audit the deletion.
- **No secrets in DB:** `provider_configs.secret_ref` points to env/secret-manager; keys never persisted in rows.

## 6. Migrations
Alembic; one migration per schema change; forward-only in prod with reversible downgrades in dev; seed script for local demo corpus.

*Changes logged in `changelog.md`.*
