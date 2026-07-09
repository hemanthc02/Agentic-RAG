import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import {
  BookOpen, FileText, Plus, Send, SlidersHorizontal, Sparkles, Trash2, X,
} from "lucide-react";
import { conversationsApi, corpusApi, queryApi, systemApi } from "../api/client";
import { useStore } from "../store/useStore";
import type { QueryResponse } from "../types";
import PDFUploader from "../components/PDFUploader";
import PipelineViz from "../components/PipelineViz";
import MetricsPanel from "../components/MetricsPanel";
import ChatMessage from "../components/ChatMessage";
import ConversationSidebar from "../components/ConversationSidebar";

export default function AskPage() {
  const {
    corpora, setCorpora, documents, setDocuments,
    activeCorpusId, setActiveCorpus,
    mode, provider, topK, setTopK,
    messages, addMessage, clearMessages, loading, setLoading,
    setNetworkStatus,
  } = useStore();

  const [question, setQuestion] = useState("");
  const [lastResponse, setLastResponse] = useState<QueryResponse | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [creatingCorpus, setCreatingCorpus] = useState(false);
  const [newCorpusName, setNewCorpusName] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    corpusApi.list().then((r) => setCorpora(r.data)).catch(() => {});
    systemApi.status().then((r) => setNetworkStatus(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (activeCorpusId) {
      corpusApi.listDocs(activeCorpusId).then((r) => setDocuments(r.data)).catch(() => {});
    }
  }, [activeCorpusId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function createCorpus(e: React.FormEvent) {
    e.preventDefault();
    const name = newCorpusName.trim();
    if (!name) return;
    try {
      const { data } = await corpusApi.create(name);
      setCorpora([data, ...corpora]);
      setActiveCorpus(data.id);
      setNewCorpusName("");
      setCreatingCorpus(false);
      toast.success("Library created. Upload PDFs to it below.");
    } catch (err: any) {
      toast.error(
        err?.response?.data?.detail ??
          (err?.response
            ? "Couldn't create the library. Try again."
            : "Can't reach the server — check that the server window is still open."),
      );
    }
  }

  async function sendQuery(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    if (question.trim().length < 3) {
      toast.error("Type a full question — at least a few words.");
      return;
    }
    if (!activeCorpusId) { toast.error("Choose or create a PDF library first"); return; }
    if (documents.length === 0) { toast.error("Upload PDFs to this library first"); return; }

    const q = question.trim();
    setQuestion("");
    addMessage({ id: `u-${Date.now()}`, role: "user", text: q, timestamp: new Date().toISOString() });
    setLoading(true);

    try {
      const { data } = await queryApi.run({
        question: q, corpus_id: activeCorpusId,
        mode, provider, top_k: topK,
        conversation_id: activeConvId ?? undefined,
      });
      setLastResponse(data);
      addMessage({
        id: `a-${Date.now()}`, role: "assistant",
        text: data.answer, response: data,
        timestamp: new Date().toISOString(),
      });
      if (data.is_cached) toast("Served from cache");
    } catch (err: any) {
      const detail =
        err.response?.data?.detail ??
        (err.response ? "Query failed" : "Can't reach the server — check that the server window is still open.");
      toast.error(detail);
      addMessage({
        id: `e-${Date.now()}`, role: "assistant",
        text: `Error: ${detail}`,
        timestamp: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  }

  const activeCorpus = corpora.find((c) => c.id === activeCorpusId);

  return (
    <div className="h-full flex">
      {/* ── Left: library + conversations ── */}
      <aside className="w-72 border-r border-zinc-200/60 bg-white flex flex-col flex-shrink-0 overflow-hidden">
        {/* PDF library */}
        <div className="p-4 border-b border-zinc-200/60">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">PDF library</h2>
            <button
              onClick={() => setCreatingCorpus((v) => !v)}
              className="p-1 rounded-md text-zinc-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
              title="New library"
              aria-label="New library"
            >
              {creatingCorpus ? <X className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
            </button>
          </div>

          {creatingCorpus && (
            <form onSubmit={createCorpus} className="flex gap-1.5 mb-2">
              <input
                autoFocus
                value={newCorpusName}
                onChange={(e) => setNewCorpusName(e.target.value)}
                placeholder="e.g. Thesis papers"
                className="input text-sm py-1.5 px-2.5 rounded-lg"
              />
              <button type="submit" className="btn-primary text-xs px-3 py-1.5 rounded-lg">Add</button>
            </form>
          )}

          <select
            className="input text-sm py-2"
            value={activeCorpusId ?? ""}
            onChange={(e) => setActiveCorpus(e.target.value || null)}
          >
            <option value="">Choose a library…</option>
            {corpora.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.doc_count} PDFs)
              </option>
            ))}
          </select>
        </div>

        {/* Upload + documents */}
        <div className="p-4 border-b border-zinc-200/60 overflow-y-auto max-h-[45%]">
          {activeCorpusId ? (
            <>
              <PDFUploader
                corpusId={activeCorpusId}
                onUploaded={() => {
                  // Refresh both the document list AND the corpora list so the
                  // "(N PDFs)" label in the dropdown updates immediately.
                  corpusApi.listDocs(activeCorpusId).then((r) => setDocuments(r.data)).catch(() => {});
                  corpusApi.list().then((r) => setCorpora(r.data)).catch(() => {});
                }}
              />
              {documents.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {documents.map((d) => (
                    <li key={d.id} className="text-xs text-zinc-600 truncate flex items-center gap-1.5">
                      <FileText className="w-3 h-3 text-brand-500 flex-shrink-0" strokeWidth={2} />
                      {d.original_name}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <div className="text-center py-6">
              <BookOpen className="w-8 h-8 mx-auto mb-2 text-zinc-300" strokeWidth={1.5} />
              <p className="text-xs text-zinc-400">Choose or create a library to upload PDFs.</p>
            </div>
          )}
        </div>

        {/* Conversations */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <ConversationSidebar
            currentMode="rag"
            onNewConv={(conv) => { setActiveConvId(conv.id); clearMessages(); }}
            onSelectConv={async (conv) => {
              setActiveConvId(conv.id);
              clearMessages();
              try {
                const { data } = await conversationsApi.get(conv.id);
                (data.messages ?? []).forEach((m) => {
                  addMessage({
                    id: m.id, role: m.role as "user" | "assistant",
                    text: m.content, timestamp: m.created_at,
                  });
                });
              } catch {}
            }}
          />
        </div>
      </aside>

      {/* ── Center: chat ── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-sm">
                <span className="w-12 h-12 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-6 h-6 text-brand-600" strokeWidth={1.5} />
                </span>
                <p className="text-lg font-semibold text-zinc-900 mb-1">
                  Ask your documents anything
                </p>
                <p className="text-sm text-zinc-500 leading-relaxed">
                  Four agents plan, retrieve, answer, and verify every citation
                  against your PDFs{activeCorpus ? ` in “${activeCorpus.name}”` : ""}.
                </p>
                {!activeCorpusId && (
                  <p className="text-xs mt-3 text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 inline-block">
                    Start by choosing a PDF library in the left panel.
                  </p>
                )}
              </div>
            </div>
          )}
          <AnimatePresence>
            {messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
          </AnimatePresence>
          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-3 items-start">
              <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center flex-shrink-0">
                <Sparkles className="w-4 h-4 text-white" strokeWidth={2} />
              </div>
              <div className="card px-4 py-3 flex gap-1.5 items-center">
                {[0, 0.15, 0.3].map((d) => (
                  <motion.div key={d} className="w-2 h-2 rounded-full bg-brand-500"
                    animate={{ scale: [1, 1.4, 1], opacity: [0.6, 1, 0.6] }}
                    transition={{ duration: 0.9, repeat: Infinity, delay: d }} />
                ))}
                <span className="text-zinc-500 text-sm ml-2">Agents running…</span>
              </div>
            </motion.div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Advanced panel (pipeline internals, metrics, retrieval settings) */}
        <AnimatePresence>
          {showAdvanced && (
            <motion.div
              key="advanced"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden border-t border-zinc-200/60 bg-white"
            >
              <div className="px-6 py-4 space-y-4 max-h-72 overflow-y-auto">
                <div className="flex items-center gap-4">
                  <label className="text-sm font-medium text-zinc-700">
                    Retrieved chunks: <span className="font-mono tabular-nums text-brand-700">{topK}</span>
                  </label>
                  <input
                    type="range" min={1} max={20} value={topK}
                    onChange={(e) => setTopK(+e.target.value)}
                    className="flex-1 max-w-xs accent-brand-600"
                  />
                </div>
                {lastResponse ? (
                  <>
                    <PipelineViz stageLog={lastResponse.stage_log} />
                    <MetricsPanel response={lastResponse} />
                  </>
                ) : (
                  <p className="text-sm text-zinc-400">
                    Pipeline stages and evaluation metrics appear here after your first question.
                  </p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Input */}
        <div className="border-t border-zinc-200/60 bg-white p-4">
          <form onSubmit={sendQuery} className="flex gap-3 max-w-4xl mx-auto">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendQuery(e as any); } }}
              placeholder={activeCorpusId ? "Ask a research question… (Enter to send)" : "Choose a PDF library first"}
              disabled={!activeCorpusId || loading}
              rows={2}
              className="input flex-1 resize-none"
            />
            <div className="flex flex-col gap-2 self-end">
              <button
                type="button"
                onClick={() => setShowAdvanced((v) => !v)}
                className={`p-2 rounded-lg border transition-colors ${
                  showAdvanced
                    ? "bg-brand-50 border-brand-200 text-brand-700"
                    : "bg-white border-zinc-200 text-zinc-400 hover:text-zinc-700"
                }`}
                title="Advanced — pipeline stages, metrics, retrieval settings"
                aria-label="Toggle advanced panel"
              >
                <SlidersHorizontal className="w-4 h-4" strokeWidth={2} />
              </button>
              <button
                type="submit"
                disabled={!question.trim() || loading || !activeCorpusId}
                className="btn-primary px-4 py-2 flex items-center justify-center"
                aria-label="Send question"
              >
                <Send className="w-4 h-4" strokeWidth={2} />
              </button>
            </div>
          </form>
          {messages.length > 0 && (
            <div className="max-w-4xl mx-auto mt-2 flex justify-end">
              <button
                onClick={clearMessages}
                className="text-xs text-zinc-400 hover:text-red-600 flex items-center gap-1 transition-colors"
              >
                <Trash2 className="w-3 h-3" strokeWidth={2} /> Clear chat
              </button>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
