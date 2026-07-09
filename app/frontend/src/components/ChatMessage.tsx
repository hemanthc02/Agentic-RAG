import { useState } from "react";
import { motion } from "framer-motion";
import { ChevronDown, ChevronUp, User, Sparkles, Zap } from "lucide-react";
import type { ChatMessage as ChatMessageType, Claim, CitedChunk } from "../types";

function scoreBand(score: number) {
  if (score >= 0.8) return "score-green";
  if (score >= 0.6) return "score-amber";
  return "score-red";
}

function ClaimCard({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={`rounded-xl border-l-4 p-3 text-sm ${
      claim.verdict ? (claim.faithfulness_score >= 0.8 ? "border-emerald-500 bg-emerald-50"
        : "border-amber-500 bg-amber-50")
      : "border-red-500 bg-red-50"}`}>
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium text-zinc-900 leading-snug">{claim.claim_text}</p>
        <span className={`badge flex-shrink-0 font-mono tabular-nums ${scoreBand(claim.faithfulness_score)}`}>
          {(claim.faithfulness_score * 100).toFixed(0)}%
        </span>
      </div>
      {claim.cited_chunks.length > 0 && (
        <>
          <button onClick={() => setOpen((v) => !v)}
            className="mt-2 text-xs text-zinc-500 hover:text-zinc-900 flex items-center gap-1 transition-colors focus-visible:ring-2 focus-visible:ring-brand-500 rounded">
            {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            {claim.cited_chunks.length} source{claim.cited_chunks.length > 1 ? "s" : ""}
          </button>
          {open && (
            <div className="mt-2 space-y-2">
              {claim.cited_chunks.map((c) => (
                <div key={c.chunk_id} className="bg-zinc-50 border border-zinc-200/60 rounded-lg p-2.5">
                  <p className="text-xs text-brand-700 font-medium mb-1">
                    {c.source} · p.{c.page}
                    {c.score !== undefined && <span className="text-zinc-400 ml-1 font-mono tabular-nums">(score: {c.score.toFixed(3)})</span>}
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

interface Props { message: ChatMessageType }

export default function ChatMessage({ message }: Props) {
  const [showClaims, setShowClaims] = useState(false);
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

        {/* Response metadata */}
        {resp && (
          <div className="flex flex-col gap-2 w-full">
            {/* Sub-questions */}
            {resp.sub_questions?.length > 0 && (
              <div className="flex flex-wrap gap-1.5 items-center">
                <span className="text-xs text-zinc-500">Sub-queries:</span>
                {resp.sub_questions.map((q, i) => (
                  <span key={i} className="badge bg-brand-50 text-brand-700 border border-brand-200 text-xs">
                    {q}
                  </span>
                ))}
              </div>
            )}

            {/* Summary bar */}
            <div className="flex items-center gap-3 flex-wrap text-xs text-zinc-500">
              <span className={`badge font-mono tabular-nums ${scoreBand(resp.overall_faithfulness)}`}>
                {(resp.overall_faithfulness * 100).toFixed(0)}% faithful
              </span>
              <span>{resp.provider}</span>
              <span className="font-mono tabular-nums">{resp.latency_ms}ms</span>
              {resp.retries > 0 && <span className="text-amber-700">{resp.retries} revision{resp.retries > 1 ? "s" : ""}</span>}
              {resp.is_cached && (
                <span className="text-brand-700 flex items-center gap-1">
                  <Zap className="w-3 h-3" /> cached
                </span>
              )}
            </div>

            {/* Claims toggle */}
            {resp.claims?.length > 0 && (
              <>
                <button onClick={() => setShowClaims((v) => !v)}
                  className="text-xs text-zinc-500 hover:text-zinc-900 flex items-center gap-1 self-start transition-colors focus-visible:ring-2 focus-visible:ring-brand-500 rounded">
                  {showClaims ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  {resp.claims.length} verified claim{resp.claims.length > 1 ? "s" : ""}
                </button>
                {showClaims && (
                  <div className="space-y-2 w-full">
                    {resp.claims.map((c, i) => <ClaimCard key={i} claim={c} />)}
                  </div>
                )}
              </>
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
