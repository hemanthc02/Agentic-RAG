import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import {
  MessageSquare, Plus, Trash2, Pencil, Check, X, BookOpen, GraduationCap, Search,
} from "lucide-react";
import { conversationsApi } from "../api/client";
import { useStore } from "../store/useStore";
import type { ConvMode, Conversation } from "../types";

const MODE_ICON: Record<ConvMode, React.ReactNode> = {
  rag:   <MessageSquare className="w-3.5 h-3.5" />,
  guide: <BookOpen className="w-3.5 h-3.5" />,
  viva:  <GraduationCap className="w-3.5 h-3.5" />,
};

const MODE_LABEL: Record<ConvMode, string> = {
  rag: "RAG",
  guide: "Guide",
  viva: "Viva",
};

interface Props {
  currentMode: ConvMode;
  onNewConv: (conv: Conversation) => void;
  onSelectConv: (conv: Conversation) => void;
}

export default function ConversationSidebar({ currentMode, onNewConv, onSelectConv }: Props) {
  const {
    conversations, setConversations, activeConvId, setActiveConvId,
    removeConversation, renameConversation, activeCorpusId,
  } = useStore();

  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameVal, setRenameVal] = useState("");
  const renameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    conversationsApi.list(60).then((r) => setConversations(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (renaming) renameRef.current?.focus();
  }, [renaming]);

  async function createNew() {
    const title = `New ${MODE_LABEL[currentMode]} chat`;
    try {
      const { data } = await conversationsApi.create(title, activeCorpusId, currentMode);
      onNewConv(data);
      setActiveConvId(data.id);
    } catch {
      toast.error("Could not create conversation");
    }
  }

  async function deleteConv(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    try {
      await conversationsApi.remove(id);
      removeConversation(id);
    } catch {
      toast.error("Could not delete conversation");
    }
  }

  async function startRename(e: React.MouseEvent, conv: Conversation) {
    e.stopPropagation();
    setRenaming(conv.id);
    setRenameVal(conv.title);
  }

  async function commitRename(id: string) {
    const title = renameVal.trim();
    if (!title) { setRenaming(null); return; }
    try {
      await conversationsApi.rename(id, title);
      renameConversation(id, title);
    } catch {
      toast.error("Could not rename");
    }
    setRenaming(null);
  }

  async function selectConv(conv: Conversation) {
    setActiveConvId(conv.id);
    onSelectConv(conv);
  }

  // Group by date
  const grouped = groupByDate(conversations);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* New chat button */}
      <div className="p-3">
        <button
          onClick={createNew}
          className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg
                     bg-brand-50 hover:bg-brand-100 border border-brand-200
                     text-brand-700 text-sm font-medium transition-colors duration-150
                     active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500"
        >
          <Plus className="w-4 h-4" />
          New {MODE_LABEL[currentMode]} chat
        </button>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-4">
        {Object.entries(grouped).map(([label, convs]) => (
          <div key={label}>
            <p className="text-xs text-zinc-400 font-medium uppercase tracking-wider px-2 mb-1">
              {label}
            </p>
            <div className="space-y-0.5">
              {convs.map((conv) => (
                <motion.div
                  key={conv.id}
                  layout
                  onClick={() => selectConv(conv)}
                  className={`group relative flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer
                              text-sm transition-colors duration-150
                              ${activeConvId === conv.id
                                ? "bg-brand-50 text-brand-700"
                                : "hover:bg-zinc-50 text-zinc-600"}`}
                >
                  <span className={`flex-shrink-0 ${activeConvId === conv.id ? "text-brand-600" : "text-zinc-400"}`}>
                    {MODE_ICON[conv.mode as ConvMode] ?? <MessageSquare className="w-3.5 h-3.5" />}
                  </span>

                  {renaming === conv.id ? (
                    <input
                      ref={renameRef}
                      className="flex-1 bg-transparent outline-none text-zinc-900 text-sm"
                      value={renameVal}
                      onChange={(e) => setRenameVal(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename(conv.id);
                        if (e.key === "Escape") setRenaming(null);
                      }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  ) : (
                    <span className="flex-1 truncate">{conv.title}</span>
                  )}

                  {renaming === conv.id ? (
                    <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                      <button onClick={() => commitRename(conv.id)}
                        className="p-1 text-zinc-400 hover:text-emerald-600 transition-colors"><Check className="w-3.5 h-3.5" /></button>
                      <button onClick={() => setRenaming(null)}
                        className="p-1 text-zinc-400 hover:text-red-600 transition-colors"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  ) : (
                    <div className="hidden group-hover:flex gap-1 flex-shrink-0">
                      <button onClick={(e) => startRename(e, conv)}
                        className="p-1 hover:text-zinc-900 text-zinc-400 transition-colors">
                        <Pencil className="w-3 h-3" />
                      </button>
                      <button onClick={(e) => deleteConv(e, conv.id)}
                        className="p-1 hover:text-red-600 text-zinc-400 transition-colors">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  )}
                </motion.div>
              ))}
            </div>
          </div>
        ))}

        {conversations.length === 0 && (
          <div className="flex flex-col items-center gap-2 pt-8 text-center">
            <MessageSquare className="w-5 h-5 text-zinc-300" />
            <p className="text-zinc-400 text-xs">No conversations yet. Start a new chat above.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function groupByDate(convs: Conversation[]): Record<string, Conversation[]> {
  const now = new Date();
  const today = now.toDateString();
  const yesterday = new Date(now.getTime() - 86400000).toDateString();
  const lastWeek = new Date(now.getTime() - 7 * 86400000);

  const groups: Record<string, Conversation[]> = {};
  for (const c of convs) {
    const d = new Date(c.updated_at);
    let label: string;
    if (d.toDateString() === today) label = "Today";
    else if (d.toDateString() === yesterday) label = "Yesterday";
    else if (d >= lastWeek) label = "Last 7 days";
    else label = d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    (groups[label] ??= []).push(c);
  }
  return groups;
}
