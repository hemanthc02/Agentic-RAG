import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { Settings, X, Eye, EyeOff, CheckCircle, XCircle, Loader, Cloud, Monitor } from "lucide-react";
import { settingsApi } from "../api/client";
import { useStore } from "../store/useStore";
import type { UserSettings } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
}

type TestState = "idle" | "testing" | "ok" | "fail";

export default function SettingsModal({ open, onClose }: Props) {
  const { userSettings, setUserSettings, setMode, setProvider } = useStore();

  const [form, setForm] = useState<Partial<UserSettings> & { groq_api_key: string }>({
    llm_mode: "cloud",
    provider: "groq",
    ollama_host: "http://localhost",
    ollama_port: 11434,
    ollama_model: "phi3:mini",
    groq_model: "meta-llama/llama-4-scout-17b-16e-instruct",
    groq_api_key: "",
  });
  const [showKey, setShowKey] = useState(false);
  const [ollamaTest, setOllamaTest] = useState<TestState>("idle");
  const [groqTest, setGroqTest] = useState<TestState>("idle");
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  // Load settings when modal opens
  useEffect(() => {
    if (!open) return;
    settingsApi.get().then((r) => {
      setUserSettings(r.data);
      setForm((f) => ({
        ...f,
        llm_mode: r.data.llm_mode,
        provider: r.data.provider,
        ollama_host: r.data.ollama_host,
        ollama_port: r.data.ollama_port,
        ollama_model: r.data.ollama_model,
        groq_model: r.data.groq_model,
        groq_api_key: "",
      }));
    }).catch(() => {});
  }, [open]);

  function patch<K extends keyof typeof form>(key: K, value: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function testOllama() {
    setOllamaTest("testing");
    try {
      const { data } = await settingsApi.testOllama(
        form.ollama_host ?? "http://localhost",
        form.ollama_port ?? 11434,
      );
      setOllamaTest(data.ok ? "ok" : "fail");
      if (data.ok) setOllamaModels(data.models);
    } catch {
      setOllamaTest("fail");
    }
  }

  async function testGroq() {
    setGroqTest("testing");
    try {
      const { data } = await settingsApi.testGroq(form.groq_api_key);
      setGroqTest(data.ok ? "ok" : "fail");
      if (!data.ok) toast.error(data.error ?? "Invalid API key");
    } catch {
      setGroqTest("fail");
    }
  }

  async function save() {
    setSaving(true);
    try {
      const { data } = await settingsApi.save(form);
      setUserSettings(data);
      // Sync global mode/provider
      setMode(data.llm_mode as any);
      setProvider(data.provider as any);
      toast.success("Settings saved");
      onClose();
    } catch {
      toast.error("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  const isOffline = form.llm_mode === "local";

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/30 backdrop-blur-sm"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            className="w-full max-w-lg bg-white border border-zinc-200/60 rounded-2xl shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)] overflow-hidden"
            initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200/60">
              <div className="flex items-center gap-2">
                <Settings className="w-5 h-5 text-brand-600" />
                <h2 className="font-semibold text-zinc-900 tracking-tight">Settings</h2>
              </div>
              <button onClick={onClose}
                className="btn-ghost p-1.5 rounded-lg transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-6 space-y-6 overflow-y-auto max-h-[70vh]">

              {/* Mode toggle */}
              <section>
                <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider block mb-3">
                  Mode
                </label>
                <div className="flex gap-2">
                  {(["cloud", "local"] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => patch("llm_mode", m)}
                      className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition-all duration-150
                        active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500
                        flex items-center justify-center gap-2 ${
                        form.llm_mode === m
                          ? m === "local"
                            ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                            : "bg-brand-50 border-brand-200 text-brand-700"
                          : "bg-white border-zinc-200/60 text-zinc-500 hover:bg-zinc-50"
                      }`}
                    >
                      {m === "local" ? <Monitor className="w-4 h-4" /> : <Cloud className="w-4 h-4" />}
                      {m === "local" ? "Offline (Ollama)" : "Online (Groq)"}
                    </button>
                  ))}
                </div>
                <p className={`text-xs mt-2 flex items-center gap-1.5 ${isOffline ? "text-emerald-700" : "text-amber-700"}`}>
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isOffline ? "bg-emerald-500" : "bg-amber-500"}`} />
                  {isOffline
                    ? "Nothing leaves your device"
                    : "Questions + retrieved chunks sent to Groq (HTTPS)"}
                </p>
              </section>

              {/* Offline / Ollama settings */}
              <section className={isOffline ? "" : "opacity-50 pointer-events-none"}>
                <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider block mb-3">
                  Ollama (Offline)
                </label>
                <div className="space-y-3">
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <label className="text-xs text-zinc-500 mb-1 block">Host</label>
                      <input
                        className="input text-sm py-2 w-full"
                        value={form.ollama_host}
                        onChange={(e) => patch("ollama_host", e.target.value)}
                        placeholder="http://localhost"
                      />
                    </div>
                    <div className="w-28">
                      <label className="text-xs text-zinc-500 mb-1 block">Port</label>
                      <input
                        type="number"
                        className="input text-sm py-2 w-full font-mono tabular-nums"
                        value={form.ollama_port}
                        onChange={(e) => patch("ollama_port", +e.target.value)}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Model</label>
                    <input
                      className="input text-sm py-2 w-full"
                      value={form.ollama_model}
                      onChange={(e) => patch("ollama_model", e.target.value)}
                      placeholder="phi3:mini"
                    />
                    {ollamaModels.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {ollamaModels.map((m) => (
                          <button key={m} onClick={() => patch("ollama_model", m)}
                            className="text-xs px-2 py-0.5 rounded bg-zinc-50 border border-zinc-200/60 text-zinc-600 hover:bg-brand-50 hover:text-brand-700 hover:border-brand-200 transition-colors">
                            {m}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <button onClick={testOllama} disabled={ollamaTest === "testing"}
                    className="btn-ghost text-sm flex items-center gap-2 py-2 transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
                    <TestIcon state={ollamaTest} />
                    {ollamaTest === "testing" ? "Testing…" : "Test connection"}
                  </button>
                  {ollamaTest === "ok" && (
                    <p className="text-xs px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700">
                      Connected. {ollamaModels.length} model{ollamaModels.length === 1 ? "" : "s"} available.
                    </p>
                  )}
                  {ollamaTest === "fail" && (
                    <p className="text-xs px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-red-600">
                      Connection failed. Check the host and port, then try again.
                    </p>
                  )}
                </div>
              </section>

              {/* Online / Groq settings */}
              <section className={!isOffline ? "" : "opacity-50 pointer-events-none"}>
                <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider block mb-3">
                  Groq (Online)
                </label>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Groq API Key</label>
                    <div className="relative">
                      <input
                        type={showKey ? "text" : "password"}
                        className="input text-sm py-2 w-full pr-10"
                        value={form.groq_api_key}
                        onChange={(e) => patch("groq_api_key", e.target.value)}
                        placeholder={userSettings?.groq_api_key_masked || "gsk_…"}
                      />
                      <button
                        onClick={() => setShowKey((v) => !v)}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-900 transition-colors"
                      >
                        {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                    <p className="text-xs text-zinc-500 mt-1">
                      Leave blank to keep existing key. Get a free key at console.groq.com
                    </p>
                  </div>

                  <div>
                    <label className="text-xs text-zinc-500 mb-1 block">Model</label>
                    <select className="input text-sm py-2 w-full"
                      value={form.groq_model}
                      onChange={(e) => patch("groq_model", e.target.value)}>
                      <option value="meta-llama/llama-4-scout-17b-16e-instruct">Llama 4 Scout 17B</option>
                      <option value="meta-llama/llama-4-maverick-17b-128e-instruct">Llama 4 Maverick 17B</option>
                      <option value="llama-3.3-70b-versatile">Llama 3.3 70B</option>
                      <option value="mixtral-8x7b-32768">Mixtral 8x7B</option>
                      <option value="gemma2-9b-it">Gemma 2 9B</option>
                    </select>
                  </div>

                  <button onClick={testGroq} disabled={groqTest === "testing"}
                    className="btn-ghost text-sm flex items-center gap-2 py-2 transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
                    <TestIcon state={groqTest} />
                    {groqTest === "testing" ? "Testing…" : "Validate API key"}
                  </button>
                  {groqTest === "ok" && (
                    <p className="text-xs px-3 py-2 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700">
                      API key valid.
                    </p>
                  )}
                  {groqTest === "fail" && (
                    <p className="text-xs px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-red-600">
                      Validation failed. Check the API key, then try again.
                    </p>
                  )}
                </div>
              </section>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-200/60 bg-zinc-50">
              <button onClick={onClose}
                className="btn-ghost text-sm transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
                Cancel
              </button>
              <button onClick={save} disabled={saving}
                className="btn-primary text-sm px-5 transition duration-150 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500">
                {saving ? "Saving…" : "Save settings"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function TestIcon({ state }: { state: TestState }) {
  if (state === "testing") return <Loader className="w-4 h-4 animate-spin text-zinc-400" />;
  if (state === "ok") return <CheckCircle className="w-4 h-4 text-emerald-600" />;
  if (state === "fail") return <XCircle className="w-4 h-4 text-red-600" />;
  return null;
}
