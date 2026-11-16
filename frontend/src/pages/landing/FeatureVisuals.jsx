/*
 * Small, illustrative UI renderings used by the landing page feature sections. They mirror real HireSense screens
 * (resume analysis, live interview, English companion, job matching, progress) with sample content; all aria-hidden.
 */

import { AlertCircle, ArrowUpRight, CheckCircle2, FileText, Mic, Timer } from "lucide-react";

function Frame({ children, className = "" }) {
  return (
    <div aria-hidden className={`select-none rounded-xl border border-slate-200 bg-white p-4 shadow-[0_24px_48px_-24px_rgb(16_21_29/0.25)] sm:p-5 ${className}`}>
      {children}
    </div>
  );
}

function Chip({ children, tone = "gray" }) {
  const t = {
    gray: "bg-slate-100 text-slate-700 ring-slate-200",
    green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
    amber: "bg-amber-50 text-amber-800 ring-amber-200",
  }[tone];
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${t}`}>{children}</span>;
}

export function ResumeVisual() {
  return (
    <Frame>
      <div className="flex items-center gap-3 border-b border-slate-100 pb-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-600"><FileText size={17} /></span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[13px] font-semibold text-slate-900">resume_2026.pdf</p>
          <p className="text-[11px] text-slate-500">Analysed for Backend Developer</p>
        </div>
        <div className="text-right">
          <p className="num font-display text-[22px] font-bold leading-none text-slate-950">78%</p>
          <p className="text-[10px] text-slate-500">role match</p>
        </div>
      </div>
      <p className="mt-3 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-slate-400">Skills found</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {["Python", "FastAPI", "REST APIs", "SQL", "React", "Git"].map((s) => <Chip key={s} tone="green">{s}</Chip>)}
      </div>
      <p className="mt-3 text-[10.5px] font-semibold uppercase tracking-[0.1em] text-slate-400">Missing for this role</p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">{["Docker", "Caching", "CI/CD"].map((s) => <Chip key={s} tone="amber">{s}</Chip>)}</div>
      <ul className="mt-4 space-y-2 border-t border-slate-100 pt-3 text-[12px] leading-snug text-slate-600">
        <li className="flex gap-2"><CheckCircle2 size={14} className="mt-px shrink-0 text-emerald-600" /> Projects show clear ownership and outcomes.</li>
        <li className="flex gap-2"><AlertCircle size={14} className="mt-px shrink-0 text-amber-600" /> Quantify impact: add numbers to the attendance-app project.</li>
      </ul>
    </Frame>
  );
}

export function InterviewVisual() {
  return (
    <Frame className="!p-0 overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 sm:px-5">
        <p className="text-[12px] font-semibold text-slate-900">Question 3 of 6 <span className="font-normal text-slate-400">· Technical</span></p>
        <span className="num inline-flex items-center gap-1 text-[11px] text-slate-500"><Timer size={12} /> 07:42</span>
      </div>
      <div className="h-0.5 bg-slate-100"><div className="h-full w-1/2 bg-brand-500" /></div>
      <div className="px-4 py-4 sm:px-5">
        <p className="text-[11px] font-medium text-slate-500">Victor · Strict technical</p>
        <p className="mt-1 font-display text-[15px] font-semibold leading-snug text-slate-950">
          A query on your orders table got slow after launch. How would you find the cause and fix it?
        </p>
        <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-rose-500 text-white"><Mic size={12} /></span>
            <span className="text-[11.5px] font-medium text-slate-800">Listening</span>
            <span className="ml-1 flex h-3 items-end gap-[2px]">
              {[0, 1, 2, 3, 4].map((i) => <span key={i} className="h-full w-[3px] origin-bottom rounded-full bg-rose-400 motion-safe:animate-eq" style={{ animationDelay: `${i * 0.12}s` }} />)}
            </span>
          </div>
          <p className="mt-2 text-[12px] italic leading-snug text-slate-600">“First I would check the query plan with EXPLAIN to see whether it is scanning the whole table…”</p>
        </div>
      </div>
    </Frame>
  );
}

export function EnglishVisual() {
  return (
    <Frame className="space-y-2.5">
      <div className="max-w-[85%] rounded-xl rounded-tl-sm bg-slate-100 px-3 py-2 text-[12.5px] leading-snug text-slate-800">
        Tell me about a project you are proud of.
      </div>
      <div className="ml-auto max-w-[85%] rounded-xl rounded-tr-sm bg-brand-500 px-3 py-2 text-[12.5px] leading-snug text-white">
        I has build an attendance app for my college using React.
      </div>
      <div className="max-w-[92%] rounded-xl border border-slate-200 px-3 py-2 text-[12px] leading-snug text-slate-700">
        <p className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-emerald-700">Better</p>
        I <span className="rounded bg-emerald-50 px-1 font-medium text-emerald-800">built</span> an attendance app for my college using React.
      </div>
      <div className="max-w-[85%] rounded-xl rounded-tl-sm bg-slate-100 px-3 py-2 text-[12.5px] leading-snug text-slate-800">
        Nice. What was the hardest part of building it?
      </div>
      <div className="ml-auto max-w-[85%] rounded-xl rounded-tr-sm bg-brand-500 px-3 py-2 text-[12.5px] leading-snug text-white">
        Keeping it fast when the whole class marked attendance at the same time.
      </div>
      <div className="mt-1 grid grid-cols-3 divide-x divide-slate-200 rounded-lg border border-slate-200 bg-slate-50 text-center">
        {[["12 min", "Session"], ["3", "Corrections"], ["+4", "New words"]].map(([v, l]) => (
          <div key={l} className="px-2 py-2.5">
            <p className="num text-[14px] font-semibold text-slate-900">{v}</p>
            <p className="text-[10.5px] text-slate-500">{l}</p>
          </div>
        ))}
      </div>
    </Frame>
  );
}

export function JobsVisual() {
  const rows = [
    { role: "Backend Developer", meta: "Full-time · Pune", match: 86 },
    { role: "Python Developer", meta: "Internship · Remote", match: 79 },
    { role: "Data Analyst", meta: "Full-time · Bengaluru", match: 61 },
  ];
  return (
    <Frame className="!p-0 overflow-hidden">
      <ul className="divide-y divide-slate-100">
        {rows.map((r) => (
          <li key={r.role} className="flex items-center gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-semibold text-slate-900">{r.role}</p>
              <p className="text-[11px] text-slate-500">{r.meta}</p>
            </div>
            <div className="w-24">
              <div className="mb-1 flex justify-end text-[11px]"><span className="num font-semibold text-slate-900">{r.match}% match</span></div>
              <div className="h-1 rounded-full bg-slate-100"><div className={`h-1 rounded-full ${r.match >= 75 ? "bg-emerald-500" : "bg-amber-500"}`} style={{ width: `${r.match}%` }} /></div>
            </div>
            <ArrowUpRight size={14} className="shrink-0 text-slate-400" />
          </li>
        ))}
      </ul>
    </Frame>
  );
}

export function ProgressVisual() {
  // sample points (0-100) for two series
  const a = [42, 48, 46, 55, 61, 64, 72];
  const b = [50, 52, 58, 57, 63, 68, 70];
  const path = (pts) => pts.map((v, i) => `${i === 0 ? "M" : "L"}${(i / (pts.length - 1)) * 280 + 10},${110 - v}`).join(" ");
  return (
    <Frame>
      <div className="flex items-baseline justify-between">
        <p className="text-[12px] font-semibold text-slate-900">Interview score</p>
        <p className="num text-[11px] font-medium text-emerald-700">+30 in 6 weeks</p>
      </div>
      <svg viewBox="0 0 300 110" className="mt-2 h-28 w-full">
        {[20, 50, 80].map((y) => <line key={y} x1="10" x2="290" y1={y} y2={y} stroke="rgb(var(--n-200))" strokeWidth="1" />)}
        <path d={path(b)} fill="none" stroke="#14A3A0" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.8" />
        <path d={path(a)} fill="none" stroke="#315EF7" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="290" cy={110 - a[a.length - 1]} r="3.5" fill="#315EF7" />
      </svg>
      <div className="mt-1 flex gap-4 text-[11px] text-slate-500">
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#315EF7]" /> Interview</span>
        <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-[#14A3A0]" /> English</span>
      </div>
    </Frame>
  );
}
