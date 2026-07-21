import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, ChevronUp, User, Sparkles, Zap, BookOpen, FileText, Route } from "lucide-react";
import type { ChatMessage as ChatMessageType, Claim, CitedChunk, QueryResponse } from "../types";
import { useStore } from "../store/useStore";

function scoreBand(score: number) {
  if (score >= 0.8) return "score-green";
  if (score >= 0.6) return "score-amber";
  return "score-red";
}

// Strip the storage UUID prefix and any folder path so the reader sees a
// clean, recognisable PDF name.
function cleanSource(src: string) {
  const base = src.split(/[\\/]/).pop() || src;
  return base.replace(/^[0-9a-fA-F]{16,32}_/, "");
}

// "Retrieved from …" — shows exactly which PDF and page each citation [n]
// came from, so the answer is traceable to its sources at a glance.
function SourcesSection({ sources }: { sources: CitedChunk[] }) {
  const [open, setOpen] = useState(false);
  const { activeCorpusId, setViewingPdf } = useStore();
  const uniqueFiles = Array.from(new Set(sources.map((s) => cleanSource(s.source))));
  return (
    <div className="w-full">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-xs text-zinc-500 hover:text-zinc-900 flex items-center gap-1 self-start transition-colors focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
      >
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        <BookOpen className="w-3.5 h-3.5 text-brand-500" strokeWidth={2} />
        Retrieved from {uniqueFiles.length} source{uniqueFiles.length > 1 ? "s" : ""}
      </button>
      {!open && (
        <p className="text-xs text-zinc-400 mt-1 truncate">{uniqueFiles.join("  ·  ")}</p>
      )}
      {open && (
        <div className="mt-2 space-y-1.5">
          {sources.map((s, i) => (
            <button
              key={s.chunk_id + i}
              onClick={() => activeCorpusId && setViewingPdf({ corpusId: activeCorpusId, name: s.source, page: s.page })}
              className="w-full text-left bg-zinc-50 hover:bg-brand-50 border border-zinc-200/60 hover:border-brand-200 rounded-lg px-2.5 py-2 transition-colors"
              title="Open this PDF at the retrieved page"
            >
              <p className="text-xs font-medium text-zinc-800 flex items-center gap-1.5">
                <span className="badge bg-brand-50 text-brand-700 border border-brand-200 font-mono tabular-nums px-1.5">[{i + 1}]</span>
                <FileText className="w-3 h-3 text-brand-500 flex-shrink-0" strokeWidth={2} />
                <span className="truncate">{cleanSource(s.source)}</span>
                <span className="text-zinc-400 flex-shrink-0">· p.{s.page}</span>
              </p>
              <p className="text-xs text-zinc-500 mt-1 leading-relaxed line-clamp-2 italic">"{s.text}"</p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function verdictWord(score: number) {
  if (score >= 0.8) return "supported";
  if (score >= 0.6) return "partly supported";
  return "not confirmed by source";
}

function ClaimCard({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  const { activeCorpusId, setViewingPdf } = useStore();
  const pct = (claim.faithfulness_score * 100).toFixed(0);
  const word = verdictWord(claim.faithfulness_score);
  return (
    <div className={`rounded-xl border-l-4 p-3 text-sm ${
      claim.verdict ? (claim.faithfulness_score >= 0.8 ? "border-emerald-500 bg-emerald-50"
        : "border-amber-500 bg-amber-50")
      : "border-red-500 bg-red-50"}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium text-zinc-900 leading-snug">{claim.claim_text}</p>
        <span
          className={`badge flex-shrink-0 whitespace-nowrap ${scoreBand(claim.faithfulness_score)}`}
          title={`Faithfulness ${pct}% — how strongly the cited source supports this exact sentence. High = the source clearly backs it; low = the model wrote something the source does not clearly confirm.`}
        >
          {word} · <span className="font-mono tabular-nums">{pct}%</span>
        </span>
      </div>

      {/* Exact source(s) + page — click to open the PDF at that page */}
      {claim.cited_chunks.length > 0 && (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
          {claim.cited_chunks.map((c, i) => (
            <span key={c.chunk_id} className="inline-flex items-center gap-1">
              <button
                onClick={() => activeCorpusId && setViewingPdf({ corpusId: activeCorpusId, name: c.source, page: c.page })}
                className="inline-flex items-center gap-1 text-xs text-brand-700 hover:text-brand-900 hover:underline transition-colors"
                title="Open this PDF at the cited page"
              >
                <FileText className="w-3 h-3 text-brand-500 flex-shrink-0" strokeWidth={2} />
                <span className="font-medium">{cleanSource(c.source)}</span>
                <span className="text-zinc-500">· p.{c.page}</span>
              </button>
              {i < claim.cited_chunks.length - 1 && <span className="text-zinc-300">|</span>}
            </span>
          ))}
        </div>
      )}

      {claim.cited_chunks.length > 0 && (
        <>
          <button onClick={() => setOpen((v) => !v)}
            className="mt-1.5 text-xs text-zinc-500 hover:text-zinc-900 flex items-center gap-1 transition-colors focus-visible:ring-2 focus-visible:ring-brand-500 rounded">
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {open ? "hide passage" : "view the exact passage"}
          </button>
          {open && (
            <div className="mt-2 space-y-2">
              {claim.cited_chunks.map((c) => (
                <div key={c.chunk_id} className="bg-zinc-50 border border-zinc-200/60 rounded-lg p-2.5">
                  <p className="text-xs text-brand-700 font-medium mb-1">
                    {cleanSource(c.source)} · p.{c.page}
                    {c.score !== undefined && <span className="text-zinc-400 ml-1 font-mono tabular-nums">(match: {c.score.toFixed(3)})</span>}
                  </p>
                  <p className="text-xs text-zinc-600 leading-relaxed line-clamp-3">"{c.text}"</p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** A friendly, step-by-step account of how THIS answer was produced — so a
 *  viewer understands the flow and why claims are (not) supported. */
function ExplainFlow({ resp }: { resp: QueryResponse }) {
  const stages = resp.stage_log || [];
  const isGuard = stages[0]?.stage === ("guard" as any);
  const cited = (resp.claims || []).filter((c) => c.cited_chunks && c.cited_chunks.length > 0);
  const supported = cited.filter((c) => c.verdict).length;
  const unsupported = cited.length - supported;
  const retr: any = stages.find((s) => s.stage === "retriever");
  const nPassages = retr?.chunks_found ?? resp.sources?.length ?? 0;
  const paperCount = new Set((resp.sources || []).map((s) => cleanSource(s.source))).size;

  const steps = isGuard
    ? [
        { title: "Recognised the question type", body: "This was a greeting or a question not related to your PDFs, so the system answered directly and honestly instead of searching — this avoids making things up." },
      ]
    : [
        {
          title: "1 · Understood your question (Planner)",
          body: resp.sub_questions?.length
            ? "It broke your question into focused sub-questions so each idea could be searched precisely:"
            : "It used your question as a single focused search.",
          chips: resp.sub_questions,
        },
        {
          title: "2 · Searched your PDFs (Retriever)",
          body: `It converted the question into "meaning" and found ${nPassages} of the most relevant passage${nPassages === 1 ? "" : "s"} across ${paperCount} paper${paperCount === 1 ? "" : "s"} — these became the numbered sources [1], [2], …`,
        },
        {
          title: "3 · Wrote the answer (Synthesizer)",
          body: "It wrote the answer using ONLY those passages and put a citation after every fact. It was told to add no outside knowledge.",
        },
        {
          title: "4 · Checked every citation (Verifier)",
          body: `It checked each sentence against the source it cites. ${supported} of ${cited.length} cited sentence${cited.length === 1 ? "" : "s"} are supported; ${unsupported} could not be confirmed by the source and ${unsupported === 1 ? "is" : "are"} flagged in red.`,
        },
      ];

  return (
    <div className="w-full bg-zinc-50 border border-zinc-200/60 rounded-xl p-3.5 space-y-3">
      <p className="text-xs text-zinc-500 leading-relaxed">
        Here is how the four agents produced this answer, step by step:
      </p>
      <ol className="space-y-2.5">
        {steps.map((s, i) => (
          <li key={i} className="flex gap-2.5">
            <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-brand-500 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs font-semibold text-zinc-800">{s.title}</p>
              <p className="text-xs text-zinc-600 leading-relaxed">{s.body}</p>
              {(s as any).chips?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {(s as any).chips.map((q: string, k: number) => (
                    <span key={k} className="badge bg-white text-brand-700 border border-brand-200 text-[11px]">{q}</span>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      {!isGuard && (
        <div className="text-xs text-zinc-600 bg-white border border-zinc-200/60 rounded-lg px-3 py-2 leading-relaxed">
          <span className="font-semibold text-zinc-800">Why “supported” vs “not confirmed”?</span> For each
          sentence, an evidence model reads the exact cited page and decides whether it truly backs the sentence.
          <span className="text-emerald-700 font-medium"> Supported</span> = the page clearly says it.
          <span className="text-red-700 font-medium"> Not confirmed</span> = the page doesn’t clearly say it, so the
          system flags it honestly rather than pretending. A low score is the system being careful, not a bug.
        </div>
      )}
    </div>
  );
}

interface Props { message: ChatMessageType }

export default function ChatMessage({ message }: Props) {
  const [showClaims, setShowClaims] = useState(false);
  const [showExplain, setShowExplain] = useState(false);
  const isUser = message.role === "user";
  const resp = message.response;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 items-start ${isUser ? "flex-row-reverse" : ""}`}
    >
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
        isUser ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-700 border border-brand-200"}`}>
        {isUser ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
      </div>

      <div className={`flex flex-col gap-2 max-w-[78%] ${isUser ? "items-end" : "items-start"}`}>
        {/* Bubble */}
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
          isUser ? "bg-brand-600 text-white rounded-tr-sm"
                 : "bg-white text-zinc-900 border border-zinc-200/60 rounded-tl-sm shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]"}`}>
          {message.text}
        </div>

        {/* Response metadata — compact summary + clean toggle buttons */}
        {resp && (
          <div className="flex flex-col gap-2 w-full">
            {/* Summary bar (compact) */}
            <div className="flex items-center gap-3 flex-wrap text-xs text-zinc-500">
              <span
                className={`badge font-mono tabular-nums ${scoreBand(resp.overall_faithfulness)}`}
                title="Overall faithfulness = average of how well the cited sources support the answer's sentences. Higher is better."
              >
                {(resp.overall_faithfulness * 100).toFixed(0)}% faithful
              </span>
              <span>{resp.provider}</span>
              <span className="font-mono tabular-nums">{(resp.latency_ms / 1000).toFixed(1)}s</span>
              {resp.retries > 0 && <span className="text-amber-700">{resp.retries} revision{resp.retries > 1 ? "s" : ""}</span>}
              {resp.is_cached && (
                <span className="text-brand-700 flex items-center gap-1"><Zap className="w-3 h-3" /> cached</span>
              )}
            </div>

            {/* Toggle buttons row — details stay hidden until asked (declutter) */}
            <div className="flex items-center gap-2 flex-wrap">
              <button onClick={() => setShowExplain((v) => !v)}
                className={`text-xs flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors ${
                  showExplain ? "bg-brand-50 border-brand-200 text-brand-700" : "bg-white border-zinc-200 text-zinc-600 hover:bg-zinc-50"}`}>
                <Route className="w-3.5 h-3.5" /> How I got this answer
              </button>
              {resp.claims?.length > 0 && (
                <button onClick={() => setShowClaims((v) => !v)}
                  className={`text-xs flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition-colors ${
                    showClaims ? "bg-brand-50 border-brand-200 text-brand-700" : "bg-white border-zinc-200 text-zinc-600 hover:bg-zinc-50"}`}>
                  <Sparkles className="w-3.5 h-3.5" /> {resp.claims.length} claim{resp.claims.length > 1 ? "s" : ""} checked
                </button>
              )}
            </div>

            {/* Explain flow */}
            {showExplain && <ExplainFlow resp={resp} />}

            {/* Sources — which PDFs this answer was retrieved from (click to open) */}
            {resp.sources?.length > 0 && <SourcesSection sources={resp.sources} />}

            {/* Per-claim verification detail */}
            {showClaims && resp.claims?.length > 0 && (
              <div className="space-y-2 w-full">
                <div className="text-xs text-zinc-500 bg-zinc-50 border border-zinc-200/60 rounded-lg px-3 py-2 leading-relaxed">
                  Each sentence is checked against the source it cites.
                  <span className="text-emerald-700 font-medium"> Green = the source supports it</span>,
                  <span className="text-amber-700 font-medium"> amber = partial</span>,
                  <span className="text-red-700 font-medium"> red = the source does not clearly confirm it</span>.
                  A low score is the system being honest, not an error.
                </div>
                {resp.claims.map((c, i) => <ClaimCard key={i} claim={c} />)}
              </div>
            )}
          </div>
        )}

        <span className="text-xs text-zinc-400">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </motion.div>
  );
}
