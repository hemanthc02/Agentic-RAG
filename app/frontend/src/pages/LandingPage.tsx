import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  BookOpen,
  Brain,
  Check,
  Cloud,
  HardDrive,
  Search,
  ShieldCheck,
} from "lucide-react";

const AGENTS = [
  {
    icon: Brain,
    step: "01",
    name: "Planner",
    desc: "Decomposes complex questions into 1–3 focused sub-queries. Simple questions pass through unchanged.",
  },
  {
    icon: Search,
    step: "02",
    name: "Retriever",
    desc: "FAISS semantic search over your PDFs, with a CRAG self-correction loop that rewrites weak queries before giving up.",
  },
  {
    icon: BookOpen,
    step: "03",
    name: "Synthesizer",
    desc: "Writes a grounded answer using only the retrieved passages, with an inline [N] citation on every factual claim.",
  },
  {
    icon: ShieldCheck,
    step: "04",
    name: "NLI Verifier",
    desc: "A DeBERTa-v3 cross-encoder scores every cited sentence against its source. Weak claims trigger a revision pass.",
  },
];

const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true },
  transition: { duration: 0.5 },
};

export default function LandingPage() {
  return (
    <div className="min-h-[100dvh] bg-zinc-50 text-zinc-900">
      {/* Nav */}
      <header className="border-b border-zinc-200/60 bg-white">
        <nav className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <span className="text-lg font-semibold tracking-tight">VeritasRAG</span>
          <div className="flex items-center gap-2">
            <Link
              to="/about"
              className="text-sm text-zinc-500 hover:text-zinc-900 px-3 py-2 rounded-lg transition focus-visible:ring-2 focus-visible:ring-brand-500 outline-none"
            >
              About
            </Link>
            <Link
              to="/login"
              className="text-sm text-zinc-500 hover:text-zinc-900 px-3 py-2 rounded-lg transition focus-visible:ring-2 focus-visible:ring-brand-500 outline-none"
            >
              Sign in
            </Link>
            <Link to="/register" className="btn-primary text-sm py-2 px-4">
              Get started
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero — left-aligned, asymmetric */}
      <section className="px-6 pt-20 pb-24">
        <div className="max-w-6xl mx-auto grid lg:grid-cols-12 gap-12 items-start">
          <motion.div
            className="lg:col-span-7"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <span className="badge bg-brand-50 text-brand-700 border border-brand-200 mb-6 inline-flex">
              Multi-agent RAG, open source
            </span>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight leading-tight mb-6">
              Answers from your PDFs, with every citation checked
            </h1>
            <p className="text-lg text-zinc-500 max-w-[65ch] mb-8 leading-relaxed">
              Upload your papers and ask questions. Four specialized agents plan,
              retrieve, and write the answer — then an NLI model checks every
              citation against your sources and flags anything it can't support.
            </p>
            <div className="flex items-center gap-4 flex-wrap">
              <Link
                to="/register"
                className="btn-primary text-base px-6 py-3 inline-flex items-center gap-2 active:scale-[0.98] transition"
              >
                Get started <ArrowRight className="w-4 h-4" />
              </Link>
              <Link
                to="/about"
                className="text-sm font-medium text-brand-700 hover:text-brand-800 transition"
              >
                How it works
              </Link>
            </div>
          </motion.div>

          <motion.div
            className="lg:col-span-5 lg:pt-4"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
          >
            <div className="card p-6">
              <p className="text-xs font-medium text-zinc-400 uppercase tracking-wide mb-4">
                What's inside
              </p>
              <ul className="flex flex-col gap-3 text-sm text-zinc-500">
                {[
                  "Per-claim citation verification with DeBERTa-v3",
                  "CRAG retrieval that self-corrects weak queries",
                  "Research guide, viva practice, and paper finder",
                  "Up to 20 PDFs per corpus, semantic chunking",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2.5">
                    <Check className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Pipeline — numbered vertical steps, zig-zag */}
      <section className="bg-white border-y border-zinc-200/60 px-6 py-24">
        <div className="max-w-6xl mx-auto">
          <motion.div {...fadeUp} className="mb-14 max-w-[65ch]">
            <h2 className="text-3xl font-bold tracking-tight mb-3">
              A four-agent pipeline
            </h2>
            <p className="text-zinc-500 leading-relaxed">
              Each agent has exactly one job. If the verifier can't support a
              claim from your documents, the answer goes back for revision — up
              to two passes.
            </p>
          </motion.div>

          <div className="flex flex-col gap-10">
            {AGENTS.map((a, i) => (
              <motion.div
                key={a.name}
                {...fadeUp}
                transition={{ duration: 0.5, delay: i * 0.05 }}
                className={`grid md:grid-cols-12 gap-6 items-start ${
                  i % 2 === 1 ? "md:text-right" : ""
                }`}
              >
                <div
                  className={`md:col-span-5 ${
                    i % 2 === 1 ? "md:col-start-8 md:order-2" : ""
                  }`}
                >
                  <div
                    className={`flex items-center gap-3 mb-2 ${
                      i % 2 === 1 ? "md:flex-row-reverse" : ""
                    }`}
                  >
                    <span className="font-mono tabular-nums text-sm text-zinc-400">
                      {a.step}
                    </span>
                    <span className="w-9 h-9 rounded-xl bg-brand-50 border border-brand-200 flex items-center justify-center">
                      <a.icon className="w-[18px] h-[18px] text-brand-700" />
                    </span>
                    <h3 className="text-lg font-semibold tracking-tight">
                      {a.name}
                    </h3>
                  </div>
                  <p className="text-sm text-zinc-500 leading-relaxed">
                    {a.desc}
                  </p>
                </div>
                <div
                  className={`hidden md:block md:col-span-6 border-t border-dashed border-zinc-200 self-center ${
                    i % 2 === 1 ? "md:col-start-1 md:order-1" : "md:col-start-7"
                  }`}
                />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Online vs offline */}
      <section className="px-6 py-24">
        <div className="max-w-6xl mx-auto">
          <motion.div {...fadeUp} className="mb-12 max-w-[65ch]">
            <h2 className="text-3xl font-bold tracking-tight mb-3">
              Online or fully offline
            </h2>
            <p className="text-zinc-500 leading-relaxed">
              Choose speed or privacy per session. Retrieval, embeddings, and
              citation verification always run locally either way.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-6">
            <motion.div {...fadeUp} className="card p-8">
              <div className="flex items-center gap-3 mb-4">
                <span className="w-10 h-10 rounded-xl bg-brand-50 border border-brand-200 flex items-center justify-center">
                  <Cloud className="w-5 h-5 text-brand-700" />
                </span>
                <div>
                  <h3 className="font-semibold tracking-tight">Online</h3>
                  <p className="text-xs text-zinc-400">Groq cloud</p>
                </div>
              </div>
              <ul className="flex flex-col gap-2.5 text-sm text-zinc-500">
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
                  Llama 4 Scout 17B for fast, capable synthesis
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
                  Only the prompt and retrieved passages leave your machine
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
                  Best for long sessions and complex questions
                </li>
              </ul>
            </motion.div>

            <motion.div
              {...fadeUp}
              transition={{ duration: 0.5, delay: 0.1 }}
              className="card p-8"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="w-10 h-10 rounded-xl bg-zinc-100 border border-zinc-200 flex items-center justify-center">
                  <HardDrive className="w-5 h-5 text-zinc-600" />
                </span>
                <div>
                  <h3 className="font-semibold tracking-tight">Offline</h3>
                  <p className="text-xs text-zinc-400">Ollama, on-device</p>
                </div>
              </div>
              <ul className="flex flex-col gap-2.5 text-sm text-zinc-500">
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
                  Phi-3 mini runs entirely on your hardware
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
                  Nothing leaves your machine — no network calls at all
                </li>
                <li className="flex items-start gap-2.5">
                  <Check className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
                  Best for sensitive or unpublished material
                </li>
              </ul>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 pb-24">
        <motion.div
          {...fadeUp}
          className="max-w-6xl mx-auto card p-10 md:p-12 flex flex-col md:flex-row md:items-center justify-between gap-6"
        >
          <div>
            <h2 className="text-2xl font-bold tracking-tight mb-2">
              Start with your own PDFs
            </h2>
            <p className="text-zinc-500 max-w-[65ch]">
              Create an account, upload a corpus, and ask your first question in
              a couple of minutes.
            </p>
          </div>
          <Link
            to="/register"
            className="btn-primary text-base px-6 py-3 inline-flex items-center gap-2 flex-shrink-0 active:scale-[0.98] transition"
          >
            Get started <ArrowRight className="w-4 h-4" />
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-zinc-200/60 bg-white px-6 py-10">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold tracking-tight">VeritasRAG</p>
            <p className="text-sm text-zinc-400 mt-1">
              MiniLM embeddings · FAISS retrieval · DeBERTa-v3 verification
            </p>
          </div>
          <div className="flex gap-6 text-sm text-zinc-500">
            <Link to="/about" className="hover:text-zinc-900 transition">
              About
            </Link>
            <Link to="/login" className="hover:text-zinc-900 transition">
              Sign in
            </Link>
            <Link to="/register" className="hover:text-zinc-900 transition">
              Register
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
