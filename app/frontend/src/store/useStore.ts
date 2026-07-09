import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  ChatMessage, Conversation, ConvMode, Corpus, Document, LLMMode,
  NetworkStatus, ProviderName, QueryResponse, SystemConfig, User, UserSettings,
} from "../types";

interface AppState {
  // Auth
  user: User | null;
  token: string | null;
  setAuth: (user: User, token: string) => void;
  logout: () => void;

  // System
  systemConfig: SystemConfig | null;
  setSystemConfig: (cfg: SystemConfig) => void;
  networkStatus: NetworkStatus | null;
  setNetworkStatus: (s: NetworkStatus) => void;

  // User settings
  userSettings: UserSettings | null;
  setUserSettings: (s: UserSettings) => void;

  // Corpora
  corpora: Corpus[];
  setCorpora: (c: Corpus[]) => void;
  activeCorpusId: string | null;
  setActiveCorpus: (id: string | null) => void;

  // Documents in active corpus
  documents: Document[];
  setDocuments: (d: Document[]) => void;

  // PDF upload — kept in the store (not component state) so navigating to
  // another tab mid-upload doesn't lose the queue or the progress bar.
  uploadQueue: File[];
  setUploadQueue: (f: File[] | ((prev: File[]) => File[])) => void;
  uploading: boolean;
  setUploading: (b: boolean) => void;
  uploadProgress: number;
  setUploadProgress: (n: number) => void;

  // Query
  mode: LLMMode;
  provider: ProviderName;
  topK: number;
  setMode: (m: LLMMode) => void;
  setProvider: (p: ProviderName) => void;
  setTopK: (k: number) => void;

  // Current session chat (in-memory, not persisted)
  messages: ChatMessage[];
  addMessage: (m: ChatMessage) => void;
  clearMessages: () => void;
  loading: boolean;
  setLoading: (b: boolean) => void;

  // Persistent conversations (sidebar)
  conversations: Conversation[];
  setConversations: (c: Conversation[]) => void;
  activeConvId: string | null;
  setActiveConvId: (id: string | null) => void;
  addConversation: (c: Conversation) => void;
  removeConversation: (id: string) => void;
  renameConversation: (id: string, title: string) => void;

  // Current page/mode
  activePage: "rag" | "guide" | "viva" | "papers";
  setActivePage: (p: "rag" | "guide" | "viva" | "papers") => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      setAuth: (user, token) => {
        localStorage.setItem("token", token);
        set({ user, token });
      },
      logout: () => {
        localStorage.removeItem("token");
        set({
          user: null, token: null, corpora: [], documents: [],
          messages: [], conversations: [], activeConvId: null,
          userSettings: null,
        });
      },

      systemConfig: null,
      setSystemConfig: (cfg) => set({ systemConfig: cfg }),
      networkStatus: null,
      setNetworkStatus: (s) => set({ networkStatus: s }),

      userSettings: null,
      setUserSettings: (s) => set({ userSettings: s }),

      corpora: [],
      setCorpora: (c) => set({ corpora: c }),
      activeCorpusId: null,
      setActiveCorpus: (id) => set({ activeCorpusId: id }),

      documents: [],
      setDocuments: (d) => set({ documents: d }),

      uploadQueue: [],
      setUploadQueue: (f) =>
        set((s) => ({ uploadQueue: typeof f === "function" ? f(s.uploadQueue) : f })),
      uploading: false,
      setUploading: (b) => set({ uploading: b }),
      uploadProgress: 0,
      setUploadProgress: (n) => set({ uploadProgress: n }),

      mode: "cloud",
      provider: "groq",
      topK: 5,
      setMode: (m) => set({ mode: m }),
      setProvider: (p) => set({ provider: p }),
      setTopK: (k) => set({ topK: k }),

      messages: [],
      addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
      clearMessages: () => set({ messages: [] }),
      loading: false,
      setLoading: (b) => set({ loading: b }),

      conversations: [],
      setConversations: (c) => set({ conversations: c }),
      activeConvId: null,
      setActiveConvId: (id) => set({ activeConvId: id }),
      addConversation: (c) =>
        set((s) => ({ conversations: [c, ...s.conversations] })),
      removeConversation: (id) =>
        set((s) => ({
          conversations: s.conversations.filter((c) => c.id !== id),
          activeConvId: s.activeConvId === id ? null : s.activeConvId,
        })),
      renameConversation: (id, title) =>
        set((s) => ({
          conversations: s.conversations.map((c) =>
            c.id === id ? { ...c, title } : c
          ),
        })),

      activePage: "rag",
      setActivePage: (p) => set({ activePage: p }),
    }),
    {
      name: "rag-store",
      partialize: (s) => ({
        user: s.user, token: s.token,
        mode: s.mode, provider: s.provider, topK: s.topK,
        activeCorpusId: s.activeCorpusId, activePage: s.activePage,
      }),
    },
  ),
);
