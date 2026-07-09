# Testing Plan
**Phase:** 7 · **Version:** 0.1 (PENDING — outline only) · **Date:** 2026-06-07

> STATUS: **Not yet authored.** Outline below; reflects the validity threats in `research-analysis.md` §9.

## Planned contents
- **Unit tests** — per agent (planner/retriever/synthesizer/verifier), repositories, services; pytest; happy-path + edge cases.
- **Integration tests** — full graph incl. the reject/revise loop; backend API; provider abstraction (mock + live).
- **Regression test** — a known *unfaithful* claim that the verifier must reject (guards the core contribution).
- **Evaluation harness (the science):** 20-question benchmark made **adversarial + blind**; pre-registered questions; include multi-hop and "answer-not-in-corpus" cases; report RAGAS + independent NLI + **human inter-annotator agreement** on a subset; verifier **precision/recall vs human labels**; calibration of the threshold.
- **Performance tests** — latency per mode incl. worst-case under max retries; memory ceiling (< 11 GB).
- **Non-functional** — security (authZ, secrets), accessibility (frontend), load (concurrent users).
- **CI gates** — coverage thresholds; no merge on failing tests.

*Updates logged in `changelog.md`.*
