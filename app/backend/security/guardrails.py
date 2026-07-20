"""Security guardrails — input sanitization, prompt injection detection,
jailbreak protection, and output validation.

Applied as FastAPI middleware and directly in route handlers.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ── Prompt injection patterns ────────────────────────────────────────────────

_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bignore\s+(previous|prior|all|above|earlier)\s+instructions\b", re.I),
    re.compile(r"\byou\s+are\s+now\b", re.I),
    re.compile(r"\bact\s+as\s+(a\s+)?(different|another|new|evil|unrestricted)\b", re.I),
    re.compile(r"\bforget\s+(everything|all|your)\b", re.I),
    re.compile(r"\bsystem\s*prompt\b", re.I),
    re.compile(r"\b<\s*\|?\s*system\s*\|?\s*>", re.I),
    re.compile(r"\bINST\b"),
    re.compile(r"\bsudo\s+mode\b", re.I),
    re.compile(r"\bdeveloper\s+mode\b", re.I),
    re.compile(r"\bjailbreak\b", re.I),
    re.compile(r"\bDAN\b"),  # "Do Anything Now" jailbreak
    re.compile(r"\bpretend\s+(you\s+)?(have\s+no|are\s+not|don.t\s+have)\b", re.I),
    re.compile(r"\breveal\s+(your|the)\s+(system|hidden|secret)\s+prompt\b", re.I),
]

# ── Off-topic / abuse patterns ───────────────────────────────────────────────

_OFFTOPIC_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(hack|crack|exploit|malware|ransomware|virus|trojan)\b", re.I),
    re.compile(r"\b(generate|write|create)\s+.*(essay|story|poem|lyrics|code)\s+about\s+(?!research)", re.I),
]

# ── Chunk sanitization ───────────────────────────────────────────────────────

_CHUNK_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(previous|prior|all)\s+instructions", re.I),
    re.compile(r"<\s*\|?\s*system\s*\|?\s*>", re.I),
    re.compile(r"\[INST\]", re.I),
    re.compile(r"<<SYS>>", re.I),
    re.compile(r"\byou\s+are\s+now\s+a", re.I),
    re.compile(r"new\s+instructions?:", re.I),
]


class GuardrailResult:
    def __init__(self, blocked: bool, reason: str = "", category: str = ""):
        self.blocked = blocked
        self.reason = reason
        self.category = category

    def to_dict(self) -> dict:
        return {"blocked": self.blocked, "reason": self.reason, "category": self.category}


def check_query(question: str) -> GuardrailResult:
    """Validate a user query before sending it to the pipeline."""
    if not question or not question.strip():
        return GuardrailResult(True, "Empty query", "validation")

    if len(question) > 2000:
        return GuardrailResult(True, "Query exceeds 2000 character limit", "validation")

    for pat in _INJECTION_PATTERNS:
        if pat.search(question):
            logger.warning("Prompt injection attempt blocked: %r", question[:100])
            return GuardrailResult(True, "Query violates usage policy", "injection")

    return GuardrailResult(False)


def sanitize_chunk_text(text: str) -> str:
    """Remove prompt injection patterns embedded in PDF content."""
    for pat in _CHUNK_INJECTION_PATTERNS:
        if pat.search(text):
            logger.warning("Injection pattern found in chunk, redacting.")
            text = pat.sub("[REDACTED]", text)
    return text


def check_output(answer: str) -> GuardrailResult:
    """Validate LLM output before returning to the user."""
    if not answer or not answer.strip():
        return GuardrailResult(True, "Empty response from model", "output")

    # Flag if model appears to have been jailbroken (reveals system prompt)
    if re.search(r"my\s+system\s+prompt\s+is", answer, re.I):
        logger.warning("Output guardrail: model may have revealed system prompt")
        return GuardrailResult(True, "Response blocked by output filter", "output")

    return GuardrailResult(False)


def sanitize_filename(filename: str) -> str:
    """Sanitize an uploaded filename to prevent path traversal."""
    # Remove any path separators and null bytes
    filename = re.sub(r"[/\\:\*\?\"\<\>\|\x00]", "_", filename)
    filename = filename.lstrip(".")
    # Limit length
    if len(filename) > 255:
        stem = filename[:250]
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        filename = f"{stem}.{ext}" if ext else stem
    return filename or "unnamed"


def validate_pdf_magic_bytes(content: bytes) -> bool:
    """Check that uploaded file is actually a PDF by its magic bytes."""
    return content[:4] == b"%PDF"


# ── SSRF protection ──────────────────────────────────────────────────────────

def is_public_https_url(url: str) -> bool:
    """True only if ``url`` is HTTPS and its host resolves entirely to public
    (globally-routable) IP addresses. Blocks server-side request forgery to
    loopback/private/link-local/metadata endpoints (e.g. 127.0.0.1:11434,
    169.254.169.254, 10.x, 192.168.x)."""
    import ipaddress
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443,
                                   proto=socket.IPPROTO_TCP)
        if not infos:
            return False
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


def is_localhost_host(host: str) -> bool:
    """True if ``host`` is loopback/localhost — the only target the Ollama
    connectivity test is allowed to reach (prevents internal port scanning)."""
    import ipaddress
    from urllib.parse import urlparse

    h = host if "//" in host else f"//{host}"
    name = urlparse(h).hostname or host
    if name in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False
