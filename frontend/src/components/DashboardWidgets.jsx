/*
 * Small building blocks shared by the four portal dashboards: a score ring, a labelled meter, a "view all" link,
 * a row that links somewhere, and a person avatar. Colours come from the theme tokens (index.css), so they work in
 * both light and dark themes; status colour is used only when the value itself carries meaning.
 */

import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight } from "lucide-react";

const TONE_VAR = { green: "--emerald-500", amber: "--amber-500", red: "--rose-500", brand: "--brand-500", gray: "--n-400" };

/** Tone for a 0-100 score: >= 75 green, >= 50 amber, otherwise red. */
export const scoreTone = (v) => (v == null ? "gray" : v >= 75 ? "green" : v >= 50 ? "amber" : "red");

/** Circular progress ring with the value in the middle. */
export function ScoreRing({ value, max = 100, size = 112, stroke = 8, tone = "brand", label = `of ${max}` }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgb(var(--n-100))" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} strokeLinecap="round"
          stroke={`rgb(var(${TONE_VAR[tone] || TONE_VAR.brand}))`} strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
          className="transition-[stroke-dashoffset] duration-1000 ease-out" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="num font-display text-[26px] font-bold leading-none tracking-tight text-slate-950">{value == null ? "—" : Math.round(value)}</span>
        <span className="mt-1 text-[11px] text-slate-500">{label}</span>
      </div>
    </div>
  );
}

/** Labelled horizontal meter. `tone` "auto" colours by score; otherwise a fixed tone. */
export function Meter({ label, value, max = 100, tone = "brand", suffix = "", hint }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  const t = tone === "auto" ? scoreTone(pct) : tone;
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3 text-[13px]">
        <span className="truncate text-slate-600">{label}</span>
        <span className="num shrink-0 font-semibold text-slate-900">{value == null ? <span className="font-normal text-slate-400">Not started</span> : `${Math.round(value)}${suffix}`}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100" role="meter" aria-label={label} aria-valuenow={value ?? 0} aria-valuemin={0} aria-valuemax={max}>
        <div className="h-full rounded-full transition-[width] duration-700 ease-out" style={{ width: `${pct}%`, background: `rgb(var(${TONE_VAR[t] || TONE_VAR.brand}))` }} />
      </div>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

/** "View all →" style link for card headers. */
export function CardLink({ to, children = "View all" }) {
  return (
    <Link to={to} className="group inline-flex items-center gap-1 text-[13px] font-medium text-slate-500 transition-colors hover:text-brand-600">
      {children} <ArrowRight size={13} className="transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

/** A full-width row inside a card list that navigates somewhere. */
export function LinkRow({ to, icon: Icon, title, meta, right, tone = "gray" }) {
  const tile = { gray: "bg-slate-100 text-slate-600", brand: "bg-brand-50 text-brand-600", green: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600", red: "bg-rose-50 text-rose-600", sky: "bg-sky-50 text-sky-600" }[tone];
  const body = (
    <>
      {Icon && <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tile}`}><Icon size={15} aria-hidden /></span>}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-slate-900">{title}</span>
        {meta && <span className="block truncate text-xs text-slate-500">{meta}</span>}
      </span>
      {right}
      {to && <ChevronRight size={15} className="shrink-0 text-slate-300 transition-colors group-hover:text-slate-500" aria-hidden />}
    </>
  );
  return to
    ? <Link to={to} className="group -mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-slate-50">{body}</Link>
    : <div className="flex items-center gap-3 py-2.5">{body}</div>;
}

export const initials = (name = "") => name.split(" ").filter(Boolean).map((p) => p[0]).slice(0, 2).join("").toUpperCase();

/** Neutral initials avatar for people in lists. */
export function PersonAvatar({ name, size = 32 }) {
  return (
    <span className="flex shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-600 ring-1 ring-inset ring-slate-200"
      style={{ width: size, height: size }} aria-hidden>{initials(name)}</span>
  );
}
