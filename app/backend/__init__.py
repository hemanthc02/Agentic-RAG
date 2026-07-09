"""FastAPI backend for the Multi-Agent RAG system.

Exposes JSON APIs consumed by the React frontend. The runtime pipeline is
pluggable (see ``pipeline.py``): a MockPipeline is used until the real LangGraph
pipeline (Weeks 1-3) is implemented, at which point it drops in behind the same
``Pipeline`` protocol without changing the API surface.
"""
