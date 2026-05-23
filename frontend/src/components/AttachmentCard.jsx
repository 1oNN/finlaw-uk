import { FiFileText, FiPaperclip } from "react-icons/fi";

export default function AttachmentCard({ name, type, size }) {
  const pretty =
    typeof size === "number" && size >= 0
      ? `${Math.round(size / 1024)} KB`
      : "";
  const ext = name?.includes(".") ? name.split(".").pop()?.toUpperCase() : "";
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-white/15 bg-surface/70 px-3 py-2">
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-panel text-white">
          <FiFileText />
        </div>
        <div className="leading-tight">
          <div className="font-semibold text-white/95">
            {name || "Attachment"}
          </div>
          <div className="text-xs text-muted">
            {[ext, type, pretty].filter(Boolean).join(" • ")}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-1 text-xs text-white/80">
        <FiPaperclip /> <span>attached</span>
      </div>
    </div>
  );
}
