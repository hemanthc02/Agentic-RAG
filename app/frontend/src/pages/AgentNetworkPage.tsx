import {
  Shield, GitBranch, Search, PenLine, ShieldCheck, ArrowRight, RotateCcw,
  Database, Cpu, Layers, FileText, Network,
} from "lucide-react";

/** Static architecture view — how the multi-agent pipeline answers a question.
 *  No backend calls: this is a "map" of the system for understanding & demos. */

const STAGES = [
  { key: "guard", name: "Guard", Icon: Shield, color: "bg-zinc-600" },
  { key: "planner", name: "Planner", Icon: GitBranch, color: "bg-brand-600" },
  { key: "retriever", name: "Retriever", Icon: Search, color: "bg-brand-600" },
  { key: "synth", name: "Synthesizer", Icon: PenLine, color: "bg-brand-600" },
  { key: "verifier", name: "Verifier", Icon: ShieldCheck, color: "bg-teal-600" },
];

const AGENTS = [
  {
    name: "Guard", Icon: Shield, layer: "Pre-filter", tint: "zinc",
    input: "The user's raw question",
    process: "Detects small-talk / off-topic questions with a fast meaning check against the library, before any heavy work.",
    output: "Either an instant honest reply, or a green light to continue",
    uses: "Embedding model (similarity)",
  },
  {
    name: "Planner", Icon: GitBranch, layer: "Orchestration", tint: "brand",
    input: "The question (once it passed the guard)",
    process: "Breaks a broad question into 1–3 focused sub-questions so each idea can be searched precisely.",
    output: "A short list of sub-questions",
    uses: "Language model (online or offline)",
  },
  {
    name: "Retriever", Icon: Search, layer: "Retrieval", tint: "brand",
    input: "The sub-questions",
    process: "Turns each into meaning-coordinates, searches the vector index, merges results round-robin, and rewrites a weak query once (CRAG).",
    output: "Ranked source passages, numbered [1] [2] [3]… with PDF + page",
    uses: "Embedding model + vector index",
  },
  {
    name: "Synthesizer", Icon: PenLine, layer: "Generation", tint: "brand",
    input: "The question + the numbered source passages",
    process: "Writes the answer using ONLY those passages, adding an inline [n] citation after every fact. Adds no outside knowledge.",
    output: "A draft answer with inline citations",
    uses: "Language model (online or offline)",
  },
  {
    name: "Verifier", Icon: ShieldCheck, layer: "Verification", tint: "teal",
    input: "The draft answer + the cited passages",
    process: "For each cited sentence, an entailment model checks whether the source truly supports it (windowed scoring); repairs wrong citations; loops back if unsupported.",
    output: "Per-claim faithfulness scores, a verified flag, or a revise signal",
    uses: "NLI (entailment) model — no online call",
  },
];

const LAYERS = [
  {
    name: "Data & Retrieval layer", Icon: Database, tint: "brand",
    items: ["PDF text extraction", "Sentence-aware chunking (~2,000 chars, overlap)", "Meaning-encoding (embeddings)", "Vector similarity index (per project)"],
  },
  {
    name: "Reasoning (agent) layer", Icon: Layers, tint: "teal",
    items: ["Guard — filters junk questions", "Planner — decomposes the question", "Retriever — finds evidence (CRAG)", "Synthesizer — writes the cited answer", "Verifier — proves each citation"],
  },
  {
    name: "Model layer", Icon: Cpu, tint: "zinc",
    items: ["Embedding model — meaning search (local)", "NLI model — citation checking (local)", "Online writer — cloud model (fast)", "Offline writer — on-device model (private)"],
  },
];

const tintCls = (t: string) =>
  t === "teal" ? "text-teal-700 bg-teal-50 border-teal-200"
  : t === "zinc" ? "text-zinc-700 bg-zinc-100 border-zinc-200"
  : "text-brand-700 bg-brand-50 border-brand-200";

