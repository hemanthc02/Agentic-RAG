import type { NetworkStatus } from "../types";

interface Props {
  status: NetworkStatus | null;
  compact?: boolean;
}

export default function StatusBadge({ status, compact = false }: Props) {
  if (!status) {
    return (
      <span className="badge bg-zinc-50 text-zinc-500 border border-zinc-200/60 text-xs">
        Checking…
      </span>
    );
  }

  const hasCloud = status.any_cloud;
  const hasOllama = status.ollama_available;

  if (compact) {
    return (
      <div className="flex gap-1">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${hasCloud ? "bg-emerald-500" : "bg-red-500"}`} />
        <span className={`w-2 h-2 rounded-full flex-shrink-0 mt-1 ${hasOllama ? "bg-emerald-500" : "bg-zinc-300"}`} />
      </div>
    );
  }

  return (
    <div className="flex gap-2 flex-wrap">
      <span className={`badge text-xs inline-flex items-center gap-1.5 ${
        hasCloud
          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
          : "bg-red-50 text-red-700 border border-red-200"}`}>
        <span className={`w-2 h-2 rounded-full ${hasCloud ? "bg-emerald-500" : "bg-red-500"}`} />
        {hasCloud ? "Cloud online" : "Cloud offline"}
      </span>
      <span className={`badge text-xs inline-flex items-center gap-1.5 ${
        hasOllama
          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
          : "bg-zinc-50 text-zinc-500 border border-zinc-200/60"}`}>
        <span className={`w-2 h-2 rounded-full ${hasOllama ? "bg-emerald-500" : "bg-zinc-300"}`} />
        {hasOllama ? "Ollama ready" : "Ollama offline"}
      </span>
      {hasOllama && status.local.models.length > 0 && (
        <span className="badge text-xs bg-zinc-50 text-zinc-500 border border-zinc-200/60 font-mono">
          {status.local.models[0]}
          {status.local.models.length > 1 && ` +${status.local.models.length - 1}`}
        </span>
      )}
    </div>
  );
}
