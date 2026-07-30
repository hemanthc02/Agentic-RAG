"""FastAPI application — Multi-Agent RAG with authentication.

Run from repo root:
    uvicorn app.backend.main:app --reload --port 8000

API docs: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from app import __version__ as APP_VERSION  # noqa: E402
from app.backend import database as db  # noqa: E402
from app.backend.routers import (  # noqa: E402
    auth_router,
    conversations_router,
    documents_router,
    query_router,
    research_router,
    settings_router,
    system_router,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Multi-Agent RAG API",
    version=APP_VERSION,
    description=(
        "Agentic RAG with Planner → Retriever (CRAG) → Synthesizer → NLI Verifier. "
        "Two models: Groq · Llama 4 Scout 17B (online) and Ollama · Phi-3 mini (offline)."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:3000", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(conversations_router.router)
app.include_router(documents_router.router)
app.include_router(query_router.router)
app.include_router(research_router.router)
app.include_router(settings_router.router)
app.include_router(system_router.router)


@app.on_event("startup")
def startup():
    db.init_db()
    logger.info("Database initialised at %s", db.DB_PATH)

    # Pre-warm the shared embedding model in the background so the first
    # query/viva/guide request doesn't pay the ~1-2 min cold model load.
    import threading

    def _warm():
        try:
            from src.retrieval import get_shared_embedder
            get_shared_embedder()
            logger.info("Embedding model pre-warmed and shared")
        except Exception as exc:
            logger.warning("Embedder pre-warm failed (will load on demand): %s", exc)
        try:
            # Pre-load the NLI verifier model too, so the first query's
            # verification step doesn't pay the model-load + online-check cost.
            from src.agents.verifier import _get_nli
            _get_nli()
            logger.info("NLI verifier model pre-warmed")
        except Exception as exc:
            logger.warning("NLI pre-warm failed (will load on demand): %s", exc)

    threading.Thread(target=_warm, daemon=True).start()


class SPAStaticFiles(StaticFiles):
    """Serve the built SPA; fall back to index.html for client-side routes
    (e.g. /app/viva) so hard refreshes and deep links work."""

    async def get_response(self, path: str, scope):
        from starlette.exceptions import HTTPException as StarletteHTTPException
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


_FRONTEND_DIST = _REPO_ROOT / "app" / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
    logger.info("Serving frontend from %s", _FRONTEND_DIST)


if __name__ == "__main__":
    import os

    import uvicorn

    # Azure App Service (and most PaaS hosts) inject the port to listen on via
    # the PORT env var and require binding all interfaces. Locally, with no PORT
    # set, this still serves on 8000. Start on a host with:
    #     python -m app.backend.main
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
