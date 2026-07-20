"""Robust JSON extraction from LLM text output.

Different LLMs format structured output differently — some wrap JSON in
markdown fences, add a preamble ("Here is the JSON:"), or truncate mid-object
when they hit the token limit. This module extracts and, where possible,
repairs the JSON so the agents don't fail on cosmetic formatting differences.
"""

from __future__ import annotations

import json
import re


def extract_json(text: str) -> dict | list:
    """Best-effort parse of a JSON object/array embedded in ``text``.

    Handles: markdown code fences, leading/trailing prose, and truncated output
    (closes unterminated strings/brackets). Raises ValueError if no JSON-like
    structure is found at all.
    """
    if not text or not text.strip():
        raise ValueError("empty LLM output")

    s = text.strip()
    # Strip surrounding markdown code fences (```json ... ``` or ``` ... ```).
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```\s*$", "", s)

    # Locate the first opening brace/bracket.
    start = next((i for i, ch in enumerate(s) if ch in "{["), None)
    if start is None:
        raise ValueError("no JSON object/array found in output")

    candidate = _slice_balanced(s, start)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return json.loads(_repair(candidate))


def _slice_balanced(s: str, start: int) -> str:
    """Return s[start:] trimmed to the matching closing bracket if found,
    otherwise the remainder (to be repaired)."""
    opener = s[start]
    closer = "}" if opener == "{" else "]"
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
    return s[start:]  # unbalanced (truncated) — repair() will close it


def _repair(candidate: str) -> str:
    """Close an unterminated string and any open brackets (truncated output)."""
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in candidate:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in "}]" and stack:
                stack.pop()

    fixed = candidate
    if in_str:
        fixed += '"'
    # Drop a trailing comma or partial key that can't be completed.
    fixed = re.sub(r",\s*$", "", fixed.rstrip())
    while stack:
        fixed += stack.pop()
    return fixed
