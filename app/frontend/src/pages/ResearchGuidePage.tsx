import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import toast from "react-hot-toast";
import {
  BookOpen, Send, Sparkles, Network, Loader, MessageSquare, GraduationCap,
} from "lucide-react";
import { conversationsApi, researchApi } from "../api/client";
import { useStore } from "../store/useStore";
import type { Conversation, KGEdge, KGNode } from "../types";
import ConversationSidebar from "../components/ConversationSidebar";
import KnowledgeGraphViewer from "../components/KnowledgeGraphViewer";

interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  text: string;
  chunks?: object[];
  latency_ms?: number;
}

type Tab = "chat" | "graph";

export default function ResearchGuidePage() {
  const { activeCorpusId, corpora, mode, provider } = useStore();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeConv, setActiveConv] = useState<Conversation | null>(null);
  const [kgBuilding, setKgBuilding] = useState(false);
  const [kgStats, setKgStats] = useState<{ node_count: number; edge_count: number } | null>(null);
  const [kgNodes, setKgNodes] = useState<KGNode[]>([]);
  const [kgEdges, setKgEdges] = useState<KGEdge[]>([]);
  const [tab, setTab] = useState<Tab>("chat");
  const [useReact, setUseReact] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const activeCorpus = corpora.find((c) => c.id === activeCorpusId);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load KG when corpus changes
  useEffect(() => {
    if (!activeCorpusId) { setKgStats(null); setKgNodes([]); setKgEdges([]); return; }
    researchApi.getKG(activeCorpusId)
      .then(({ data }) => {
        setKgStats({ node_count: data.node_count, edge_count: data.edge_count });
        setKgNodes(data.nodes ?? []);
        setKgEdges(data.edges ?? []);
      })
      .catch(() => {});
  }, [activeCorpusId]);

  async function buildKG() {
    if (!activeCorpusId) return toast.error("Select a corpus first");
    setKgBuilding(true);
    try {
      await researchApi.buildKG(activeCorpusId, mode, provider);
      // Reload full graph data after build
      const { data } = await researchApi.getKG(activeCorpusId);
      setKgStats({ node_count: data.node_count, edge_count: data.edge_count });
      setKgNodes(data.nodes ?? []);
      setKgEdges(data.edges ?? []);
      toast.success(`Knowledge graph: ${data.node_count} entities, ${data.edge_count} relations`);
      setTab("graph");
    } catch {
      toast.error("Failed to build knowledge graph");
    } finally {
      setKgBuilding(false);
    }
  }

  async function runGapAnalysis() {
    if (!activeCorpusId) return toast.error("Select a corpus first");
    setLoading(true);
    setTab("chat");
    addMsg("user", "Run a gap analysis on my research corpus — what are the open problems and improvement opportunities?");
    try {
      const { data } = await researchApi.gapAnalysis(activeCorpusId, mode, provider);
      addMsg("assistant", data.analysis, data.chunks, data.latency_ms);
    } catch {
      toast.error("Gap analysis failed");
      addMsg("assistant", "Gap analysis failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function addMsg(role: "user" | "assistant", text: string, chunks?: object[], latency_ms?: number) {
    setMessages((prev) => [...prev, {
      id: `${role}-${Date.now()}`, role, text, chunks, latency_ms,
    }]);
  }

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || !activeCorpusId) return;
    setQuestion("");
    addMsg("user", q);
    setLoading(true);
    try {
      const { data } = await researchApi.guide({
        question: q,
        corpus_id: activeCorpusId,
        conversation_id: activeConv?.id,
        mode,
        provider,
        use_react: useReact,
      });
      addMsg("assistant", data.answer, data.chunks, data.latency_ms);
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Guide request failed");
      addMsg("assistant", "Error: " + (err.response?.data?.detail ?? "Request failed"));
    } finally {
      setLoading(false);
    }
  }

  function handleNewConv(conv: Conversation) {
    setActiveConv(conv);
    setMessages([]);
  }

  async function handleSelectConv(conv: Conversation) {
    setActiveConv(conv);
    try {
      const { data } = await conversationsApi.get(conv.id);
      setMessages(
        (data.messages ?? []).map((m) => ({
          id: m.id, role: m.role as "user" | "assistant",
          text: m.content, latency_ms: (m.metadata as any)?.latency_ms,
        }))
      );
    } catch {
      setMessages([]);
    }
  }

  return (
    <div className="h-full flex overflow-hidden">

      {/* Conversation sidebar */}
      <aside className="w-60 border-r border-zinc-200/60 bg-white flex flex-col flex-shrink-0">
        <ConversationSidebar
          currentMode="guide"
          onNewConv={handleNewConv}
          onSelectConv={handleSelectConv}
        />
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden">

        {/* Top bar */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-200/60 bg-white">
          <div className="flex items-center gap-3">
            {/* Tab toggle */}
            <div className="flex items-center gap-1 bg-zinc-100 rounded-lg p-1">
              <button
                onClick={() => setTab("chat")}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                  tab === "chat"
                    ? "bg-white text-zinc-900 shadow-sm"
                    : "text-zinc-500 hover:text-zinc-900"
                }`}
              >
                <MessageSquare className="w-3 h-3" />
                Chat
              </button>
              <button
                onClick={() => setTab("graph")}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${
                  tab === "graph"
                    ? "bg-white text-zinc-900 shadow-sm"
                    : "text-zinc-500 hover:text-zinc-900"
                }`}
              >
                <Network className="w-3 h-3" />
                Knowledge graph
                {kgStats && kgStats.node_count > 0 && (
                  <span className="ml-1 bg-brand-600 text-white text-[10px] font-mono tabular-nums rounded-full px-1.5 py-0.5 leading-none">
                    {kgStats.node_count}
                  </span>
                )}
              </button>
            </div>

            {activeCorpus && (
              <span className="text-xs text-zinc-500">· {activeCorpus.name}</span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {kgStats && tab === "graph" && (
              <span className="text-xs text-zinc-500 font-mono tabular-nums">
                {kgStats.node_count} entities · {kgStats.edge_count} relations
              </span>
            )}
            <button
              onClick={buildKG}
              disabled={kgBuilding || !activeCorpusId}
              className="btn-ghost text-xs flex items-center gap-1.5 py-1.5 px-3 transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
            >
              {kgBuilding ? <Loader className="w-3 h-3 animate-spin" /> : <Network className="w-3 h-3" />}
              {kgBuilding ? "Building KG…" : "Build KG"}
            </button>
            <button
              onClick={runGapAnalysis}
              disabled={loading || !activeCorpusId}
              className="btn-ghost text-xs flex items-center gap-1.5 py-1.5 px-3 transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
            >
              <Sparkles className="w-3 h-3" />
              Gap analysis
            </button>
          </div>
        </div>

        {/* Tab content */}
        {tab === "graph" ? (
          <div className="flex-1 overflow-hidden p-4">
            <KnowledgeGraphViewer nodes={kgNodes} edges={kgEdges} />
          </div>
        ) : (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
              {messages.length === 0 && (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center max-w-md">
                    <BookOpen className="w-12 h-12 mx-auto mb-3 text-zinc-300" />
                    <p className="text-lg font-semibold tracking-tight mb-2 text-zinc-900">Research guide</p>
                    <p className="text-sm text-zinc-500 mb-4 max-w-[65ch]">
                      Ask about research gaps, methodology comparisons, improvement ideas,
                      or how techniques in your uploaded papers relate to each other.
                    </p>
                    <div className="grid grid-cols-1 gap-2 text-left">
                      {[
                        "What are the key limitations in the papers I uploaded?",
                        "How does CRAG differ from Self-RAG in my corpus?",
                        "What improvements could I make to the retrieval approach?",
                        "Run a gap analysis on my research corpus",
                      ].map((s) => (
                        <button key={s} onClick={() => setQuestion(s)}
                          className="text-xs text-left px-3 py-2 rounded-lg bg-white border border-zinc-200/60 hover:border-brand-200 hover:bg-brand-50 text-zinc-600 hover:text-brand-700 transition-colors duration-150 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              <AnimatePresence>
                {messages.map((msg) => (
                  <motion.div key={msg.id}
                    initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                    className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    {msg.role === "assistant" && (
                      <div className="w-8 h-8 rounded-full bg-brand-50 border border-brand-200 flex items-center justify-center flex-shrink-0">
                        <BookOpen className="w-4 h-4 text-brand-700" />
                      </div>
                    )}
                    <div className={`max-w-3xl rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-brand-600 text-white rounded-br-sm"
                        : "bg-white border border-zinc-200/60 text-zinc-900 rounded-bl-sm"
                    }`}>
                      {msg.text}
                      {msg.latency_ms && (
                        <div className={`mt-1.5 text-xs font-mono tabular-nums ${msg.role === "user" ? "text-brand-100" : "text-zinc-400"}`}>
                          {(msg.latency_ms / 1000).toFixed(1)}s
                        </div>
                      )}
                    </div>
                    {msg.role === "user" && (
                      <div className="w-8 h-8 rounded-full bg-zinc-100 border border-zinc-200/60 flex items-center justify-center flex-shrink-0">
                        <GraduationCap className="w-4 h-4 text-zinc-500" />
                      </div>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>

              {loading && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="flex gap-3 items-start">
                  <div className="w-8 h-8 rounded-full bg-brand-50 border border-brand-200 flex items-center justify-center">
                    <BookOpen className="w-4 h-4 text-brand-700" />
                  </div>
                  <div className="bg-white border border-zinc-200/60 rounded-2xl px-4 py-3 flex gap-1.5 items-center">
                    {[0, 0.15, 0.3].map((d) => (
                      <motion.div key={d} className="w-2 h-2 rounded-full bg-brand-500"
                        animate={{ scale: [1, 1.4, 1] }}
                        transition={{ duration: 0.9, repeat: Infinity, delay: d }} />
                    ))}
                    <span className="text-zinc-500 text-sm ml-2">Researching…</span>
                  </div>
                </motion.div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input */}
            <div className="border-t border-zinc-200/60 bg-white p-4">
              {!activeCorpusId && (
                <p className="text-amber-600 text-xs mb-2">
                  Choose or create a PDF library on the Ask tab first.
                </p>
              )}
              <form onSubmit={send} className="flex gap-3">
                <div className="flex-1 flex flex-col gap-2">
                  <textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(e as any); } }}
                    placeholder={activeCorpusId ? "Ask your research guide… (Enter to send)" : "Select a corpus first"}
                    disabled={!activeCorpusId || loading}
                    rows={2}
                    className="input resize-none"
                  />
                  <label className="flex items-center gap-2 cursor-pointer self-start">
                    <div
                      onClick={() => setUseReact(!useReact)}
                      className={`w-8 h-4 rounded-full transition-colors duration-150 relative ${useReact ? "bg-brand-600" : "bg-zinc-300"}`}
                    >
                      <span className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow-sm transition-transform ${useReact ? "translate-x-4" : "translate-x-0.5"}`} />
                    </div>
                    <span className="text-xs text-zinc-500">
                      ReAct mode {useReact ? <span className="text-brand-700">(multi-step reasoning)</span> : ""}
                    </span>
                  </label>
                </div>
                <button type="submit" disabled={!question.trim() || loading || !activeCorpusId}
                  className="btn-primary px-4 flex items-center gap-1.5 self-start mt-0 transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50">
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
