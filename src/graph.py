"""Thin shim so the documented command ``python -m src.graph "..."`` works.

The real LangGraph pipeline lives in :mod:`src.agents.graph`. prompt.md §5
documents the entry point as ``python -m src.graph``; this module re-exports the
public API and forwards the CLI so both invocations behave identically.
"""

from __future__ import annotations

from src.agents.graph import get_pipeline, main, run

__all__ = ["run", "get_pipeline", "main"]


if __name__ == "__main__":
    main()
