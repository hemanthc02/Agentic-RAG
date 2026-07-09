import { useState } from "react";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { GraduationCap, ChevronRight, RotateCcw, Loader, Trophy, Check, AlertTriangle } from "lucide-react";
import { researchApi } from "../api/client";
import { useStore } from "../store/useStore";
import type { VivaEvaluation } from "../types";

type QuestionType = "breadth" | "depth" | "defense" | "novelty" | "future";
type Phase = "setup" | "question" | "feedback" | "complete";
type Difficulty = "undergraduate" | "masters" | "phd";

const Q_TYPES: { value: QuestionType; label: string; desc: string }[] = [
  { value: "breadth",  label: "Breadth",  desc: "Scope and contribution" },
  { value: "depth",    label: "Depth",    desc: "Technical methodology" },
  { value: "defense",  label: "Defense",  desc: "Limitations and trade-offs" },
  { value: "novelty",  label: "Novelty",  desc: "Difference from prior work" },
  { value: "future",   label: "Future",   desc: "Next steps and extensions" },
];

const DIFFICULTY_OPTS: { value: Difficulty; label: string; desc: string }[] = [
  { value: "undergraduate", label: "UG / Bachelor's", desc: "Foundational concepts" },
  { value: "masters",       label: "Master's",        desc: "Methodology + results" },
  { value: "phd",           label: "PhD",             desc: "Full defense, edge cases" },
];

const SCORE_COLOR = (s: number) =>
  s >= 8 ? "text-emerald-600" : s >= 6 ? "text-amber-600" : "text-red-600";

const VERDICT_COLOR: Record<string, string> = {
  strong:            "score-green",
  acceptable:        "score-amber",
  needs_improvement: "score-red",
};

interface ScoreEntry { q: string; type: string; score: number; verdict: string }

