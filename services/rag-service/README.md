# services/rag-service — agentic pipeline

The LangGraph `StateGraph`: Planner → Retriever → Synthesizer → Verifier →
(conditional revise) → END. LLM-using nodes call `services/ai-service` via the
`LLMProvider` port; Retriever search (MiniLM + pgvector/FAISS) and Verifier
(DeBERTa-v3-MNLI) run locally in both modes.

The research Weeks 1–3 modules (`src/ingestion`, `src/retrieval`, agents,
`graph`) migrate here as the production pipeline, replacing the Phase-0
`app/backend` MockPipeline behind the same port. Core novelty: the independent
NLI verifier + bounded reject-and-revise loop. Built in step 12.
