import { useCallback, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { motion } from "framer-motion";
import { Upload, X, FolderOpen } from "lucide-react";
import toast from "react-hot-toast";
import { corpusApi } from "../api/client";
import { useStore } from "../store/useStore";

const MAX_FILES = 20;
const MAX_MB = 50;

interface Props {
  corpusId: string;
  onUploaded: () => void;
}

export default function PDFUploader({ corpusId, onUploaded }: Props) {
  // Upload state lives in the global store so the queue and progress bar
  // survive switching to another tab while indexing runs.
  const {
    uploading, setUploading,
    uploadProgress: progress, setUploadProgress: setProgress,
    uploadQueue: queued, setUploadQueue: setQueued,
  } = useStore();
  const folderInputRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback((accepted: File[]) => {
    const valid = accepted.filter(
      (f) => f.name.toLowerCase().endsWith(".pdf") && f.size <= MAX_MB * 1024 * 1024,
    );
    if (valid.length < accepted.length)
      toast.error(`Some files skipped (PDF only, max ${MAX_MB} MB each)`);
    setQueued((prev) => [...prev, ...valid].slice(0, MAX_FILES));
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: { "application/pdf": [".pdf"] },
    maxFiles: MAX_FILES, disabled: uploading,
  });

  function onFolderPicked(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (pdfs.length === 0) {
      toast.error("No PDFs found in that folder");
    } else {
      if (pdfs.length < files.length)
        toast.error(`${files.length - pdfs.length} non-PDF file${files.length - pdfs.length > 1 ? "s" : ""} skipped`);
      onDrop(pdfs);
    }
    e.target.value = "";
  }

  async function uploadAll() {
    if (!queued.length) return;
    const count = queued.length;
    setUploading(true);
    setProgress(0);
    try {
      await corpusApi.upload(corpusId, queued, setProgress);
      toast.success(`${count} PDF${count > 1 ? "s" : ""} indexed and ready!`);
      setQueued([]);
      onUploaded();
    } catch (err: any) {
      toast.error(
        err.response?.data?.detail ??
          (err.response ? "Upload failed" : "Can't reach the server — is it still running?"),
      );
    } finally {
      setUploading(false);
      setProgress(0);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors duration-150 ${
          isDragActive ? "border-brand-400 bg-brand-50/50" : "border-zinc-300 hover:border-brand-400 hover:bg-brand-50/50"
        } ${uploading ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <input {...getInputProps()} />
        <Upload className="w-6 h-6 mx-auto mb-1.5 text-zinc-400" />
        <p className="text-xs text-zinc-500">
          {isDragActive ? "Drop PDFs here…" : "Drop PDFs or click"}
        </p>
        <p className="text-xs text-zinc-400 mt-1">max {MAX_FILES} PDFs · {MAX_MB} MB each</p>
      </div>

      {/* Folder upload */}
      <input
        ref={folderInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={onFolderPicked}
        {...({ webkitdirectory: "", directory: "" } as any)}
      />
      <button
        type="button"
        onClick={() => folderInputRef.current?.click()}
        disabled={uploading}
        className="btn-ghost text-xs py-2 flex items-center justify-center gap-1.5 w-full
                   transition duration-150 active:scale-[0.98]
                   focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
      >
        <FolderOpen className="w-3.5 h-3.5" />
        Upload folder
      </button>

      {queued.length > 0 && (
        <div className="space-y-1.5">
          {queued.map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-zinc-600 bg-zinc-50 border border-zinc-200/60 rounded-lg px-3 py-2">
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-zinc-400 font-mono tabular-nums">{(f.size / 1024 / 1024).toFixed(1)}MB</span>
              <button onClick={() => setQueued((q) => q.filter((_, j) => j !== i))}
                className="text-zinc-400 hover:text-red-600 transition-colors">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}

          {uploading && (
            <div className="w-full bg-zinc-100 rounded-full h-1.5">
              <motion.div className="bg-brand-600 h-1.5 rounded-full"
                animate={{ width: `${progress}%` }} transition={{ duration: 0.3 }} />
            </div>
          )}

          <button onClick={uploadAll} disabled={uploading}
            className="btn-primary w-full text-xs py-2">
            {uploading
              ? progress < 100
                ? `Uploading… ${progress}%`
                : "Indexing on server… (takes a few minutes for many PDFs)"
              : `Index ${queued.length} PDF${queued.length > 1 ? "s" : ""}`}
          </button>
        </div>
      )}
    </div>
  );
}
