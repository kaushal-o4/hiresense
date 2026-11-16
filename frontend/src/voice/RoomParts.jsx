// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/voice/RoomParts.jsx
//
// FILE PURPOSE:
// Small presentational pieces of the live interview room.
//
// WHAT THIS FILE DOES:
// 1. SubtitleLine: subtitles with the current word highlighted.
// 2. interviewPhase + AiStateIndicator: what the AI is doing now; Equalizer, QuestionStepper.
// 3. RoundButton, Panel, Stat, Toggle, Segmented: basic room UI pieces.
//
// HOW THIS FILE WORKS:
// Simple React components with props only.
//
// IMPORTANT FUNCTIONS:
//    - SubtitleLine()
//        Subtitles: exactly what is being said (greeting included); the word being spoken is
//        highlighted.
//    Other helper functions: RoundButton, Panel, Stat, Toggle
//
// INPUT:
// Props.
//
// OUTPUT:
// UI elements.
//
// FILES CONNECTED TO THIS FILE:
//    Used by: pages/student/LiveVoiceInterview.jsx, voice/ControlBar.jsx,
//    voice/RoomSettingsPanel.jsx, voice/RoomSidePanels.jsx
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/* Small presentational pieces of the live interview room (pages/student/LiveVoiceInterview.jsx) and the English
   avatar session. Props only - no state machine logic lives here. */
import { AlertTriangle, CheckCircle2, Loader2, Mic, PauseCircle, PenLine, Radio, Sparkles, Volume2 } from "lucide-react";
import { S } from "./interviewMachine";

/** Readable interview category ("hr" -> "HR"). */
export const categoryLabel = (c) => ({ hr: "HR", technical: "Technical", behavioral: "Behavioral", communication: "Communication", mixed: "Mixed" }[c] || c);

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
        <span className="rounded bg-brand-500/70 px-0.5 text-snow">{full.slice(startIdx, end)}</span>
        <span className="text-snow/55">{full.slice(end)}</span>
      </>
    );
  }
  return <p className={`rounded-lg bg-night-950/85 px-4 py-2 text-center leading-snug text-snow ring-1 ring-snow/10 ${SUB_SIZE[size] || SUB_SIZE.md}`} aria-live="polite">{body}</p>;
}

/** Animated level bars: shown while someone is talking. Purely decorative (aria-hidden). */
export function Equalizer({ bars = 4, className = "bg-current" }) {
  return (
    <span className="flex h-3.5 items-end gap-[2px]" aria-hidden>
      {Array.from({ length: bars }, (_, i) => (
        <span key={i} className={`h-full w-[3px] origin-bottom rounded-full animate-eq ${className}`} style={{ animationDelay: `${i * 0.13}s` }} />
      ))}
    </span>
  );
}

const TONE = {
  brand: { chip: "bg-brand-500/15 text-brand-700 ring-brand-500/30", dot: "bg-brand-500" },
  rose: { chip: "bg-rose-500/15 text-rose-700 ring-rose-500/30", dot: "bg-rose-500" },
  green: { chip: "bg-emerald-500/15 text-emerald-700 ring-emerald-500/30", dot: "bg-emerald-500" },
  amber: { chip: "bg-amber-500/15 text-amber-700 ring-amber-500/30", dot: "bg-amber-500" },
  gray: { chip: "bg-slate-500/10 text-slate-700 ring-slate-400/30", dot: "bg-slate-400" },
};

/**
 * What the AI is doing right now, as {tone, icon, title, detail, anim}. anim: "eq" (talking), "spin" (working), null.
 * Derived only from the interview state machine (status + recording) - nothing is simulated.
 */
export function interviewPhase(st, name, { talking } = {}) {
  if (st.recording) return { tone: "rose", icon: Mic, title: "Recording", detail: "Speak naturally - it stops after a short pause.", anim: "eq" };
  switch (st.status) {
    case S.INITIALIZING: return { tone: "gray", icon: Loader2, title: "Connecting", detail: "Loading the interview.", anim: "spin" };
    case S.READY: return { tone: "gray", icon: Radio, title: "Ready", detail: "Complete the checks below to begin.", anim: null };
    case S.PREPARING_SPEECH: return { tone: "brand", icon: Sparkles, title: "Preparing question", detail: `${name} is getting the next question ready.`, anim: "spin" };
    case S.SPEAKING: return { tone: "brand", icon: Volume2, title: `${name} is speaking`, detail: talking ? "Listen to the question - your microphone is off." : "Read the question on screen.", anim: talking ? "eq" : null };
    case S.LISTENING: return { tone: "green", icon: Mic, title: "Your turn", detail: "Press the microphone to answer, or type instead.", anim: null };
    case S.TRANSCRIBING: return { tone: "brand", icon: PenLine, title: "Transcribing", detail: "Turning your answer into text on this computer.", anim: "spin" };
    case S.REVIEWING: return { tone: "green", icon: PenLine, title: "Review your answer", detail: "Correct the text if needed, then submit.", anim: null };
    case S.EVALUATING: return { tone: "brand", icon: Sparkles, title: "Evaluating", detail: `${name} is considering your answer.`, anim: "spin" };
    case S.WRAP_UP: return { tone: "green", icon: CheckCircle2, title: "All questions answered", detail: "Finish to get your feedback report.", anim: null };
    case S.COMPLETING: return { tone: "brand", icon: Sparkles, title: "Preparing your report", detail: "Scoring every answer - this takes a moment.", anim: "spin" };
    case S.COMPLETED: return { tone: "green", icon: CheckCircle2, title: "Interview complete", detail: "", anim: null };
    case S.PAUSED: return { tone: "amber", icon: PauseCircle, title: "Paused", detail: "Take your time. Resume when you are ready.", anim: null };
    case S.ERROR: return { tone: "rose", icon: AlertTriangle, title: "Connection problem", detail: "Reconnect to continue where you left off.", anim: null };
    default: return { tone: "gray", icon: Radio, title: st.status, detail: "", anim: null };
  }
}

