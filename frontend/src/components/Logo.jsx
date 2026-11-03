/* HireSense wordmark: a gradient "H" monogram with a single accent dot, plus the name. */

import { useId } from "react";

export function LogoMark({ size = 28 }) {
  // unique per instance: a gradient defined inside a hidden (display:none) copy cannot be referenced by another
  const id = `hs-logo-${useId().replace(/:/g, "")}`;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#818cf8" /><stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${id})`} />
      <rect x="0.5" y="0.5" width="31" height="31" rx="8.5" fill="none" stroke="rgba(255,255,255,0.25)" />
      <path d="M10.5 9v14M21.5 9v14M10.5 16h11" stroke="#ffffff" strokeWidth="2.8" strokeLinecap="round" />
      <circle cx="25" cy="7" r="2.6" fill="#5eead4" />
    </svg>
  );
}

export default function Logo({ size = 28, inverted = false, className = "" }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} />
      <span className={`text-[17px] font-semibold tracking-tight ${inverted ? "text-snow" : "text-slate-950"}`}>HireSense</span>
    </span>
  );
}
