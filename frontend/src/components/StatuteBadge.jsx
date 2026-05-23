import React from "react";

export default function StatuteBadge({
  label,
  sub,
  tone = "default",
  size = "md",
  className = "",
}) {
  const tones = {
    default: "bg-ivory border-ivory-3 text-ink",
    soft: "bg-ivory-2 border-ivory-3 text-ink",
    ink: "bg-ink/5 border-ink/15 text-ink",
    gold: "bg-gold-soft border-gold/30 text-ink",
    verified: "bg-verified/10 border-verified/30 text-verified",
    caution: "bg-caution/10 border-caution/30 text-caution",
  };
  const sizes = {
    sm: "px-2 py-0.5 text-[11px]",
    md: "px-2.5 py-1 text-xs",
    lg: "px-3 py-1.5 text-sm",
  };
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 rounded-chip border font-medium",
        "font-mono tracking-tight",
        tones[tone] || tones.default,
        sizes[size] || sizes.md,
        className,
      ].join(" ")}
    >
      <span>{label}</span>
      {sub && (
        <span className="text-slate font-sans font-normal">· {sub}</span>
      )}
    </span>
  );
}
