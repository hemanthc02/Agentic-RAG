# Product Vision
**Project:** VeritasRAG — Verifiable Agentic Research Assistant
**Phase:** 3 (Execution order step 3) · **Version:** 1.0 · **Date:** 2026-06-07
**Depends on:** `research-analysis.md`, `gap-analysis.md`

> Working product name **VeritasRAG** ("truth-RAG") used throughout the design docs; the codebase/repo remains `multi-agent-rag`. Rename is cosmetic and configurable.

## 1. Vision statement
**Make AI answers over your own documents *provably* trustworthy — every claim carries a machine-verified evidence link — on hardware you already own, with data you fully control.**

Where most RAG tools optimise for fluent answers, VeritasRAG optimises for *defensible* answers: each sentence is checked against its cited evidence by an independent model, low-support claims are repaired or flagged, and the whole pipeline can run fully on-device for regulated or air-gapped use.

## 2. The wedge (why we win where others don't)
Cloud incumbents (Scopus AI, Harvey, generic RAG copilots) are fast and broad but: (a) closed/cloud-only, (b) display citations without *verifying* them, (c) unusable where data cannot leave the building. SQuAI (the closest research system) scales to millions of papers but shows supporting sentences as *display*, not as a *verification gate*, and has no air-gapped story.

**Our wedge:** privacy-first, *verification-first* research QA for teams who must prove their citations and control their data — pharma, legal, government, and the long tail of researchers without GPUs.

## 3. Target personas
- **Dr. Priya — translational researcher (pharma R&D).** Reviews 50+ papers per question; cannot send unpublished compound data to a cloud API; needs an audit trail of which evidence supports each conclusion.
- **Marcus — litigation associate (legal tech).** Drafts briefs from case-law PDFs; a single fabricated citation is a sanction risk; needs verifiable, traceable attributions.
- **Aïsha — M.Tech/PhD student.** No GPU, no budget; needs reproducible literature review and a defensible methodology for her own thesis.
- **Sam — research-platform admin.** Manages corpora, model providers, usage, and compliance for a department or company.

## 4. Jobs To Be Done
1. "When I ask a question of my paper library, give me an answer where I can *trust and trace* every citation." 
2. "When my data is sensitive, let me run everything on-device and prove nothing left." 
3. "When I cite something downstream, show me *how confident* the system is per claim so I can reject what's weak." 
4. "As an admin, let me control providers, costs, access, and keep an audit log."

## 5. Product principles
1. **Verification over fluency.** A flagged uncertain answer beats a confident wrong one.
2. **Honest privacy.** Claims are always mode-specific and precise; never "fully local" without qualification.
3. **Reproducible by default.** Runs on a 16 GB CPU laptop; no fine-tuning; free/open-source core.
4. **Provider-agnostic.** No lock-in; swap Gemini/OpenRouter/NVIDIA NIM/Ollama by config.
5. **Explainability is the UX.** Per-claim supportedness + reliance, surfaced and actionable.

## 6. Success metrics (product + research)
- **Research:** ≥ 80% of claims at NLI supportedness ≥ 0.6; ≥ 10% RAGAS faithfulness gain over vanilla RAG (paired t-test p<0.05); verifier precision/recall vs human labels reported.
- **Product (north-star):** *Verified-answer rate* = % of answered questions where every claim passes verification or is explicitly flagged. Secondary: weekly active researchers, corpora indexed, time-to-first-verified-answer, retention.
- **Trust:** measured reduction in user-rejected citations over time; audit-log completeness.

## 7. Three-horizon roadmap
- **H1 (now, research + MVP):** CPU pipeline, independent NLI verifier + reject/revise, supportedness vs reliance, dual backend, single-tenant web app, reproducible benchmark, paper draft.
- **H2 (SaaS):** multi-tenant, Postgres+pgvector+Redis, auth/RBAC, provider abstraction (NIM/OpenRouter/Gemini), usage metering, admin panel, observability.
- **H3 (enterprise):** SSO/SAML, on-prem/air-gapped distribution, eval-as-a-service, team workspaces, compliance (SOC2 path), API platform.

## 8. Non-goals (this iteration)
Multimodal (figures/tables as images), multilingual, real-time web search, LLM fine-tuning, mobile-native apps, replacing the researcher's own reading.
