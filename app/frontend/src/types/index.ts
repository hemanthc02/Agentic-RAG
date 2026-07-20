// Shared TypeScript types — mirrors the FastAPI response shapes.

export type LLMMode = "cloud" | "local";
// The app exposes exactly two models: Groq (cloud) and Ollama (offline).
export type ProviderName = "anthropic" | "groq" | "ollama";

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface Corpus {
  id: string;
  user_id: string;
  name: string;
  doc_count: number;
  chunk_count: number;
  created_at: string;
}

export interface Document {
  id: string;
  corpus_id: string;
  filename: string;
  original_name: string;
  page_count: number;
  chunk_count: number;
  file_size: number;
  indexed_at: string;
}

export interface CitedChunk {
  chunk_id: string;
  source: string;
  page: number;
  text: string;
  score: number;
  section?: string;
}

export interface Claim {
  claim_text: string;
  cited_chunk_ids: string[];
  cited_chunks: CitedChunk[];
  faithfulness_score: number;
  verdict: boolean;
}

export interface StageLogEntry {
  stage: "planner" | "retriever" | "synthesizer" | "verifier";
  latency_ms: number;
  sub_questions?: string[];
  chunks_found?: number;
  top_score?: number;
  crag_triggered?: boolean;
  claims?: number;
  failed?: number;
  overall_faithfulness?: number;
  will_revise?: boolean;
  revision?: number;
  answer_len?: number;
  error?: string;
}

export interface QueryResponse {
  question: string;
  answer: string;
  sub_questions: string[];
  claims: Claim[];
  sources: CitedChunk[];
  overall_faithfulness: number;
  mode: LLMMode;
  provider: string;
  latency_ms: number;
  retries: number;
  stage_log: StageLogEntry[];
  is_cached: boolean;
  error?: string;
}

export interface QueryHistoryItem extends QueryResponse {
  id: string;
  user_id: string;
  corpus_id: string;
  created_at: string;
}

export interface SystemConfig {
  default_mode: LLMMode;
  default_provider: ProviderName;
  available_providers: { cloud: ProviderName[]; local: ProviderName[] };
  provider_models: Record<ProviderName, string>;
  faithfulness_threshold: number;
  retrieval_relevance_threshold: number;
  max_verifier_retries: number;
  embedding_model: string;
  nli_model: string;
  max_pdfs_per_corpus: number;
  score_green_min: number;
  score_amber_min: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: QueryResponse;
  timestamp: string;
}

export interface NetworkStatus {
  cloud: Record<string, boolean>;
  local: { ollama: boolean; models: string[] };
  any_cloud: boolean;
  ollama_available: boolean;
}

// ── Conversations ──────────────────────────────────────────────────────────

export type ConvMode = "rag" | "guide" | "viva";

export interface Conversation {
  id: string;
  user_id: string;
  corpus_id: string | null;
  title: string;
  mode: ConvMode;
  created_at: string;
  updated_at: string;
  messages?: Message[];
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  query_id?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ── Settings ───────────────────────────────────────────────────────────────

export interface UserSettings {
  user_id: string;
  llm_mode: LLMMode;
  provider: ProviderName;
  ollama_host: string;
  ollama_port: number;
  ollama_model: string;
  groq_model: string;
  groq_api_key: string;
  groq_api_key_masked: string;
  updated_at: string;
}

export interface ConnectionTestResult {
  ok: boolean;
  models: string[];
  error?: string;
}

// ── Research ───────────────────────────────────────────────────────────────

export interface Paper {
  title: string;
  authors: string[];
  year: number | null;
  abstract: string;
  citations: number;
  venue: string;
  pdf_url: string | null;
  source: "semantic_scholar" | "arxiv";
  external_ids: Record<string, string>;
}

export interface KGNode {
  id: string;
  corpus_id: string;
  entity: string;
  entity_type: string;
  description: string;
  source_chunk_id: string;
}

export interface KGEdge {
  id: string;
  source_entity: string;
  target_entity: string;
  relation: string;
}

export interface VivaEvaluation {
  score: number;
  verdict: "strong" | "acceptable" | "needs_improvement";
  correct_points: string[];
  missed_points: string[];
  feedback: string;
  follow_up: string;
  supporting_chunks: Array<{ source: string; page: number; text: string }>;
  latency_ms: number;
}
