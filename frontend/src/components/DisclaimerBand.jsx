import React from "react";
import { FiInfo } from "react-icons/fi";

export default function DisclaimerBand({ variant = "page", className = "" }) {
  if (variant === "thin") {
    return (
      <div
        className={`inline-flex items-center gap-1.5 text-[11px] text-slate ${className}`}
      >
        <FiInfo size={11} aria-hidden />
        <span>Research tool — not legal advice.</span>
      </div>
    );
  }

  return (
    <div
      className={`border-y border-ivory-3 bg-ivory-2 ${className}`}
      role="note"
    >
      <div className="mx-auto flex max-w-7xl items-start gap-3 px-4 py-3 text-sm text-ink/85 sm:px-6">
        <FiInfo
          className="mt-0.5 flex-none text-gold-2"
          size={16}
          aria-hidden
        />
        <p>
          <span className="font-medium text-ink">FinLaw is a research tool.</span>{" "}
          Information provided is for educational purposes only and does not
          constitute legal advice.
        </p>
      </div>
    </div>
  );
}
