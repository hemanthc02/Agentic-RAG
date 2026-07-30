import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  BookOpen, Cloud, GraduationCap, HardDrive, LogOut,
  MessageSquareText, Search as SearchIcon, Settings, Network,
} from "lucide-react";
import toast from "react-hot-toast";
import { systemApi } from "../api/client";
import { useStore } from "../store/useStore";
import SettingsModal from "./SettingsModal";
import AskPage from "../pages/AskPage";
import ResearchGuidePage from "../pages/ResearchGuidePage";
import VivaPage from "../pages/VivaPage";
import PaperFinderPage from "../pages/PaperFinderPage";
import AgentNetworkPage from "../pages/AgentNetworkPage";
import PdfViewerPanel from "./PdfViewerPanel";
import type { LLMMode } from "../types";

const TABS = [
  { to: "/app",        label: "Ask",            Icon: MessageSquareText, end: true },
  { to: "/app/guide",  label: "Research guide", Icon: BookOpen,          end: false },
  { to: "/app/viva",   label: "Viva",           Icon: GraduationCap,     end: false },
  { to: "/app/papers", label: "Papers",         Icon: SearchIcon,        end: false },
  { to: "/app/agents", label: "Agents",         Icon: Network,           end: false },
];

// Cloud-only build (e.g. deployed to Azure App Service, where the local Ollama
// daemon can't run): set VITE_CLOUD_ONLY=1 at build time to hide the Offline
// toggle and pin the app to online (Claude) mode.
const CLOUD_ONLY = import.meta.env.VITE_CLOUD_ONLY === "1";

