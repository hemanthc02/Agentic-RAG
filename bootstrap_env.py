"""Ensure multi-agent-rag/.env exists with a real (non-placeholder) JWT secret.

Run automatically by setup.bat. Safe to run repeatedly — it only fills in what
is missing and never overwrites a real JWT_SECRET you already set.
"""
import re
import secrets
from pathlib import Path

here = Path(__file__).resolve().parent
env = here / ".env"
example = here / ".env.example"

if env.exists():
    text = env.read_text(encoding="utf-8")
elif example.exists():
    text = example.read_text(encoding="utf-8")
else:
    text = ""


def ensure(txt: str, key: str, val: str) -> str:
    if re.search(rf"(?m)^{key}=.*$", txt):
        return re.sub(rf"(?m)^{key}=.*$", f"{key}={val}", txt)
    sep = "" if (not txt or txt.endswith("\n")) else "\n"
    return f"{txt}{sep}{key}={val}\n"


# Only generate a secret if there isn't already a real one.
if not re.search(r"(?m)^JWT_SECRET=\S+", text):
    text = ensure(text, "JWT_SECRET", secrets.token_urlsafe(48))
if not re.search(r"(?m)^JWT_ACCESS_TTL_SECONDS=\S+", text):
    text = ensure(text, "JWT_ACCESS_TTL_SECONDS", "28800")
text = ensure(text, "OLLAMA_MODEL", "phi4-mini")
# HF_HUB_OFFLINE must be 0 so the embedding & verifier models can DOWNLOAD on a
# fresh machine the first time (they are cached afterwards). Forcing 1 here was
# the cause of "indexing fails on another computer" — the model couldn't load.
text = ensure(text, "HF_HUB_OFFLINE", "0")

env.write_text(text, encoding="utf-8")
print(f".env is ready at {env}")
if not re.search(r"(?m)^GROQ_API_KEY=gsk_\S+", text):
    print("NOTE: add your GROQ_API_KEY (starts with gsk_) to .env for ONLINE mode.")
