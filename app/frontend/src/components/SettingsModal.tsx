import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import { Settings, X, CheckCircle, XCircle, Loader, Cloud, Monitor } from "lucide-react";
import { settingsApi } from "../api/client";
import { useStore } from "../store/useStore";
import type { UserSettings } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
}

type TestState = "idle" | "testing" | "ok" | "fail";

export default function SettingsModal({ open, onClose }: Props) {
  const { setUserSettings, setMode, setProvider } = useStore();

  const [form, setForm] = useState<Partial<UserSettings> & { groq_api_key: string }>({
    llm_mode: "cloud",
    provider: "anthropic",
    ollama_host: "http://localhost",
    ollama_port: 11434,
    ollama_model: "phi4-mini",
    groq_model: "claude-sonnet-5",
    groq_api_key: "",
  });
  const [ollamaTest, setOllamaTest] = useState<TestState>("idle");
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
                      {m === "local" ? "Offline (Ollama)" : "Online (Claude)"}
                    </button>
                  ))}
                </div>
                <p className={`text-xs mt-2 flex items-center gap-1.5 ${isOffline ? "text-emerald-700" : "text-amber-700"}`}>
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${isOffline ? "bg-emerald-500" : "bg-amber-500"}`} />
                  {isOffline
                    ? "Nothing leaves your device"
                    : "Questions + retrieved chunks sent to Anthropic (HTTPS)"}
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

              {/* Models in use (read-only — no keys are entered in the app) */}
              <section>
                <label className="text-xs font-semibold text-zinc-500 uppercase tracking-wider block mb-3">
                  Models in use
                </label>
                <div className="space-y-2.5">
                  <div className="rounded-xl border border-zinc-200/60 bg-zinc-50 px-4 py-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-zinc-900">Claude Sonnet 5</p>
                      <p className="text-xs text-zinc-500 mt-0.5">Online — writes answers in the cloud (fast)</p>
                    </div>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-brand-50 text-brand-700 border border-brand-200 font-medium">Online</span>
                  </div>
                  <div className="rounded-xl border border-zinc-200/60 bg-zinc-50 px-4 py-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-zinc-900">phi4-mini</p>
                      <p className="text-xs text-zinc-500 mt-0.5">Offline — writes answers on your device (private)</p>
                    </div>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">Offline</span>
                  </div>
                  <div className="rounded-xl border border-zinc-200/60 bg-zinc-50 px-4 py-3 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-zinc-900">MiniLM · DeBERTa NLI</p>
                      <p className="text-xs text-zinc-500 mt-0.5">Meaning search &amp; citation verification (always local)</p>
                    </div>
                    <span className="text-xs px-2.5 py-1 rounded-full bg-zinc-100 text-zinc-600 border border-zinc-200 font-medium">Local</span>
                  </div>
                  <p className="text-xs text-zinc-400 pt-1">
                    API keys are configured securely on the server — nothing sensitive is entered in the app.
                  </p>
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
