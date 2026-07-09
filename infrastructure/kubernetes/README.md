# kubernetes (cloud SaaS)

Manifests (step 15): Deployments for `web`, `api`, `rag-service`, `ai-service`,
`evaluation-service` (stateless, HPA-enabled); Services; Ingress + WAF; secrets
sourced from the cloud provider's secret manager (never in manifests);
managed Postgres(+pgvector) and Redis referenced via env. Kustomize overlays per
environment (dev/staging/prod).