export default function AgentNetworkPage() {
  return (
    <div className="h-full overflow-y-auto bg-canvas">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-start gap-3 mb-2">
          <span className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center flex-shrink-0">
            <Network className="w-5 h-5 text-white" strokeWidth={2} />
          </span>
          <div>
            <h1 className="text-xl font-semibold text-zinc-900 tracking-tight">Agent Network</h1>
            <p className="text-sm text-zinc-500">How the four agents turn a question into a verified answer — inputs, work, and outputs.</p>
          </div>
        </div>

        {/* Pipeline flow */}
        <div className="mt-6 bg-white border border-zinc-200/60 rounded-2xl p-5">
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-4">The pipeline</p>
          <div className="flex items-stretch gap-2 flex-wrap">
            {STAGES.map((s, i) => (
              <div key={s.key} className="flex items-center gap-2">
                <div className="flex flex-col items-center gap-1.5">
                  <div className={`w-14 h-14 rounded-2xl ${s.color} flex items-center justify-center`}>
                    <s.Icon className="w-6 h-6 text-white" strokeWidth={2} />
                  </div>
                  <span className="text-xs font-medium text-zinc-700">{s.name}</span>
                </div>
                {i < STAGES.length - 1 && (
                  <ArrowRight className="w-5 h-5 text-zinc-300 flex-shrink-0" strokeWidth={2.5} />
                )}
              </div>
            ))}
            <div className="flex items-center gap-2">
              <ArrowRight className="w-5 h-5 text-zinc-300" strokeWidth={2.5} />
              <div className="flex flex-col items-center gap-1.5">
                <div className="w-14 h-14 rounded-2xl bg-emerald-600 flex items-center justify-center">
                  <FileText className="w-6 h-6 text-white" strokeWidth={2} />
                </div>
                <span className="text-xs font-medium text-zinc-700">Answer</span>
              </div>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 w-fit">
            <RotateCcw className="w-3.5 h-3.5" strokeWidth={2} />
            Revision loop: if the Verifier finds an unsupported claim, the answer goes back to the Synthesizer and is re-checked (up to 2 times).
          </div>
        </div>

        {/* Agent detail cards */}
        <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mt-8 mb-3">What each agent does</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {AGENTS.map((a) => (
            <div key={a.name} className="bg-white border border-zinc-200/60 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <span className={`w-9 h-9 rounded-xl border flex items-center justify-center ${tintCls(a.tint)}`}>
                    <a.Icon className="w-4.5 h-4.5" strokeWidth={2} />
                  </span>
                  <h3 className="text-base font-semibold text-zinc-900">{a.name}</h3>
                </div>
                <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${tintCls(a.tint)}`}>{a.layer}</span>
              </div>
              <dl className="space-y-2 text-sm">
                <div className="flex gap-2">
                  <dt className="w-16 flex-shrink-0 text-xs font-semibold text-zinc-400 uppercase pt-0.5">Input</dt>
                  <dd className="text-zinc-700">{a.input}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-16 flex-shrink-0 text-xs font-semibold text-zinc-400 uppercase pt-0.5">Does</dt>
                  <dd className="text-zinc-700">{a.process}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-16 flex-shrink-0 text-xs font-semibold text-zinc-400 uppercase pt-0.5">Output</dt>
                  <dd className="text-zinc-900 font-medium">{a.output}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-16 flex-shrink-0 text-xs font-semibold text-zinc-400 uppercase pt-0.5">Uses</dt>
                  <dd className="text-brand-700">{a.uses}</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>

        {/* Layers view */}
        <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mt-8 mb-3">The three layers it works across</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {LAYERS.map((l) => (
            <div key={l.name} className="bg-white border border-zinc-200/60 rounded-2xl p-5">
              <div className="flex items-center gap-2.5 mb-3">
                <span className={`w-9 h-9 rounded-xl border flex items-center justify-center ${tintCls(l.tint)}`}>
                  <l.Icon className="w-4.5 h-4.5" strokeWidth={2} />
                </span>
                <h3 className="text-sm font-semibold text-zinc-900">{l.name}</h3>
              </div>
              <ul className="space-y-1.5">
                {l.items.map((it) => (
                  <li key={it} className="text-xs text-zinc-600 flex items-start gap-1.5">
                    <span className="text-brand-500 mt-0.5">•</span>
                    <span>{it}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
