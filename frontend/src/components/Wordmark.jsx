import React from "react";

// The single FinLaw-UK brand lockup: a pilcrow in the accent colour beside the
// wordmark in editorial serif. Used in the header, auth pages, and footer so
// the identity is consistent everywhere. `PilcrowMark` is the standalone glyph
// for compact/avatar slots.

const MARK = { sm: "1.25rem", md: "1.4rem", lg: "1.8rem" };
const TEXT = { sm: "0.98rem", md: "1.05rem", lg: "1.2rem" };

export function PilcrowMark({ size = "md", className = "" }) {
  return (
    <span
      aria-hidden
      className={`font-display leading-none text-accent ${className}`}
      style={{ fontSize: MARK[size] || MARK.md }}
    >
      ¶
    </span>
  );
}

export default function Wordmark({ size = "md", className = "" }) {
  return (
    <span className={`inline-flex items-baseline gap-2 ${className}`}>
      <PilcrowMark size={size} />
      <span
        className="font-display font-semibold tracking-tightish text-ink"
        style={{ fontSize: TEXT[size] || TEXT.md }}
      >
        FinLaw-UK
      </span>
    </span>
  );
}
