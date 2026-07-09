import { motion } from "framer-motion";
import { Brain, CheckCircle, Search, Shield, XCircle } from "lucide-react";
import type { StageLogEntry } from "../types";

const STAGE_META: Record<string, { icon: typeof Brain; color: string; label: string }> = {
  planner:     { icon: Brain,        color: "text-brand-600", label: "Planner" },
  retriever:   { icon: Search,       color: "text-brand-600", label: "Retriever" },
  synthesizer: { icon: Brain,        color: "text-brand-600", label: "Synthesizer" },
  verifier:    { icon: Shield,       color: "text-brand-600", label: "Verifier" },
};

function StageCard({ entry, index }: { entry: StageLogEntry; index: number }) {
  const meta = STAGE_META[entry.stage] ?? { icon: Brain, color: "text-zinc-500", label: entry.stage };
  const Icon = meta.icon;
  const failed = entry.failed && entry.failed > 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className={`flex items-start gap-3 p-3 rounded-xl border ${
        failed
          ? "bg-amber-50 border-amber-200"
          : "bg-white border-zinc-200/60"
      }`}
    >
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
        failed ? "bg-amber-100" : "bg-brand-50"}`}>
        <Icon className={`w-3.5 h-3.5 ${failed ? "text-amber-600" : meta.color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-zinc-900">{meta.label}</span>
          <span className="text-xs text-zinc-500 font-mono tabular-nums">{entry.latency_ms}ms</span>
          {entry.error && <span className="badge score-red text-xs">{entry.error}</span>}
        </div>
        <div className="mt-1 space-y-0.5">
          {entry.sub_questions && (
            <p className="text-xs text-zinc-500">
              Sub-questions: {entry.sub_questions.map((q, i) => (
                <span key={i} className="inline-block bg-brand-50 border border-brand-200 text-brand-700 rounded px-1.5 py-0.5 mr-1 mb-0.5">{q}</span>
              ))}
            </p>
          )}
          {entry.chunks_found !== undefined && (
            <p className="text-xs text-zinc-500">
              Chunks: <span className="text-zinc-900 font-mono tabular-nums">{entry.chunks_found}</span>
              {" · "}Top score: <span className="text-zinc-900 font-mono tabular-nums">{(entry.top_score ?? 0).toFixed(3)}</span>
              {entry.crag_triggered && <span className="ml-2 badge score-amber text-xs">CRAG corrected</span>}
            </p>
          )}
          {entry.claims !== undefined && (
            <p className="text-xs text-zinc-500">
              Claims: <span className="text-zinc-900 font-mono tabular-nums">{entry.claims}</span>
              {entry.failed !== undefined && entry.failed > 0 && (
                <span className="ml-2 text-amber-600">{entry.failed} failed</span>
              )}
              {entry.overall_faithfulness !== undefined && (
                <span className="ml-2">· Overall: <span className={`font-mono tabular-nums ${
                  entry.overall_faithfulness >= 0.8 ? "text-emerald-600"
                    : entry.overall_faithfulness >= 0.6 ? "text-amber-600"
                    : "text-red-600"
                }`}>{(entry.overall_faithfulness * 100).toFixed(0)}%</span></span>
              )}
              {entry.will_revise && <span className="ml-2 badge score-amber text-xs">revising…</span>}
            </p>
          )}
          {entry.revision !== undefined && entry.revision > 0 && (
            <p className="text-xs text-amber-600">Revision pass #{entry.revision}</p>
          )}
        </div>
      </div>
    </motion.div>
  );
}

interface Props { stageLog: StageLogEntry[] }

export default function PipelineViz({ stageLog }: Props) {
  if (!stageLog?.length) return null;
  const total = stageLog.reduce((a, s) => a + s.latency_ms, 0);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between mb-1">
        <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Pipeline stages</p>
        <span className="text-xs text-zinc-500 font-mono tabular-nums">Total: {total}ms</span>
      </div>
      {stageLog.map((entry, i) => (
        <div key={i} className="flex items-stretch gap-2">
          <div className="flex flex-col items-center">
            <div className="w-px bg-zinc-300 flex-1" style={{ display: i === 0 ? "none" : undefined }} />
            <div className="w-2 h-2 rounded-full bg-brand-600 flex-shrink-0" />
            <div className="w-px bg-zinc-300 flex-1" style={{ display: i === stageLog.length - 1 ? "none" : undefined }} />
          </div>
          <div className="flex-1 pb-2">
            <StageCard entry={entry} index={i} />
          </div>
        </div>
      ))}
    </div>
  );
}
