import React from "react";

function Mark({ size = 28, monochrome = false, className = "" }) {
  const ink = monochrome ? "currentColor" : "#0F1E3D";
  const surface = monochrome ? "transparent" : "#F7F3EA";
  const gold = monochrome ? "currentColor" : "#B8893A";

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 100 100"
      width={size}
      height={size}
      role="img"
      aria-label="FinLaw"
      className={className}
    >
      <rect width="100" height="100" rx="18" fill={ink} />
      <g fill={surface}>
        <rect x="22" y="20" width="56" height="10" rx="1" />
        <rect x="32" y="20" width="14" height="60" rx="1" />
        <rect x="32" y="46" width="32" height="10" rx="1" />
        <rect x="18" y="78" width="64" height="6" rx="1" />
      </g>
      <circle cx="72" cy="51" r="4.5" fill={gold} />
    </svg>
  );
}

function Wordmark({ size = "md", withMark = true, className = "" }) {
  const text =
    size === "sm"
      ? "text-[1.05rem]"
      : size === "lg"
      ? "text-2xl md:text-3xl"
      : "text-xl";
  const markSize = size === "sm" ? 22 : size === "lg" ? 36 : 28;

  return (
    <span
      className={`inline-flex items-center gap-2.5 leading-none ${className}`}
    >
      {withMark && <Mark size={markSize} />}
      <span
        className={`font-display font-semibold tracking-tightish text-ink ${text}`}
      >
        Fin
        <span className="relative">
          Law
          <span
            aria-hidden
            className="pointer-events-none absolute -bottom-0.5 left-0 right-0 h-[2px] bg-gold"
          />
        </span>
      </span>
    </span>
  );
}

export default function Logo({
  variant = "wordmark",
  size = "md",
  withMark = true,
  monochrome = false,
  className = "",
}) {
  if (variant === "mark") {
    const px = size === "sm" ? 22 : size === "lg" ? 56 : 32;
    return <Mark size={px} monochrome={monochrome} className={className} />;
  }
  return (
    <Wordmark size={size} withMark={withMark} className={className} />
  );
}
