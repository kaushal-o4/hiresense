/* Small presentational pieces of the live interview room (pages/student/VoiceInterview.jsx). */

const SUB_SIZE = { sm: "text-sm", md: "text-base", lg: "text-lg sm:text-xl" };

/** Subtitles: exactly what is being said (greeting included); the word being spoken is highlighted. */
export function SubtitleLine({ text: full, pos, size, speaking }) {
  let body = <span>{full}</span>;
  if (speaking && pos != null) {
    const at = Math.round(pos * full.length);
    const startIdx = full.lastIndexOf(" ", Math.max(0, at - 1)) + 1;
    const endIdx = full.indexOf(" ", at);
    const end = endIdx === -1 ? full.length : endIdx;
    body = (
      <>
        <span className="text-snow">{full.slice(0, startIdx)}</span>
        <span className="rounded bg-snow/20 px-0.5 text-snow">{full.slice(startIdx, end)}</span>
        <span className="text-slate-600">{full.slice(end)}</span>
      </>
    );
  }
  return <p className={`rounded-lg bg-black/75 px-4 py-2 text-center leading-snug text-snow backdrop-blur-sm ${SUB_SIZE[size] || SUB_SIZE.md}`} aria-live="polite">{body}</p>;
}

export function RoundButton({ label, children, onClick, disabled, active, danger }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={label} title={label} aria-pressed={active || undefined}
      className={`flex h-11 w-11 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-40 ${
        danger ? "bg-rose-600 text-snow shadow-[0_0_20px_rgb(244_63_94/0.65)] hover:bg-rose-500" : active ? "bg-gradient-to-br from-brand-500 to-violet-500 text-snow shadow-glow" : "bg-snow/[0.07] text-snow ring-1 ring-inset ring-snow/10 hover:bg-snow/15"}`}>
      {children}
    </button>
  );
}

export function Panel({ title, children }) {
  return (
    <section className="card p-4">
      <h2 className="mb-3 text-[13px] font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

export function Stat({ label, value }) {
  return <div className="rounded-lg bg-slate-50 py-2"><p className="num text-lg font-semibold text-slate-900">{value}</p><p className="text-[11px] text-slate-500">{label}</p></div>;
}

export function Toggle({ label, checked, onChange, disabled, hint }) {
  return (
    <label className={`flex items-start gap-2 ${disabled ? "opacity-60" : ""}`}>
      <input type="checkbox" className="mt-0.5" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}{hint && <span className="block text-xs text-slate-400">{hint}</span>}</span>
    </label>
  );
}
