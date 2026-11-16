/*
 * HireSense brand: a square "H" monogram with a blue signal block, plus the spaced H I R E S E N S E wordmark.
 * Works on light and dark surfaces (`inverted` forces white type for dark panels). Same mark as public/favicon.svg.
 */

export function LogoMark({ size = 28, inverted = false }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="7" fill={inverted ? "#ffffff" : "rgb(var(--n-950))"} />
      <path d="M10 8.5v15M22 8.5v15M10 16h12" stroke={inverted ? "#10151D" : "rgb(var(--surface))"} strokeWidth="2.6" strokeLinecap="round" />
      <rect x="20.5" y="5" width="5" height="5" rx="1.2" fill="#315EF7" />
    </svg>
  );
}

export default function Logo({ size = 28, inverted = false, className = "", wordmark = true }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={size} inverted={inverted} />
      {wordmark && (
        <span className={`font-display text-[14px] font-extrabold tracking-[0.28em] ${inverted ? "text-snow" : "text-slate-950"}`}>
          HIRESENSE
        </span>
      )}
      <span className="sr-only">HireSense</span>
    </span>
  );
}
