import { useEffect, useState } from "react";
import { X, FileText, ExternalLink, Loader } from "lucide-react";
import { corpusApi } from "../api/client";
import { useStore } from "../store/useStore";

function cleanName(src: string) {
  const base = src.split(/[\\/]/).pop() || src;
  return base.replace(/^[0-9a-fA-F]{16,32}_/, "");
}

/** Right-side in-app PDF viewer. Opens the source paper at the retrieved page
 *  when the user clicks a citation / source. Fetches the file with auth as a
 *  blob (no token in the URL) and renders it in an iframe. */
export default function PdfViewerPanel() {
  const { viewingPdf, setViewingPdf } = useStore();
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!viewingPdf) { setUrl(null); return; }
    let objUrl: string | null = null;
    setLoading(true); setError(null); setUrl(null);
    corpusApi.fileBlob(viewingPdf.corpusId, viewingPdf.name)
      .then((r) => {
        const blob = new Blob([r.data], { type: "application/pdf" });
        objUrl = URL.createObjectURL(blob);
        setUrl(`${objUrl}#page=${viewingPdf.page}&view=FitH`);
      })
      .catch(() => setError("Couldn't load this PDF file."))
      .finally(() => setLoading(false));
    return () => { if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [viewingPdf?.corpusId, viewingPdf?.name, viewingPdf?.page]);

  if (!viewingPdf) return null;
  const title = cleanName(viewingPdf.name);

  return (
    <div className="w-[46%] max-w-[760px] min-w-[380px] h-full bg-white border-l border-zinc-200/60 flex flex-col flex-shrink-0">
      <div className="flex items-center gap-2 px-4 h-12 border-b border-zinc-200/60 flex-shrink-0">
        <FileText className="w-4 h-4 text-brand-500 flex-shrink-0" strokeWidth={2} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-zinc-900 truncate" title={title}>{title}</p>
          <p className="text-xs text-zinc-400">retrieved from page {viewingPdf.page}</p>
        </div>
        {url && (
          <a href={url} target="_blank" rel="noreferrer"
             className="p-1.5 rounded-md text-zinc-400 hover:text-brand-700 transition-colors"
             title="Open in a new tab">
            <ExternalLink className="w-4 h-4" />
          </a>
        )}
        <button onClick={() => setViewingPdf(null)}
                className="p-1.5 rounded-md text-zinc-400 hover:text-red-600 transition-colors"
                title="Close viewer" aria-label="Close PDF viewer">
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 min-h-0 bg-zinc-100">
        {loading && (
          <div className="h-full flex items-center justify-center text-zinc-400">
            <Loader className="w-5 h-5 animate-spin" />
          </div>
        )}
        {error && (
          <div className="h-full flex items-center justify-center text-red-500 text-sm px-6 text-center">{error}</div>
        )}
        {url && !loading && !error && (
          <iframe title={title} src={url} className="w-full h-full border-0" />
        )}
      </div>
    </div>
  );
}
