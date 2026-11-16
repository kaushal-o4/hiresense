/*
 * Hero visual of the landing page: an HTML/CSS rendering of the real HireSense student workspace (sidebar,
 * placement-readiness score, interview report). Purely illustrative - aria-hidden and labelled "Sample report".
 * Rendered in the light theme even inside the dark hero, so it reads as the actual product.
 */

import { BarChart3, Briefcase, CheckCircle2, FileText, LayoutDashboard, MessagesSquare, Mic, Search } from "lucide-react";
import { LogoMark } from "../../components/Logo";

const NAV = [
  { icon: LayoutDashboard, label: "Overview" },
  { icon: Mic, label: "Mock interviews", active: true },
  { icon: MessagesSquare, label: "Communication" },
  { icon: FileText, label: "Resume analysis" },
  { icon: Briefcase, label: "Job opportunities" },
  { icon: BarChart3, label: "My progress" },
];

const SCORES = [
  { label: "Technical depth", value: 82, tone: "bg-emerald-500" },
  { label: "Communication", value: 74, tone: "bg-brand-500" },
  { label: "Problem solving", value: 68, tone: "bg-brand-500" },
  { label: "Structure (STAR)", value: 57, tone: "bg-amber-500" },
];

function Ring({ value }) {
  return (
    <div className="relative h-[92px] w-[92px] shrink-0">
      <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
        <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgb(var(--n-200))" strokeWidth="2.6" />
        <circle cx="18" cy="18" r="15.9" fill="none" stroke="rgb(var(--brand-500))" strokeWidth="2.6" strokeLinecap="round"
          strokeDasharray={`${value} 100`} className="origin-center" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="num font-display text-[24px] font-bold leading-none text-slate-950">{value}</span>
        <span className="mt-0.5 text-[9.5px] text-slate-500">of 100</span>
      </div>
    </div>
  );
}

export default function ProductPreview() {
  return (
    <div aria-hidden className="theme-light select-none overflow-hidden rounded-xl border border-white/10 bg-slate-50 text-left shadow-[0_40px_80px_-30px_rgb(0_0_0/0.75)] ring-1 ring-black/40">
      {/* app top bar */}
      <div className="flex h-10 items-center gap-3 border-b border-slate-200 bg-white px-3.5">
        <LogoMark size={18} />
        <span className="font-display text-[10px] font-extrabold tracking-[0.24em] text-slate-950">HIRESENSE</span>
        <span className="ml-3 hidden h-6 flex-1 items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 text-[10.5px] text-slate-400 sm:flex md:max-w-[220px]">
          <Search size={11} /> Search pages…
        </span>
        <span className="ml-auto flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-[9px] font-semibold text-white">AS</span>
      </div>
      <div className="flex">
        {/* sidebar */}
        <div className="hidden w-[150px] shrink-0 border-r border-slate-200 bg-white px-2 py-3 sm:block">
          <p className="px-2 pb-1.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">Workspace</p>
          {NAV.map(({ icon: Icon, label, active }) => (
            <div key={label} className={`mb-0.5 flex items-center gap-2 rounded-md px-2 py-1.5 text-[10.5px] ${active ? "bg-slate-100 font-semibold text-slate-950" : "text-slate-500"}`}>
              <Icon size={12} className={active ? "text-brand-600" : ""} /> {label}
            </div>
          ))}
        </div>
        {/* main */}
        <div className="min-w-0 flex-1 p-3.5 sm:p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-slate-400">Sample report</p>
              <p className="truncate font-display text-[14px] font-bold text-slate-950">Backend Developer · Technical round</p>
              <p className="text-[10.5px] text-slate-500">6 questions · 18 min · interviewer Aria</p>
            </div>
            <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-emerald-50 px-1.5 py-0.5 text-[9.5px] font-medium text-emerald-700 ring-1 ring-inset ring-emerald-200">
              <span className="h-1 w-1 rounded-full bg-emerald-500" /> Completed
            </span>
          </div>

          <div className="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_170px]">
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex items-center gap-4">
                <Ring value={72} />
                <div className="min-w-0 flex-1 space-y-2">
                  {SCORES.map((s, i) => (
                    <div key={s.label}>
                      <div className="mb-0.5 flex justify-between text-[9.5px]"><span className="text-slate-600">{s.label}</span><span className="num font-semibold text-slate-900">{s.value}</span></div>
                      <div className="h-1 rounded-full bg-slate-100">
                        <div className={`h-1 origin-left rounded-full ${s.tone} motion-safe:animate-[grow_1s_cubic-bezier(.2,.7,.2,1)_both]`} style={{ width: `${s.value}%`, animationDelay: `${400 + i * 110}ms` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="hidden space-y-2 md:block">
              <div className="rounded-lg border border-slate-200 bg-white p-2.5">
                <p className="text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-400">Readiness</p>
                <p className="num font-display text-[18px] font-bold text-slate-950">64<span className="text-[10px] font-medium text-slate-400"> / 100</span></p>
                <p className="text-[9.5px] text-amber-700">Almost ready</p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white p-2.5">
                <p className="text-[9px] font-semibold uppercase tracking-[0.1em] text-slate-400">Resume match</p>
                <p className="num font-display text-[18px] font-bold text-slate-950">78%</p>
                <p className="text-[9.5px] text-slate-500">Backend Developer</p>
              </div>
            </div>
          </div>

          <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3">
            <p className="text-[10px] font-semibold text-slate-900">Next steps</p>
            <ul className="mt-1.5 space-y-1">
              {["Structure behavioural answers as situation, action, result.", "Mention indexing and query plans when discussing SQL performance."].map((t) => (
                <li key={t} className="flex gap-1.5 text-[10px] leading-snug text-slate-600"><CheckCircle2 size={11} className="mt-px shrink-0 text-brand-500" /> {t}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
