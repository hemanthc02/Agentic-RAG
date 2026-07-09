# terraform (multi-cloud)

Modules (step 15) per target — AWS / Azure / GCP:
- managed PostgreSQL with pgvector, managed Redis, object storage (S3/Blob/GCS),
  networking/VPC, container runtime (EKS/AKS/GKE or serverless containers),
  secret manager wiring, IAM least-privilege.
Remote state per environment; `terraform plan` gated in CI before apply.
