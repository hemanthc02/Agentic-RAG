"""Azure AI Search vector store.

Free tier = 3 indexes / 50 MB, so the whole app shares ONE index and every
document carries a ``corpus_id`` field; all reads/writes/deletes are scoped with
an OData ``corpus_id eq '...'`` filter. Embeddings are still produced locally by
the shared MiniLM model (no Azure OpenAI needed) and pushed as raw vectors; the
NLI verifier is unchanged. All Azure SDK imports are lazy.
"""

from __future__ import annotations

import logging

import config
from src.ingestion import Chunk
from src.retrieval import RetrievalResult, get_shared_embedder

logger = logging.getLogger(__name__)

_client = None
_index_ready = False


def _odata_escape(value: str) -> str:
    """Escape a value for an OData filter literal (single quotes doubled)."""
    return value.replace("'", "''")


def _ensure_index() -> None:
    """Create the shared vector index once if it does not already exist."""
    global _index_ready
    if _index_ready:
        return
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    ic = SearchIndexClient(config.AZURE_SEARCH_ENDPOINT,
                           AzureKeyCredential(config.AZURE_SEARCH_KEY))
    if config.AZURE_SEARCH_INDEX in set(ic.list_index_names()):
        _index_ready = True
        return

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="corpus_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_id", type=SearchFieldDataType.String),
        SearchableField(name="text", type=SearchFieldDataType.String),
        SimpleField(name="source", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="page", type=SearchFieldDataType.Int32),
        SimpleField(name="section", type=SearchFieldDataType.String),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=config.EMBEDDING_DIM,
            vector_search_profile_name="vprofile",
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
        profiles=[VectorSearchProfile(name="vprofile",
                                      algorithm_configuration_name="hnsw")],
    )
    ic.create_index(SearchIndex(name=config.AZURE_SEARCH_INDEX, fields=fields,
                                vector_search=vector_search))
    logger.info("Created Azure AI Search index '%s'", config.AZURE_SEARCH_INDEX)
    _index_ready = True


def _search_client():
    global _client
    if _client is None:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient

        if not (config.AZURE_SEARCH_ENDPOINT and config.AZURE_SEARCH_KEY):
            raise RuntimeError(
                "SEARCH_BACKEND=azure_search but AZURE_SEARCH_ENDPOINT / AZURE_SEARCH_KEY are not set"
            )
        _ensure_index()
        _client = SearchClient(config.AZURE_SEARCH_ENDPOINT, config.AZURE_SEARCH_INDEX,
                               AzureKeyCredential(config.AZURE_SEARCH_KEY))
    return _client


def _doc_key(corpus_id: str, chunk_id: str) -> str:
    # Azure Search document keys allow letters, digits, _, -, =. A uuid corpus_id
    # and a hex chunk_id are both safe; the pair is globally unique in the index.
    return f"{corpus_id}__{chunk_id}"


# --------------------------------------------------------------------------- #
# Write / delete
# --------------------------------------------------------------------------- #

def upsert_chunks(corpus_id: str, chunks: list[Chunk]) -> None:
    chunks = list(chunks)
    if not chunks:
        return
    vecs = get_shared_embedder().encode([c.text for c in chunks])
    docs = [
        {
            "id": _doc_key(corpus_id, c.chunk_id),
            "corpus_id": corpus_id,
            "chunk_id": c.chunk_id,
            "text": c.text,
            "source": c.source,
            "page": int(c.page),
            "section": getattr(c, "section", "") or "",
            "embedding": [float(x) for x in v],
        }
        for c, v in zip(chunks, vecs)
    ]
    client = _search_client()
    for i in range(0, len(docs), 1000):  # AI Search caps batches at 1000 docs
        client.upload_documents(docs[i:i + 1000])
    logger.info("Upserted %d chunks into Azure Search for corpus %s", len(docs), corpus_id)


def _delete_by_filter(odata_filter: str) -> None:
    client = _search_client()
    ids = [{"id": d["id"]}
           for d in client.search(search_text="*", filter=odata_filter,
                                  select="id", top=1000)]
    if ids:
        client.delete_documents(ids)


def delete_document(corpus_id: str, filename: str) -> None:
    _delete_by_filter(
        f"corpus_id eq '{_odata_escape(corpus_id)}' and source eq '{_odata_escape(filename)}'"
    )


def delete_corpus(corpus_id: str) -> None:
    _delete_by_filter(f"corpus_id eq '{_odata_escape(corpus_id)}'")


def corpus_has_docs(corpus_id: str) -> bool:
    client = _search_client()
    res = client.search(search_text="*",
                        filter=f"corpus_id eq '{_odata_escape(corpus_id)}'",
                        top=1, include_total_count=True)
    try:
        count = res.get_count()
        if count is not None:
            return count > 0
    except Exception:
        pass
    return any(True for _ in res)


# --------------------------------------------------------------------------- #
# Read — a store object mirroring src.retrieval.VectorStore.search()
# --------------------------------------------------------------------------- #

class AzureSearchStore:
    """Vector-search store for one corpus; ``.search`` mirrors VectorStore."""

    def __init__(self, corpus_id: str) -> None:
        self.corpus_id = corpus_id

    def search(self, query: str, k: int = config.TOP_K) -> list[RetrievalResult]:
        from azure.search.documents.models import VectorizedQuery

        qv = [float(x) for x in get_shared_embedder().encode([query])[0]]
        vq = VectorizedQuery(vector=qv, k_nearest_neighbors=k, fields="embedding")
        res = _search_client().search(
            search_text=None,
            vector_queries=[vq],
            filter=f"corpus_id eq '{_odata_escape(self.corpus_id)}'",
            top=k,
        )
        out: list[RetrievalResult] = []
        for d in res:
            chunk = Chunk(
                chunk_id=d.get("chunk_id", ""),
                text=d.get("text", ""),
                source=d.get("source", ""),
                page=int(d.get("page", 1) or 1),
                section=d.get("section", "") or "",
            )
            out.append(RetrievalResult(chunk=chunk, score=float(d.get("@search.score", 0.0))))
        return out
