import axios from "axios";
import type {
  ConnectionTestResult, Conversation, Corpus, Document, Message,
  NetworkStatus, Paper, QueryHistoryItem, QueryResponse,
  SystemConfig, User, UserSettings, VivaEvaluation,
} from "../types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "",
  headers: { "Content-Type": "application/json" },
});

// Attach JWT from localStorage on every request
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem("token");
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// Redirect to login on 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);

// Auth
export const authApi = {
  register: (email: string, name: string, password: string) =>
    api.post<{ access_token: string; user: User }>("/api/auth/register", { email, name, password }),
  login: (email: string, password: string) =>
    api.post<{ access_token: string; user: User }>("/api/auth/login", { email, password }),
  me: () => api.get<User>("/api/auth/me"),
};

// Corpora & documents
export const corpusApi = {
  list: () => api.get<Corpus[]>("/api/corpora"),
  create: (name: string) => api.post<Corpus>("/api/corpora", { name }),
  remove: (id: string) => api.delete(`/api/corpora/${id}`),
  listDocs: (corpusId: string) => api.get<Document[]>(`/api/corpora/${corpusId}/documents`),
  upload: (corpusId: string, files: File[], onProgress?: (pct: number) => void) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return api.post(`/api/corpora/${corpusId}/upload`, form, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) => onProgress?.(Math.round((e.loaded / (e.total ?? 1)) * 100)),
    });
  },
  deleteDoc: (corpusId: string, docId: string) =>
    api.delete(`/api/corpora/${corpusId}/documents/${docId}`),
  fileBlob: (corpusId: string, name: string) =>
    api.get(`/api/corpora/${corpusId}/file`, { params: { name }, responseType: "blob" }),
};

// Query
export const queryApi = {
  run: (params: {
    question: string; corpus_id: string; mode: string;
    provider: string; top_k?: number; use_cache?: boolean;
    conversation_id?: string;
  }) => api.post<QueryResponse>("/api/query", params),
  history: (limit = 20) => api.get<QueryHistoryItem[]>(`/api/query/history?limit=${limit}`),
};

// System
export const systemApi = {
  health: () => api.get("/api/health"),
  config: () => api.get<SystemConfig>("/api/config"),
  status: () => api.get<NetworkStatus>("/api/status"),
};

// Settings
export const settingsApi = {
  get: () => api.get<UserSettings>("/api/settings"),
  save: (s: Partial<UserSettings> & { groq_api_key?: string }) =>
    api.put<UserSettings>("/api/settings", s),
  testOllama: (host: string, port: number) =>
    api.post<ConnectionTestResult>(`/api/settings/test-ollama?host=${encodeURIComponent(host)}&port=${port}`),
  testGroq: (api_key?: string) =>
    api.post<ConnectionTestResult>("/api/settings/test-groq", undefined, {
      params: api_key ? { api_key } : {},
    }),
};

// Conversations
export const conversationsApi = {
  list: (limit = 50) => api.get<Conversation[]>(`/api/conversations?limit=${limit}`),
  create: (title: string, corpus_id?: string | null, mode?: string) =>
    api.post<Conversation>("/api/conversations", { title, corpus_id, mode }),
  get: (id: string) => api.get<Conversation & { messages: Message[] }>(`/api/conversations/${id}`),
  rename: (id: string, title: string) =>
    api.patch(`/api/conversations/${id}`, { title }),
  remove: (id: string) => api.delete(`/api/conversations/${id}`),
  addMessage: (convId: string, role: string, content: string, metadata?: object) =>
    api.post<Message>(`/api/conversations/${convId}/messages`, { role, content, metadata }),
};

// Research guide, viva, paper search
export const researchApi = {
  guide: (params: {
    question: string; corpus_id: string; conversation_id?: string;
    mode?: string; provider?: string; top_k?: number; use_react?: boolean;
  }) => api.post<{ answer: string; chunks: object[]; latency_ms: number; react_trace?: object[] }>("/api/research/guide", params),

  gapAnalysis: (corpus_id: string, mode?: string, provider?: string) =>
    api.post<{ analysis: string; chunks: object[]; latency_ms: number }>(
      `/api/research/gap-analysis?corpus_id=${corpus_id}&mode=${mode ?? "cloud"}&provider=${provider ?? "groq"}`
    ),

  createVivaSession: (params: { corpus_id: string; difficulty?: string }) =>
    api.post<{ id: string; difficulty: string; questions: object[]; scores: number[] }>(
      "/api/research/viva/sessions", params
    ),

  listVivaSessions: () =>
    api.get<{ id: string; corpus_id: string; difficulty: string; completed: boolean; created_at: string }[]>(
      "/api/research/viva/sessions"
    ),

  completeVivaSession: (sessionId: string) =>
    api.patch<{ id: string; average_score: number }>(`/api/research/viva/sessions/${sessionId}/complete`),

  vivaQuestion: (params: {
    corpus_id: string; question_type?: string;
    asked_questions?: string[]; session_id?: string | null;
    mode?: string; provider?: string;
  }) => api.post<{ question: string; question_type: string; latency_ms: number }>(
    "/api/research/viva/question", params
  ),

  vivaEvaluate: (params: {
    corpus_id: string; question: string; student_answer: string;
    session_id?: string | null; question_type?: string;
    mode?: string; provider?: string;
  }) => api.post<VivaEvaluation>("/api/research/viva/evaluate", params),

  searchPapers: (params: {
    query: string; limit?: number; expand_query?: boolean; mode?: string; provider?: string;
  }) => api.post<{ papers: Paper[]; count: number; query: string }>("/api/research/papers/search", params),

  downloadPaper: (params: { pdf_url: string; corpus_id: string; title?: string }) =>
    api.post<{ success: boolean; filename?: string; chunk_count?: number; error?: string }>(
      "/api/research/papers/download", params
    ),
};
