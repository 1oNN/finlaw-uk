import { FiFileText, FiPaperclip } from "react-icons/fi";

export default function AttachmentCard({ name, type, size }) {
  const pretty =
    typeof size === "number" && size >= 0
      ? `${Math.round(size / 1024)} KB`
      : "";
  const ext = name?.includes(".") ? name.split(".").pop()?.toUpperCase() : "";
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-ivory-3 bg-ivory-2/50 px-3 py-2">
      <div className="flex min-w-0 items-center gap-3">
        <div className="grid h-9 w-9 flex-none place-items-center rounded-md bg-ink text-ivory">
          <FiFileText size={16} />
        </div>
        <div className="min-w-0 leading-tight">
          <div className="truncate font-medium text-ink">
            {name || "Attachment"}
          </div>
          <div className="truncate text-xs text-slate">
            {[ext, type, pretty].filter(Boolean).join(" · ")}
          </div>
        </div>
      </div>
      <div className="flex flex-none items-center gap-1 text-xs text-slate">
        <FiPaperclip size={12} />
        <span>attached</span>
      </div>
    </div>
  );
}
