# infrastructure

- **docker/** — `docker-compose.yml` (local + air-gapped: postgres+pgvector, redis,
  optional ollama, api, web) and per-service Dockerfiles (`api.Dockerfile`,
  `web.Dockerfile` — added in step 15).
- **kubernetes/** — manifests for cloud SaaS: stateless web/api/rag/ai/eval
  Deployments + HPA, Services, Ingress + WAF, secrets via cloud secret managers.
- **terraform/** — modules per target (AWS / Azure / GCP): managed Postgres
  (pgvector), Redis, object storage, networking.

Deployment targets: local development, AWS, Azure, GCP. Built in step 15
(`documentcreation/deployment-plan.md`).