/** Compact status chip + one-line explanation. `phase` comes from interviewPhase() (or an equivalent object). */
export function AiStateIndicator({ phase, compact = false, className = "" }) {
  const t = TONE[phase.tone] || TONE.gray;
  const Icon = phase.icon;
  return (
    <div role="status" aria-live="polite" className={`flex min-w-0 items-center gap-3 ${className}`}>
      <span className={`inline-flex h-8 shrink-0 items-center gap-2 rounded-full px-3 text-xs font-semibold ring-1 ring-inset ${t.chip}`}>
        {phase.anim === "eq" ? <Equalizer className={t.dot} /> : <Icon size={14} className={phase.anim === "spin" ? "animate-spin [animation-duration:1.6s]" : ""} aria-hidden />}
        {phase.title}
      </span>
      {!compact && phase.detail && <span className="min-w-0 truncate text-[13px] text-slate-500">{phase.detail}</span>}
    </div>
  );
}

/** One dot per planned question: done (answered), current, upcoming. */
export function QuestionStepper({ total, answered, current }) {
  if (!total) return null;
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label={`Question ${Math.min(current, total)} of ${total}`}>
      {Array.from({ length: total }, (_, i) => {
        const n = i + 1;
        const state = n <= answered ? "done" : n === current ? "current" : "todo";
        return (
          <li key={n} className={`h-1.5 rounded-full transition-all duration-500 ${state === "done" ? "w-6 bg-brand-500" : state === "current" ? "w-6 bg-brand-500/40 ring-1 ring-brand-500" : "w-3 bg-slate-200"}`}
            title={`Question ${n}${state === "done" ? " - answered" : state === "current" ? " - current" : ""}`} />
        );
      })}
    </ol>
  );
}

export function RoundButton({ label, children, onClick, disabled, active, danger, primary }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={label} title={label} aria-pressed={active || undefined}
      className={`flex shrink-0 items-center justify-center rounded-full transition duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-night-900 active:scale-95 disabled:cursor-not-allowed disabled:opacity-35 ${
        primary ? "h-14 w-14" : "h-11 w-11"} ${
        danger ? "bg-rose-500 text-snow hover:bg-rose-600"
          : primary ? "bg-snow text-night-900 hover:bg-snow/90"
            : active ? "bg-brand-500 text-snow hover:bg-brand-600" : "bg-snow/[0.08] text-snow ring-1 ring-inset ring-snow/10 hover:bg-snow/15"}`}>
      {children}
    </button>
  );
}

export function Panel({ title, children, actions }) {
  return (
    <section className="card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-[13px] font-semibold text-slate-900">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value }) {
  return <div className="rounded-lg bg-slate-50 px-2 py-2 ring-1 ring-inset ring-slate-200/70"><p className="num font-display text-lg font-bold text-slate-900">{value}</p><p className="text-[11px] text-slate-500">{label}</p></div>;
}

export function Toggle({ label, checked, onChange, disabled, hint }) {
  return (
    <label className={`flex items-start gap-2.5 ${disabled ? "opacity-60" : ""}`}>
      <input type="checkbox" className="mt-0.5 h-4 w-4" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="text-slate-700">{label}{hint && <span className="block text-xs text-slate-500">{hint}</span>}</span>
    </label>
  );
}

/** Segmented option buttons used in settings panels. */
export function Segmented({ options, value, onChange, label }) {
  return (
    <div className="mt-1.5 inline-flex flex-wrap gap-0.5 rounded-lg border border-slate-200 bg-slate-100 p-0.5" role="group" aria-label={label}>
      {options.map(([v, name]) => (
        <button key={v} type="button" onClick={() => onChange(v)} aria-pressed={value === v}
          className={`rounded-md px-3 py-1 text-xs font-medium transition ${value === v ? "bg-white text-slate-950 shadow-soft ring-1 ring-slate-200" : "text-slate-500 hover:text-slate-900"}`}>
          {name}
        </button>
      ))}
    </div>
  );
}