export default function VivaPage() {
  const { activeCorpusId, corpora, mode, provider } = useStore();

  const [phase, setPhase]               = useState<Phase>("setup");
  const [difficulty, setDifficulty]     = useState<Difficulty>("masters");
  const [qType, setQType]               = useState<QuestionType>("depth");
  const [sessionId, setSessionId]       = useState<string | null>(null);
  const [currentQuestion, setQuestion]  = useState("");
  const [studentAnswer, setAnswer]      = useState("");
  const [evaluation, setEvaluation]     = useState<VivaEvaluation | null>(null);
  const [askedQuestions, setAsked]      = useState<string[]>([]);
  const [history, setHistory]           = useState<ScoreEntry[]>([]);
  const [totalScore, setTotalScore]     = useState(0);
  const [loading, setLoading]           = useState(false);

  const corpus = corpora.find((c) => c.id === activeCorpusId);
  const avgScore = history.length > 0 ? totalScore / history.length : 0;

  async function startViva() {
    if (!activeCorpusId) return toast.error("Select a corpus first");
    setLoading(true);
    try {
      // Create session
      const { data: session } = await researchApi.createVivaSession({
        corpus_id: activeCorpusId,
        difficulty,
      });
      setSessionId(session.id);
      await fetchQuestion(session.id, []);
    } catch {
      toast.error("Failed to start viva session");
    } finally {
      setLoading(false);
    }
  }

  async function fetchQuestion(sid: string, asked: string[]) {
    setLoading(true);
    setAnswer("");
    setEvaluation(null);
    try {
      const { data } = await researchApi.vivaQuestion({
        corpus_id: activeCorpusId!,
        question_type: qType,
        asked_questions: asked,
        session_id: sid,
        mode,
        provider,
      });
      setQuestion(data.question);
      setAsked((prev) => [...prev, data.question]);
      setPhase("question");
    } catch {
      toast.error("Failed to generate question");
    } finally {
      setLoading(false);
    }
  }

  async function submitAnswer() {
    if (!activeCorpusId || !studentAnswer.trim()) return;
    setLoading(true);
    try {
      const { data } = await researchApi.vivaEvaluate({
        corpus_id: activeCorpusId,
        question: currentQuestion,
        student_answer: studentAnswer,
        session_id: sessionId ?? undefined,
        question_type: qType,
        mode,
        provider,
      });
      setEvaluation(data);
      setTotalScore((s) => s + data.score);
      setHistory((h) => [...h, {
        q: currentQuestion, type: qType,
        score: data.score, verdict: data.verdict,
      }]);
      setPhase("feedback");
    } catch {
      toast.error("Evaluation failed");
    } finally {
      setLoading(false);
    }
  }

  async function nextQuestion() {
    if (!sessionId) return;
    await fetchQuestion(sessionId, askedQuestions);
  }

  async function endSession() {
    if (sessionId) {
      try { await researchApi.completeVivaSession(sessionId); } catch { /* best-effort */ }
    }
    setPhase("complete");
  }

  function reset() {
    setPhase("setup");
    setSessionId(null);
    setQuestion("");
    setAnswer("");
    setEvaluation(null);
    setAsked([]);
    setHistory([]);
    setTotalScore(0);
  }

  return (
    <div className="h-full overflow-y-auto bg-canvas">
      <div className="flex flex-col items-center py-10 px-4">
        <div className="w-full max-w-2xl space-y-6">

          {/* Header */}
          <div className="text-center">
            <div className="w-14 h-14 rounded-2xl bg-brand-50 border border-brand-200 flex items-center justify-center mx-auto mb-3">
              <GraduationCap className="w-7 h-7 text-brand-600" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Research viva</h1>
            <p className="text-zinc-500 text-sm mt-1">
              Simulate a thesis defense — grounded in your uploaded papers
            </p>
            {corpus && (
              <p className="text-brand-700 text-xs mt-1">Corpus: {corpus.name}</p>
            )}
          </div>

          {/* Running score */}
          {history.length > 0 && phase !== "complete" && (
            <div className="card px-5 py-3 flex items-center justify-between">
              <div className="flex gap-4 text-sm text-zinc-500">
                <span>Questions: <span className="text-zinc-900 font-semibold font-mono tabular-nums">{history.length}</span></span>
                <span>Avg: <span className={`font-semibold font-mono tabular-nums ${SCORE_COLOR(avgScore)}`}>{avgScore.toFixed(1)}/10</span></span>
              </div>
              <button onClick={endSession}
                className="text-xs text-zinc-500 hover:text-zinc-700 underline transition duration-150 focus-visible:ring-2 focus-visible:ring-brand-500 rounded">
                End & see summary
              </button>
            </div>
          )}

          {/* ── SETUP ── */}
          {phase === "setup" && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              className="card p-6 space-y-6">

              {/* Difficulty */}
              <div>
                <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wide block mb-3">
                  Examination level
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {DIFFICULTY_OPTS.map((d) => (
                    <button key={d.value} onClick={() => setDifficulty(d.value)}
                      className={`p-3 rounded-lg border text-left text-xs transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 ${
                        difficulty === d.value
                          ? "bg-brand-50 border-brand-200 text-brand-700"
                          : "bg-white border-zinc-200/60 text-zinc-500 hover:border-zinc-300"
                      }`}>
                      <div className="font-medium text-sm">{d.label}</div>
                      <div className="opacity-70 mt-0.5">{d.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Question type */}
              <div>
                <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wide block mb-3">
                  First question type
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {Q_TYPES.map((t) => (
                    <button key={t.value} onClick={() => setQType(t.value)}
                      className={`p-3 rounded-lg border text-left text-sm transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 ${
                        qType === t.value
                          ? "bg-brand-50 border-brand-200 text-brand-700"
                          : "bg-white border-zinc-200/60 text-zinc-500 hover:border-zinc-300"
                      }`}>
                      <div className="font-medium">{t.label}</div>
                      <div className="text-xs opacity-70 mt-0.5">{t.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {!activeCorpusId && (
                <p className="text-amber-600 text-xs flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
                  Choose a PDF library on the Ask tab first.
                </p>
              )}

              <button onClick={startViva}
                disabled={loading || !activeCorpusId}
                className="btn-primary w-full flex items-center justify-center gap-2">
                {loading ? <Loader className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
                {loading ? "Starting session…" : "Begin viva"}
              </button>
            </motion.div>
          )}

          {/* ── QUESTION ── */}
          {phase === "question" && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              className="space-y-4">
              <div className="card p-5">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xs font-semibold text-brand-700 uppercase tracking-wide font-mono tabular-nums">
                    Q{askedQuestions.length}
                  </span>
                  <span className="badge capitalize">{qType}</span>
                  <span className="badge capitalize">{difficulty}</span>
                </div>
                <p className="text-zinc-900 leading-relaxed">{currentQuestion}</p>
              </div>

              <div>
                <label className="text-xs text-zinc-500 mb-2 block">Your answer</label>
                <textarea
                  value={studentAnswer}
                  onChange={(e) => setAnswer(e.target.value)}
                  rows={6}
                  className="input w-full resize-none"
                  placeholder="Type your answer here…"
                />
              </div>

              <div className="flex gap-3">
                <button onClick={submitAnswer}
                  disabled={loading || !studentAnswer.trim()}
                  className="btn-primary flex-1 flex items-center justify-center gap-2">
                  {loading ? <Loader className="w-4 h-4 animate-spin" /> : null}
                  {loading ? "Evaluating…" : "Submit answer"}
                </button>
                {/* Let student change question type for next */}
                <select value={qType} onChange={(e) => setQType(e.target.value as QuestionType)}
                  className="input text-xs px-3 py-2 w-36">
                  {Q_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
            </motion.div>
          )}

          {/* ── FEEDBACK ── */}
          {phase === "feedback" && evaluation && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              className="space-y-4">

              <div className="card p-5 flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-sm">Score</p>
                  <p className={`text-4xl font-bold mt-1 font-mono tabular-nums ${SCORE_COLOR(evaluation.score)}`}>
                    {evaluation.score}<span className="text-zinc-400 text-xl">/10</span>
                  </p>
                </div>
                <span className={`text-sm font-medium px-3 py-1.5 rounded-full border capitalize ${VERDICT_COLOR[evaluation.verdict]}`}>
                  {evaluation.verdict.replace("_", " ")}
                </span>
              </div>

              <div className="card p-5 space-y-4">
                <p className="text-zinc-700 text-sm leading-relaxed">{evaluation.feedback}</p>

                {evaluation.correct_points.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-emerald-600 mb-2 flex items-center gap-1">
                      <Check className="w-3.5 h-3.5" /> Done well
                    </p>
                    <ul className="space-y-1">
                      {evaluation.correct_points.map((p, i) => (
                        <li key={i} className="text-xs text-zinc-600 flex gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1 flex-shrink-0" /> {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {evaluation.missed_points.length > 0 && (
                  <div>
                    <p className="text-xs font-semibold text-amber-600 mb-2 flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" /> Missed points
                    </p>
                    <ul className="space-y-1">
                      {evaluation.missed_points.map((p, i) => (
                        <li key={i} className="text-xs text-zinc-600 flex gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1 flex-shrink-0" /> {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {evaluation.follow_up && (
                  <div className="border-t border-zinc-200/60 pt-3">
                    <p className="text-xs font-semibold text-brand-700 mb-1">Follow-up question</p>
                    <p className="text-sm text-zinc-600 italic">"{evaluation.follow_up}"</p>
                  </div>
                )}
              </div>

              <div className="flex gap-3">
                <button onClick={nextQuestion} disabled={loading}
                  className="btn-primary flex-1 flex items-center justify-center gap-2">
                  {loading ? <Loader className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
                  {loading ? "Generating…" : "Next question"}
                </button>
                <button onClick={endSession} className="btn-ghost px-4 flex items-center gap-2">
                  <Trophy className="w-4 h-4" /> Finish
                </button>
                <button onClick={reset} className="btn-ghost px-4">
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          )}

          {/* ── COMPLETE / SUMMARY ── */}
          {phase === "complete" && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              className="space-y-4">
              <div className="card p-6 text-center">
                <Trophy className="w-12 h-12 text-amber-500 mx-auto mb-3" />
                <h2 className="text-xl font-bold tracking-tight text-zinc-900 mb-1">Viva complete</h2>
                <p className={`text-4xl font-bold mt-3 font-mono tabular-nums ${SCORE_COLOR(avgScore)}`}>
                  {avgScore.toFixed(1)}<span className="text-zinc-400 text-xl">/10</span>
                </p>
                <p className="text-zinc-500 text-sm mt-1">
                  {history.length} question{history.length !== 1 ? "s" : ""} · avg score
                </p>
              </div>

              {/* Per-question breakdown */}
              {history.length > 0 && (
                <div className="card p-4 space-y-2">
                  <p className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">Question breakdown</p>
                  {history.map((entry, i) => (
                    <div key={i} className="flex items-start gap-3 py-2 border-b border-zinc-200/60 last:border-0">
                      <span className="text-xs text-zinc-400 w-5 flex-shrink-0 mt-0.5 font-mono tabular-nums">Q{i + 1}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-zinc-700 truncate">{entry.q}</p>
                        <span className="text-xs text-zinc-400 capitalize">{entry.type}</span>
                      </div>
                      <span className={`text-sm font-semibold flex-shrink-0 font-mono tabular-nums ${SCORE_COLOR(entry.score)}`}>
                        {entry.score}/10
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <button onClick={reset} className="btn-primary w-full flex items-center justify-center gap-2">
                <RotateCcw className="w-4 h-4" /> Start new session
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
