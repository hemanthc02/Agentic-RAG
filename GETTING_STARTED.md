# Getting Started — VeritasRAG

Run the app in one step, or set it up manually. Full illustrated guides are in
[`../documentation/`](../documentation/) (PDFs).

---

## What you need

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 – 3.13 | Required |
| Ollama | latest | Only for **offline** mode (`ollama pull phi4-mini`) |
| Anthropic API key | — | Only for **online** mode (`sk-ant-…`, from console.anthropic.com) |
| Internet | — | First-time setup + online mode |
| RAM / Disk | ~8 GB / ~6 GB free | Models run on CPU |

> Node.js is **not** required — the web interface ships pre-built.

---

## Easiest — one click

Double-click **`START.bat`** (in this folder).

- **First run:** creates the environment, installs dependencies, downloads the AI
  models, prepares `.env`, and starts the app. ~10–20 minutes; needs internet.
- **After that:** just starts the app and opens **http://localhost:8000**.

Keep the console window open (that's the server). Press **Ctrl+C** to stop.

---

## Online mode (Claude) — add your key

Open `.env` in this folder and set:

```
ANTHROPIC_API_KEY=sk-ant-your_key_here
```

Then restart `START.bat`. The online writer is **Claude Sonnet 5**.
(Offline mode uses the local **phi4-mini** model and needs no key.)

---

## Manual setup (alternative)

```bash
python -m venv .venv
.venv\Scripts\activate                 # Windows  (Mac/Linux: source .venv/bin/activate)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python bootstrap_env.py                 # writes .env with a secure JWT secret
# add ANTHROPIC_API_KEY to .env for online mode
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000, create an account, create a PDF library, upload PDFs,
and ask questions.

---

## Using the app

- **Ask** — upload PDFs and ask; answers show a **Retrieved from** source list
  (PDF + page per citation) and per-claim green/red verification cards.
- **Online / Offline** toggle (top-right) — cloud (fast) vs on-device (private).
- **Research guide** — pick a project and get gap-analysis / methodology help.
- **Viva** — dynamic exam questions + scoring from your own papers.
- **Papers** — search and import new papers (online).
- **Agents** — a visual map of how the pipeline works.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Python not found" | Install Python 3.10–3.13, tick "Add to PATH", re-run `START.bat` |
| Online query fails (401) | Set a valid `ANTHROPIC_API_KEY` in `.env` |
| Indexing fails on a new PC | Needs internet on first run to download the models (setup does this) |
| Offline is slow | Normal on CPU; keep other apps closed |
| Vague in-app error | Make sure the `START.bat` console window is still open |

More detail: `../documentation/01_Installation_and_Setup.pdf` and `02_How_to_Run.pdf`.
