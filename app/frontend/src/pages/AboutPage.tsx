import { Fragment } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight, BookOpen, Brain, Search, ShieldCheck } from "lucide-react";
import { useStore } from "../store/useStore";

const AGENTS = [
  {
    icon: Brain,
    name: "Planner",
    step: "01",
    desc: "Analyses the question's complexity. If it contains multiple sub-queries, it decomposes it into 1–3 focused sub-questions using an LLM call. Simple questions pass through unchanged.",
    detail: "Uses temperature=0 for deterministic decomposition. Returns JSON. Falls back to the original question if the LLM fails.",
  },
  {
    icon: Search,
    name: "Retriever (CRAG)",
    step: "02",
    desc: "Searches the FAISS vector index for each sub-question. Implements Corrective RAG: if the top chunk similarity is below the threshold (0.5), rewrites the query and retries once.",
    detail: "Embedder: all-MiniLM-L6-v2 (384-dim). Index: flat L2 up to 5K chunks, then IVF. Per-corpus indexes stored in data/corpora/{id}/.",
  },
  {
    icon: BookOpen,
    name: "Synthesizer",
    step: "03",
    desc: "Writes a grounded answer using ONLY the retrieved chunks. Every factual claim must have an inline [N] citation. On revision passes, failed claims are called out explicitly.",
    detail: "System prompt enforces citation discipline. Uses temperature=0.1 for slight creative latitude. Max 1024 tokens.",
  },
  {
    icon: ShieldCheck,
    name: "Verifier (NLI)",
    step: "04",
    desc: "The novelty: every cited sentence is scored by a cross-encoder NLI model (DeBERTa-v3-base). Scores below the threshold (0.6) are flagged and trigger a revision pass (max 2).",
    detail: "If DeBERTa is not loaded, falls back to LLM-based faithfulness estimation. Scores: ≥0.8 green, ≥0.6 amber, <0.6 red.",
  },
];

const STACK = [
  { label: "Embeddings", value: "all-MiniLM-L6-v2 · 384-dim · CPU-friendly" },
  { label: "Vector index", value: "FAISS flat-L2 / IVF · per-corpus" },
  { label: "NLI model", value: "cross-encoder/nli-deberta-v3-base" },
  { label: "Orchestration", value: "LangGraph 0.2 · StateGraph" },
  { label: "Online LLM", value: "Groq · Llama 4 Scout 17B" },
  { label: "Offline LLM", value: "Ollama · Phi-3 mini (on-device)" },
  { label: "Chunking", value: "Sentence-based · 2048 chars · 256 overlap" },
  { label: "Database", value: "SQLite · bcrypt · JWT (24 h TTL)" },
];

export default function AboutPage() {
  const token = useStore((s) => s.token);

  return (
    <div className="min-h-[100dvh] bg-zinc-50 text-zinc-900">
      <header className="border-b border-zinc-200/60 bg-white">
        <nav className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            VeritasRAG
          </Link>
          <Link
            to={token ? "/app" : "/"}
            className="btn-ghost text-sm py-2 px-4 inline-flex items-center gap-1.5 active:scale-[0.98] transition"
          >
            <ArrowLeft className="w-4 h-4" /> {token ? "Back to app" : "Back"}
          </Link>
        </nav>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-14">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 transition mb-8"
          >
            <ArrowLeft className="w-4 h-4" /> Home
          </Link>

          <h1 className="text-4xl font-bold tracking-tight mb-4">How VeritasRAG works</h1>
          <p className="text-zinc-500 text-lg mb-12 leading-relaxed max-w-[65ch]">
            A four-agent assembly line where each agent has exactly one job.
            The Verifier — using a dedicated NLI model — is the system's novelty:
            no existing multi-agent RAG system (SQuAI, MA-RAG) has a per-claim
            citation faithfulness checker.
          </p>

          {/* Pipeline diagram */}
          <div className="flex items-center gap-2 mb-12 flex-wrap">
            {["Planner", "Retriever", "Synthesizer", "Verifier"].map((n, i) => (
              <Fragment key={n}>
                <span className="bg-brand-50 border border-brand-200 text-brand-700 text-sm font-medium px-3 py-1.5 rounded-lg">
                  {n}
                </span>
                {i < 3 && <ArrowRight className="w-4 h-4 text-zinc-400" />}
              </Fragment>
            ))}
            <span className="text-zinc-400 text-sm ml-1">(revise up to 2 times)</span>
          </div>

          {/* Agent cards */}
          <div className="flex flex-col gap-6 mb-14">
            {AGENTS.map((a) => (
              <div key={a.name} className="card p-6">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-zinc-400 font-mono tabular-nums text-sm">{a.step}</span>
                  <span className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-200 flex items-center justify-center">
                    <a.icon className="w-4 h-4 text-brand-700" />
                  </span>
                  <h3 className="text-lg font-semibold tracking-tight">{a.name}</h3>
                </div>
                <p className="text-zinc-900 mb-2 leading-relaxed">{a.desc}</p>
                <p className="text-zinc-500 text-sm leading-relaxed">{a.detail}</p>
              </div>
            ))}
          </div>

          {/* Technical details */}
          <h2 className="text-2xl font-bold tracking-tight mb-6">Technical stack</h2>
          <div className="grid md:grid-cols-2 gap-4 mb-14">
            {STACK.map((r) => (
              <div key={r.label} className="card p-4 flex gap-3">
                <span className="text-zinc-500 text-sm font-medium w-32 flex-shrink-0">{r.label}</span>
                <span className="text-zinc-900 text-sm">{r.value}</span>
              </div>
            ))}
          </div>

          <div className="flex gap-4">
            <Link to="/register" className="btn-primary active:scale-[0.98] transition">
              Get started
            </Link>
            <Link to="/" className="btn-ghost active:scale-[0.98] transition">
              Home
            </Link>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
