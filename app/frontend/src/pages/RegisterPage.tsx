import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import toast from "react-hot-toast";
import { ArrowLeft, FileCheck2, ShieldCheck, WifiOff } from "lucide-react";
import { authApi } from "../api/client";
import { useStore } from "../store/useStore";

export default function RegisterPage() {
  const navigate = useNavigate();
  const { setAuth, setUserSettings, setMode, setProvider } = useStore();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPasswordError(null);
    if (password.length < 8) {
      setPasswordError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      const { data } = await authApi.register(email, name, password);
      setAuth(data.user, data.access_token);
      const settings = (data as any).settings;
      if (settings) {
        setUserSettings(settings as any);
        if (settings.llm_mode) setMode(settings.llm_mode as any);
        if (settings.provider) setProvider(settings.provider as any);
      }
      toast.success("Account created! Welcome aboard.");
      navigate("/app");
    } catch (err: any) {
      setError(err.response?.data?.detail ?? "Registration failed. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[100dvh] bg-canvas grid lg:grid-cols-2">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-center bg-brand-50 border-r border-zinc-200/60 px-16">
        <div className="max-w-md">
          <p className="text-lg font-semibold tracking-tight text-brand-700">VeritasRAG</p>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-zinc-900 max-w-[65ch]">
            Research answers with receipts.
          </h2>
          <ul className="mt-8 flex flex-col gap-6">
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white border border-brand-200 text-brand-700">
                <FileCheck2 className="w-4 h-4" />
              </span>
              <div>
                <p className="text-sm font-medium text-zinc-900">Verified citations</p>
                <p className="mt-1 text-sm text-zinc-500 max-w-[65ch]">
                  Every citation is checked against its source by an NLI model before it reaches you.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white border border-brand-200 text-brand-700">
                <WifiOff className="w-4 h-4" />
              </span>
              <div>
                <p className="text-sm font-medium text-zinc-900">Offline privacy</p>
                <p className="mt-1 text-sm text-zinc-500 max-w-[65ch]">
                  Run fully offline with local models — your documents never leave your machine.
                </p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white border border-brand-200 text-brand-700">
                <ShieldCheck className="w-4 h-4" />
              </span>
              <div>
                <p className="text-sm font-medium text-zinc-900">Faithfulness scoring</p>
                <p className="mt-1 text-sm text-zinc-500 max-w-[65ch]">
                  Each answer carries a per-claim faithfulness score, so you know what to trust.
                </p>
              </div>
            </li>
          </ul>
        </div>
      </div>

      {/* Form side */}
      <div className="flex flex-col px-6 py-8 sm:px-12 lg:px-16">
        <div>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-zinc-500 hover:text-zinc-900 transition rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <ArrowLeft className="w-4 h-4" />
            Back
          </Link>
        </div>

        <motion.div
          className="w-full max-w-md my-auto py-12"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Create your account</h1>
          <p className="mt-2 text-sm text-zinc-500">Free to start. No credit card required.</p>

          <form onSubmit={submit} noValidate className="mt-8 flex flex-col gap-5">
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-zinc-900 mb-1.5">
                Name
              </label>
              <input
                id="name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                autoComplete="name"
                className="input"
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zinc-900 mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                className="input"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-zinc-900 mb-1.5">
                Password <span className="text-zinc-400 font-normal">(min 8 characters)</span>
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                className="input"
              />
              {passwordError && (
                <p role="alert" className="mt-2 text-sm text-red-600">
                  {passwordError}
                </p>
              )}
              {error && (
                <p role="alert" className="mt-2 text-sm text-red-600">
                  {error}
                </p>
              )}
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full mt-1 transition active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? "Creating account…" : "Create account"}
            </button>
            <p className="text-sm text-zinc-500">
              Already registered?{" "}
              <Link
                to="/login"
                className="font-medium text-brand-700 hover:text-brand-600 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              >
                Sign in
              </Link>
            </p>
          </form>
        </motion.div>
      </div>
    </div>
  );
}
