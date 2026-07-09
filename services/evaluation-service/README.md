# services/evaluation-service — research evaluation

Runs the benchmark comparing (baseline / multi-agent / +verifier) × (cloud /
local). Metrics: RAGAS (faithfulness, answer relevance, context precision/recall),
**independent NLI supportedness** (ours), latency, and verifier precision/recall
vs human labels. Reports paired t-test (p<0.05) per `documentcreation/testing-plan.md`.
The 20-question benchmark is built **blind + adversarial** (validity threats in
`research-analysis.md` §9). Built in step 14.
