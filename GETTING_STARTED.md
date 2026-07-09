# Getting Started — VeritasRAG

A step-by-step guide to run the Multi-Agent RAG application on your local machine.

---

## What you need

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10 or 3.11 | 3.12 not yet tested |
| Node.js | 18 or later | For the React frontend |
| Git | any | To clone the repo |
| Groq API key **or** Ollama | — | Pick one (see Step 3) |

---

## Step 1 — Clone and enter the project

```bash
git clone <your-repo-url>
cd multi-agent-rag
```

---

## Step 2 — Set up Python environment

```bash
# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# Mac / Linux:
source .venv/bin/activate

# Install CPU-only PyTorch first (important — prevents a 3 GB CUDA download)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install all other dependencies
pip install -r requirements.txt
```

> The first install downloads ~500 MB of models (MiniLM embeddings + DeBERTa NLI).  
> This is a one-time download — they cache in `~/.cache/huggingface/`.

---

## Step 3 — Choose your LLM backend

Pick **one** of the two options below. You can switch anytime by editing `.env`.

### Option A — Groq (cloud, recommended for speed)

1. Sign up free at [console.groq.com](https://console.groq.com) → copy your API key
2. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and fill in your key:
   ```
   LLM_MODE=cloud
   LLM_PROVIDER=groq
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
   ```

> Your PDFs stay on your device. Only the question + retrieved text excerpts are sent to Groq over HTTPS.

---

### Option B — Phi-3 mini via Ollama (fully local, nothing leaves your device)

1. Download and install Ollama from [ollama.com](https://ollama.com)
2. Pull the Phi-3 mini model (~2.2 GB, one-time):
   ```bash
   ollama pull phi3:mini
   ```
3. Copy the environment template and configure:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and set:
   ```
   LLM_MODE=local
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=phi3:mini
   ```
4. Keep Ollama running in a separate terminal before starting the app:
   ```bash
   ollama serve
   ```

---

## Step 4 — Add your PDFs

Drop PDF files (research papers, documents) into the `data/pdfs/` folder:

```
multi-agent-rag/
└── data/
    └── pdfs/
        ├── paper1.pdf
        ├── paper2.pdf
        └── ...
```

> Aim for 10–50 PDFs. The folder is gitignored — your files won't be committed.

---

## Step 5 — Build the search index

This reads all PDFs, chunks them, and builds the FAISS vector index. Run once (or again whenever you add new PDFs):

```bash
python -m src.retrieval --build
```

You should see output like:
```
Indexed 1,243 chunks from 12 documents → data/corpora/default/
```

---

## Step 6 — Test from the command line

```bash
# Quick single query (no UI needed)
python -m src.graph "What is the difference between CRAG and Self-RAG?"

# Run the baseline (vanilla RAG, for comparison)
python -m src.baseline "What is retrieval-augmented generation?"

# Run the full evaluation comparison
python -m src.evaluation --compare
```

---

## Step 7 — Run the full application (FastAPI + React UI)

Open **two terminals**, both with the virtual environment active.

**Terminal 1 — Backend API:**
```bash
cd app/backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see: `Uvicorn running on http://0.0.0.0:8000`

**Terminal 2 — Frontend UI:**
```bash
cd app/frontend
npm install          # first time only
npm run dev
```

You should see: `Local: http://localhost:5173`

Open your browser at **http://localhost:5173**

---

## Quick reference — all useful commands

| What | Command |
|---|---|
| Activate venv (Windows) | `.venv\Scripts\activate` |
| Activate venv (Mac/Linux) | `source .venv/bin/activate` |
| Build index | `python -m src.retrieval --build` |
| Run a query (CLI) | `python -m src.graph "your question"` |
| Run baseline query | `python -m src.baseline "your question"` |
| Run evaluation | `python -m src.evaluation --compare` |
| Start backend | `cd app/backend && uvicorn main:app --reload` |
| Start frontend | `cd app/frontend && npm run dev` |
| Start Ollama (if using local mode) | `ollama serve` |

---

## Troubleshooting

**`GROQ_API_KEY not set` error**  
→ Make sure `.env` exists and has your key. The `.env.example` file is just a template — it does not work on its own.

**`Connection refused` on Ollama**  
→ Run `ollama serve` in a separate terminal before starting the app.

**`ModuleNotFoundError`**  
→ Your virtual environment is not activated. Run `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux) first.

**Index not found error**  
→ Run `python -m src.retrieval --build` to create the index. Check that PDFs are in `data/pdfs/`.

**Frontend shows blank page or CORS error**  
→ Make sure the backend is running on port 8000 before opening the frontend.

**Out of memory**  
→ The app is designed for CPU-only machines with 8 GB+ RAM. Close other applications and try again.

---

## Architecture overview

```
Your question
     │
     ▼
  Planner  ──── breaks question into sub-questions
     │
     ▼
 Retriever ──── FAISS similarity search over your PDFs
     │          (rewrites query if score < 0.50)
     ▼
Synthesizer ── LLM generates cited answer
     │          (Groq Llama 4 Scout  OR  Ollama Phi-3 mini)
     ▼
  Verifier ──── DeBERTa NLI checks every citation
     │          (retries up to 2× if faithfulness < 0.60)
     ▼
Verified Answer (faithfulness score attached)
```

Embeddings (MiniLM), FAISS index, and DeBERTa NLI verifier all run **locally on CPU** in both modes.
