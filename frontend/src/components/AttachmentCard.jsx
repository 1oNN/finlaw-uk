import { FiAlertTriangle, FiFileText, FiPaperclip } from "react-icons/fi";

export default function AttachmentCard({ name, type, size, chunks, error }) {
  const pretty =
    typeof size === "number" && size >= 0
      ? `${Math.round(size / 1024)} KB`
      : "";
  const ext = name?.includes(".") ? name.split(".").pop()?.toUpperCase() : "";
  const hasError = Boolean(error);
  const borderClass = hasError ? "border-caution" : "border-accent";
  return (
    <div
      className={`flex items-baseline justify-between gap-3 border-l-2 ${borderClass} pl-3.5 py-1.5`}
    >
      <div className="flex min-w-0 items-baseline gap-2">
        {hasError ? (
          <FiAlertTriangle size={13} className="text-caution" aria-hidden />
        ) : (
          <FiFileText size={13} className="text-ink-mute" aria-hidden />
        )}
        <div className="min-w-0">
          <div className="truncate font-medium text-ink">
            {name || "Attachment"}
          </div>
          <div className="truncate text-[0.78rem] text-ink-mute">
            {[ext, type, pretty].filter(Boolean).join(" · ")}
          </div>
          {hasError ? (
            <div className="truncate text-[0.78rem] text-caution">{error}</div>
          ) : typeof chunks === "number" ? (
            <div className="truncate text-[0.78rem] text-ink-mute">
              ingested {chunks} {chunks === 1 ? "chunk" : "chunks"}
            </div>
          ) : null}
        </div>
      </div>
      <span className="smallcaps-fallback flex-none text-ink-mute">
        <FiPaperclip size={10} className="mr-1 inline" aria-hidden />
        {hasError ? "rejected" : "attached"}
      </span>
    </div>
  );
}