export default function WorkspaceLayout() {
  const {
    user, logout, mode, setMode, setProvider,
    networkStatus, setNetworkStatus,
  } = useStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    systemApi.status().then((r) => setNetworkStatus(r.data)).catch(() => {});
  }, []);

  // In a cloud-only build, force online mode on load — offline can't work here.
  useEffect(() => {
    if (CLOUD_ONLY && mode !== "cloud") {
      setMode("cloud");
      setProvider("groq");
    }
  }, []);

  async function switchMode(next: LLMMode) {
    if (next === mode) return;
    setMode(next);
    setProvider(next === "local" ? "ollama" : "groq");

    if (next === "local") {
      // Paper search needs the internet — leave that tab when going offline.
      if (location.pathname.startsWith("/app/papers")) navigate("/app");
      try {
        const { data } = await systemApi.status();
        setNetworkStatus(data);
        if (data.ollama_available) {
          const models = data.local.models;
          toast.success(
            models.length > 0
              ? `Offline mode — local Ollama connected (${models[0]})`
              : "Ollama is running, but no model is pulled yet. Run: ollama pull <model>",
          );
        } else {
          toast.error("Ollama not detected. Start the Ollama app first.");
        }
      } catch {
        toast.error("Couldn't reach the backend to check Ollama status.");
      }
    } else {
      toast.success("Online mode — Anthropic Claude");
    }
  }

  function handleLogout() {
    logout();
    toast.success("Signed out");
    navigate("/");
  }

  const offline = mode === "local";
  const ollamaUp = networkStatus?.ollama_available ?? false;

  // Which tab is visible. All four stay mounted so switching tabs never
  // kills an in-flight query, viva evaluation, or paper search UI.
  const path = location.pathname;
  const activeTab =
    path.startsWith("/app/guide") ? "guide"
    : path.startsWith("/app/viva") ? "viva"
    : path.startsWith("/app/papers") ? "papers"
    : path.startsWith("/app/agents") ? "agents"
    : "ask";

  // Covers deep links / page reloads landing on Papers while offline.
  useEffect(() => {
    if (offline && activeTab === "papers") navigate("/app");
  }, [offline, activeTab]);

  const activeTitle =
    activeTab === "guide" ? "Research guide"
    : activeTab === "viva" ? "Viva preparation"
    : activeTab === "papers" ? "Paper finder"
    : activeTab === "agents" ? "Agent network"
    : "Ask";

  return (
    <div className="h-[100dvh] flex bg-canvas">
      {/* ───────────────────────── Left sidebar ───────────────────────── */}
      <aside className="w-60 flex-shrink-0 flex flex-col bg-white border-r border-zinc-200/70">
        {/* Brand */}
        <Link to="/app" className="flex items-center gap-2.5 h-14 px-5 border-b border-zinc-200/60 flex-shrink-0">
          <span className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm">
            <svg viewBox="0 0 32 32" className="w-4 h-4" fill="none">
              <path d="M9 17l5 5 9-11" stroke="white" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          <span className="flex flex-col leading-none">
            <span className="font-semibold tracking-tight text-zinc-900">VeritasRAG</span>
            <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400 mt-0.5">Agentic RAG</span>
          </span>
        </Link>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Workspace</p>
          <div className="space-y-1">
            {TABS.map(({ to, label, Icon, end }) => {
              // Paper search hits Semantic Scholar/arXiv — meaningless offline.
              if (offline && to === "/app/papers") {
                return (
                  <span
                    key={to}
                    title="Paper search needs the internet — switch to Online mode to use it"
                    onClick={() => toast("Paper search needs the internet. Switch to Online mode first.")}
                    className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-zinc-300 cursor-not-allowed select-none"
                  >
                    <Icon className="w-4 h-4" strokeWidth={2} />
                    {label}
                  </span>
                );
              }
              return (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `relative flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-brand-50 text-brand-700"
                        : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-50"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-brand-600" />
                      )}
                      <Icon className="w-4 h-4" strokeWidth={2} />
                      {label}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        </nav>

        {/* Sidebar footer: model mode + status */}
        <div className="border-t border-zinc-200/60 p-3 space-y-2.5 flex-shrink-0">
          {!CLOUD_ONLY && (
            <div className="flex items-center bg-zinc-100 rounded-xl p-0.5" role="group" aria-label="Model mode">
              <button
                onClick={() => switchMode("cloud")}
                className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-[10px] text-xs font-medium transition-all active:scale-[0.98] ${
                  !offline ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500 hover:text-zinc-700"
                }`}
                title="Anthropic Claude (cloud). Question and retrieved passages leave this device."
              >
                <Cloud className="w-3.5 h-3.5" strokeWidth={2} />
                Online
              </button>
              <button
                onClick={() => switchMode("local")}
                className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-[10px] text-xs font-medium transition-all active:scale-[0.98] ${
                  offline ? "bg-white text-zinc-900 shadow-sm" : "text-zinc-500 hover:text-zinc-700"
                }`}
                title="Ollama local model (phi4-mini). Nothing leaves this device."
              >
                <HardDrive className="w-3.5 h-3.5" strokeWidth={2} />
                Offline
              </button>
            </div>
          )}

          <span
            className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg border ${
              offline
                ? ollamaUp
                  ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                  : "bg-red-50 border-red-200 text-red-700"
                : "bg-brand-50 border-brand-200 text-brand-700"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                offline ? (ollamaUp ? "bg-emerald-500" : "bg-red-500") : "bg-brand-500"
              }`}
            />
            {offline ? (ollamaUp ? "Private — on-device" : "Ollama offline") : "Cloud — Claude"}
          </span>
        </div>
      </aside>

      {/* ───────────────────────── Content column ───────────────────────── */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Top bar: page title + account controls */}
        <header className="flex items-center gap-4 px-6 h-14 bg-white border-b border-zinc-200/60 flex-shrink-0">
          <h1 className="text-sm font-semibold text-zinc-900">{activeTitle}</h1>

          <div className="flex items-center gap-2 ml-auto">
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-2 rounded-lg text-zinc-500 hover:text-zinc-900 hover:bg-zinc-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
              title="Settings"
              aria-label="Settings"
            >
              <Settings className="w-4 h-4" strokeWidth={2} />
            </button>

            <div className="flex items-center gap-2 pl-3 border-l border-zinc-200">
              <span className="w-7 h-7 rounded-lg bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-semibold uppercase">
                {user?.name?.slice(0, 1) ?? "?"}
              </span>
              <span className="hidden lg:block text-sm text-zinc-600">{user?.name}</span>
              <button
                onClick={handleLogout}
                className="p-2 rounded-lg text-zinc-500 hover:text-red-600 hover:bg-red-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut className="w-4 h-4" strokeWidth={2} />
              </button>
            </div>
          </div>
        </header>

        {/* Main content */}
        <div className="flex-1 min-h-0 flex">
          <div className="flex-1 min-w-0 h-full">
            <div className={activeTab === "ask" ? "h-full" : "hidden"}><AskPage /></div>
            <div className={activeTab === "guide" ? "h-full" : "hidden"}><ResearchGuidePage /></div>
            <div className={activeTab === "viva" ? "h-full" : "hidden"}><VivaPage /></div>
            <div className={activeTab === "papers" ? "h-full" : "hidden"}><PaperFinderPage /></div>
            <div className={activeTab === "agents" ? "h-full" : "hidden"}><AgentNetworkPage /></div>
          </div>
          <PdfViewerPanel />
        </div>
      </div>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
