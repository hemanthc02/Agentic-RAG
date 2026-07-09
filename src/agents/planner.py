"""Planner agent: decomposes a complex question into sub-questions."""

from __future__ import annotations

import json
import logging
import re
import time

import config
from src.agents.state import AgentState
from src.llm_backend import get_backend

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a research question planner. Decompose the question into 1–3 focused "
    "sub-questions whose answers together fully address it. "
    "For a simple, already-specific question return just that question unchanged. "
    "Respond with valid JSON ONLY — no prose, no markdown fences."
)

_USER_TMPL = (
    'Question: "{question}"\n\n'
    'Return: {{"sub_questions": ["...", "..."]}}\n'
    'If already focused: {{"sub_questions": ["{question}"]}}'
)


def planner_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    question = state["question"]

    try:
        llm = get_backend(mode=state["mode"], provider=state["provider"])
        prompt = _SYSTEM + "\n\n" + _USER_TMPL.format(question=question)
        raw = llm.generate(prompt, temperature=0.0, max_tokens=256)

        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
            sub_qs = [q.strip() for q in data.get("sub_questions", []) if q.strip()]
        else:
            sub_qs = []
    except Exception as exc:
        logger.warning("Planner LLM failed: %s — falling back to original question", exc)
        sub_qs = []

    if not sub_qs:
        sub_qs = [question]
    sub_qs = sub_qs[:3]  # max 3

    elapsed = int((time.perf_counter() - t0) * 1000)
    log = state.get("stage_log", [])
    log.append({"stage": "planner", "sub_questions": sub_qs, "latency_ms": elapsed})

    return {"sub_questions": sub_qs, "stage_log": log}
