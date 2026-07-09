import { RadialBarChart, RadialBar, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import type { QueryResponse } from "../types";

function scoreBand(score: number) {
  if (score >= 0.8) return { label: "High", color: "#059669" };
  if (score >= 0.6) return { label: "Medium", color: "#d97706" };
  return { label: "Low", color: "#dc2626" };
}

function ScoreGauge({ value, label }: { value: number; label: string }) {
  const band = scoreBand(value);
  const pct = Math.round(value * 100);
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
          <circle cx="18" cy="18" r="15.9" fill="none" stroke="#e4e4e7" strokeWidth="3" />
          <circle cx="18" cy="18" r="15.9" fill="none"
            stroke={band.color} strokeWidth="3"
            strokeDasharray={`${pct} ${100 - pct}`}
            strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-sm font-bold font-mono tabular-nums" style={{ color: band.color }}>{pct}%</span>
        </div>
      </div>
      <p className="text-xs text-zinc-500 text-center leading-tight">{label}</p>
      <span className="text-xs font-medium" style={{ color: band.color }}>{band.label}</span>
    </div>
  );
}

interface Props { response: QueryResponse }

export default function MetricsPanel({ response }: Props) {
  const claimData = response.claims.map((c, i) => ({
    name: `C${i + 1}`,
    score: +(c.faithfulness_score * 100).toFixed(1),
    fill: c.faithfulness_score >= 0.8 ? "#059669"
      : c.faithfulness_score >= 0.6 ? "#d97706" : "#dc2626",
  }));

  const retrieverStage = response.stage_log.find((s) => s.stage === "retriever");
  const topScore = retrieverStage?.top_score ?? 0;

  return (
    <div className="space-y-4">
      <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
        RAG evaluation metrics
      </p>

      {/* Gauge row */}
      <div className="grid grid-cols-3 gap-4">
        <ScoreGauge value={response.overall_faithfulness} label="Citation faithfulness" />
        <ScoreGauge value={topScore} label="Retrieval precision" />
        <ScoreGauge value={response.claims.filter((c) => c.verdict).length / Math.max(response.claims.length, 1)}
          label="Claim pass rate" />
      </div>

      {/* Per-claim bar */}
      {claimData.length > 0 && (
        <div className="card p-3">
          <p className="text-xs text-zinc-500 mb-2">Per-claim faithfulness scores</p>
          <ResponsiveContainer width="100%" height={80}>
            <BarChart data={claimData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
              <XAxis dataKey="name" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: "#a1a1aa", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: "#ffffff", border: "1px solid #e4e4e7", borderRadius: 8 }}
                labelStyle={{ color: "#71717a" }}
                formatter={(v: number) => [`${v}%`, "Faithfulness"]}
              />
              <Bar dataKey="score" fill="#0d9488">
                {claimData.map((d, i) => (
                  <rect key={i} fill={d.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-2">
        {[
          { label: "Latency", value: `${response.latency_ms}ms` },
          { label: "Retries", value: response.retries },
          { label: "Sources", value: response.sources.length },
          { label: "Cached", value: response.is_cached ? "Yes" : "No" },
        ].map((s) => (
          <div key={s.label} className="card p-3 text-center">
            <p className="text-base font-bold font-mono tabular-nums text-brand-700">{s.value}</p>
            <p className="text-xs text-zinc-500 mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
