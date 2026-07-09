import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import {
  Search, Download, ExternalLink, Loader, BookOpen,
  Calendar, Quote, FileText,
} from "lucide-react";
import { researchApi } from "../api/client";
import { useStore } from "../store/useStore";
import type { Paper } from "../types";

export default function PaperFinderPage() {
  const { activeCorpusId, corpora, mode, provider } = useStore();
  const [query, setQuery] = useState("");
  const [papers, setPapers] = useState<Paper[]>([]);
  const [searching, setSearching] = useState(false);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [expandedAbstract, setExpandedAbstract] = useState<string | null>(null);

  const corpus = corpora.find((c) => c.id === activeCorpusId);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setPapers([]);
    try {
      const { data } = await researchApi.searchPapers({
        query: query.trim(),
        limit: 12,
        expand_query: true,
        mode,
        provider,
      });
      setPapers(data.papers);
      if (data.papers.length === 0) toast("No papers found for this query");
    } catch (err: any) {
      toast.error("Search failed: " + (err.response?.data?.detail ?? "Unknown error"));
    } finally {
      setSearching(false);
    }
  }

  async function download(paper: Paper) {
    if (!activeCorpusId) return toast.error("Select a corpus first");
    if (!paper.pdf_url) return toast.error("No open-access PDF available for this paper");
    setDownloading(paper.title);
    try {
      const { data } = await researchApi.downloadPaper({
        pdf_url: paper.pdf_url,
        corpus_id: activeCorpusId,
        title: paper.title,
      });
      if (data.success) {
        toast.success(`Downloaded & indexed: ${data.filename} (${data.chunk_count} chunks)`);
      } else {
        toast.error(data.error ?? "Download failed");
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Download failed");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="h-full overflow-y-auto bg-canvas">
      <div className="max-w-4xl mx-auto px-6 py-10 space-y-8">

        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 flex items-center gap-2">
            <Search className="w-6 h-6 text-brand-600" /> Paper finder
          </h1>
          <p className="text-zinc-500 text-sm mt-1 max-w-[65ch]">
            Search Semantic Scholar + arXiv. Open-access papers can be auto-downloaded into your corpus.
          </p>
          {corpus && (
            <p className="text-brand-700 text-xs mt-1">
              Downloads go to: <strong>{corpus.name}</strong>
            </p>
          )}
          {!activeCorpusId && (
            <p className="text-amber-600 text-xs mt-1">
              Choose a PDF library on the Ask tab to enable auto-download.
            </p>
          )}
        </div>

        {/* Search bar */}
        <form onSubmit={search} className="flex gap-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. corrective RAG citation faithfulness, agentic retrieval NLI verification…"
            className="input flex-1 text-sm"
          />
          <button type="submit" disabled={searching || !query.trim()}
            className="btn-primary px-5 flex items-center gap-2 transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50">
            {searching ? <Loader className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {searching ? "Searching…" : "Search"}
          </button>
        </form>

        {/* Empty state + suggested queries */}
        {papers.length === 0 && !searching && (
          <div className="py-10 flex flex-col items-center text-center">
            <BookOpen className="w-8 h-8 text-zinc-400 mb-3" />
            <p className="text-sm text-zinc-500 mb-5">
              Search for a topic to find open-access papers you can add to your corpus.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {[
                "retrieval augmented generation survey",
                "knowledge graph question answering",
                "LLM hallucination detection",
                "NLI natural language inference",
                "CRAG corrective retrieval",
                "self-RAG reflection tokens",
              ].map((s) => (
                <button key={s} onClick={() => setQuery(s)}
                  className="text-xs px-3 py-1.5 rounded-full bg-white border border-zinc-200/60 text-zinc-500 hover:text-zinc-900 hover:border-brand-200 transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        <AnimatePresence>
          {papers.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <p className="text-zinc-500 text-xs mb-2">
                <span className="font-mono tabular-nums">{papers.length}</span> results ·{" "}
                <span className="font-mono tabular-nums">{papers.filter((p) => p.pdf_url).length}</span> open access
              </p>

              <div className="bg-white border border-zinc-200/60 rounded-2xl">
                {papers.map((paper, i) => (
                  <motion.div key={i}
                    initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="px-5 py-4 border-b border-zinc-200/60 last:border-b-0">

                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-zinc-900 text-sm leading-snug mb-1.5">
                          {paper.title}
                        </h3>

                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500 mb-2">
                          {paper.authors.length > 0 && (
                            <span>{paper.authors.slice(0, 3).join(", ")}{paper.authors.length > 3 ? " et al." : ""}</span>
                          )}
                          {paper.year && (
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" /><span className="font-mono tabular-nums">{paper.year}</span>
                            </span>
                          )}
                          {paper.citations > 0 && (
                            <span className="flex items-center gap-1">
                              <Quote className="w-3 h-3" /><span className="font-mono tabular-nums">{paper.citations}</span> citations
                            </span>
                          )}
                          <span className="badge bg-brand-50 text-brand-700 border-brand-200">
                            {paper.source === "arxiv" ? "arXiv" : "Semantic Scholar"}
                          </span>
                          {paper.pdf_url ? (
                            <span className="text-emerald-600 flex items-center gap-1">
                              <FileText className="w-3 h-3" /> Open access
                            </span>
                          ) : (
                            <span className="text-zinc-400">No free PDF</span>
                          )}
                        </div>

                        {paper.abstract && (
                          <div>
                            <p className={`text-xs text-zinc-500 leading-relaxed max-w-[65ch] ${
                              expandedAbstract === paper.title ? "" : "line-clamp-2"
                            }`}>
                              {paper.abstract}
                            </p>
                            {paper.abstract.length > 150 && (
                              <button
                                onClick={() => setExpandedAbstract(
                                  expandedAbstract === paper.title ? null : paper.title
                                )}
                                className="text-xs text-brand-600 hover:text-brand-700 mt-1 transition focus-visible:ring-2 focus-visible:ring-brand-500">
                                {expandedAbstract === paper.title ? "Show less" : "Read more"}
                              </button>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="flex flex-col gap-2 flex-shrink-0">
                        {paper.pdf_url ? (
                          <button
                            onClick={() => download(paper)}
                            disabled={downloading === paper.title || !activeCorpusId}
                            className="btn-primary text-xs flex items-center gap-1.5 px-3 py-1.5 whitespace-nowrap transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
                            title={!activeCorpusId ? "Select a corpus first" : "Download & add to corpus"}
                          >
                            {downloading === paper.title
                              ? <Loader className="w-3 h-3 animate-spin" />
                              : <Download className="w-3 h-3" />}
                            {downloading === paper.title ? "Downloading…" : "Add to corpus"}
                          </button>
                        ) : (
                          <span className="text-xs text-zinc-400 px-3 py-1.5">Paywalled</span>
                        )}

                        {paper.external_ids.ArXiv && (
                          <a
                            href={`https://arxiv.org/abs/${paper.external_ids.ArXiv}`}
                            target="_blank" rel="noopener noreferrer"
                            className="btn-ghost text-xs flex items-center gap-1.5 px-3 py-1.5 transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500"
                          >
                            <ExternalLink className="w-3 h-3" /> arXiv
                          </a>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Loading skeleton */}
        {searching && (
          <div className="space-y-4" aria-busy="true">
            <p className="text-xs text-zinc-500">Searching Semantic Scholar + arXiv…</p>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="border-b border-zinc-200/60 pb-4 space-y-2">
                <div className="animate-pulse bg-zinc-100 rounded h-4 w-3/4" />
                <div className="animate-pulse bg-zinc-100 rounded h-3 w-1/2" />
                <div className="animate-pulse bg-zinc-100 rounded h-3 w-full" />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
