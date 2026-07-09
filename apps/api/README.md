# apps/api — FastAPI gateway

Planned layout (clean architecture; built in step 11):
```
api/
├── domain/         entities, value objects, ports (LLMProvider, VectorStore, repos)
├── application/    use cases: AskQuestion, IngestCorpus, RunEvaluation; DTOs
├── infrastructure/ SQLAlchemy repos, ai-service adapter, pgvector store, event bus
├── interface/      FastAPI routers (/api/v1/*), deps (DI), middleware (auth, rate-limit)
├── alembic/        migrations (see documentcreation/database-design.md)
└── tests/          unit (domain) + integration (repos) + api
```
Implements `documentcreation/api-design.md` and `security-design.md`.
Depends on `services/ai-service` and `services/rag-service` via ports.
