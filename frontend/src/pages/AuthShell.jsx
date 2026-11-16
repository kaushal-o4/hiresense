// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/AuthShell.jsx
//
// FILE PURPOSE:
// The two-column layout shared by the login, register, forgot-password and reset-password pages.
//
// WHAT THIS FILE DOES:
// 1. Left: a dark product panel with a headline, a live 3D interviewer (InterviewerStage) and a
//    sample report preview.
// 2. Right: the form passed in as children.
//
// HOW THIS FILE WORKS:
// A layout component; ReportPreview is a static mock-up of a report card for decoration.
//
// IMPORTANT FUNCTIONS:
//    - AuthShell()
//        The layout wrapper.
//    - ReportPreview()
//        Decorative example report card.
//
// INPUT:
// Props: title, subtitle, children (the form).
//
// OUTPUT:
// The page layout.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/InterviewerStage.jsx, components/Logo.jsx
//    Used by: pages/ForgotPassword.jsx, pages/Login.jsx, pages/Register.jsx,
//    pages/ResetPassword.jsx
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Split-screen layout shared by the Login, Register, ForgotPassword and ResetPassword pages: a dark brand panel
 * (wordmark, tagline, what HireSense does, a live 3D interviewer with a sample feedback card) and the form column.
 */

import { Link } from "react-router-dom";
import { ArrowLeft, FileText, MessagesSquare, Mic } from "lucide-react";
import InterviewerStage from "../components/InterviewerStage";
import { PasswordInput } from "../components/SharedUiComponents";
import Logo from "../components/Logo";

const POINTS = [
  { icon: Mic, text: "Spoken mock interviews with a 3D AI interviewer" },
  { icon: FileText, text: "Resume analysis with role-specific gaps" },
  { icon: MessagesSquare, text: "English conversation practice with corrections" },
];

/** Password field for the auth forms. Uses an explicit <label htmlFor> holding only the label text, so the
 * show/hide toggle and hint never become part of the field's accessible label. */
export function PasswordField({ id, label, error, hint, className = "h-11", ...props }) {
  const msgId = `${id}-msg`;
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      <PasswordInput id={id} className={className} aria-invalid={!!error} aria-describedby={error || hint ? msgId : undefined} {...props} />
      {error ? <p id={msgId} className="mt-1.5 text-xs text-rose-600">{error}</p>
        : hint ? <p id={msgId} className="mt-1.5 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

function SampleFeedback() {
  return (
    <div className="w-[270px] rounded-xl border border-white/10 bg-night-800 p-4 shadow-[0_24px_48px_-16px_rgb(0_0_0/0.7)]" aria-hidden>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-500">Sample feedback</p>
          <p className="mt-1 text-[13px] font-medium text-snow">Backend Developer · Q3</p>
        </div>
        <p className="num font-display text-[26px] font-bold leading-none text-snow">78</p>
      </div>
      <div className="mt-3 h-1 rounded-full bg-white/10"><div className="h-1 w-[78%] origin-left rounded-full bg-brand-400 motion-safe:animate-[grow_1s_cubic-bezier(.2,.7,.2,1)_both]" /></div>
      <p className="mt-3 text-[12px] leading-relaxed text-slate-600">
        Strong diagnosis with EXPLAIN. Next time, close with the result you measured.
      </p>
    </div>
  );
}

export default function AuthShell({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen bg-white">
      <aside className="theme-dark relative hidden w-[46%] max-w-[680px] flex-col overflow-hidden bg-night-900 lg:flex">
        <div className="pointer-events-none absolute inset-0 grid-bg [mask-image:radial-gradient(ellipse_80%_60%_at_30%_10%,black,transparent)]" aria-hidden />
        <div className="relative z-10 px-10 pt-10 xl:px-14 xl:pt-12">
          <Link to="/" className="inline-block rounded-md" aria-label="HireSense home"><Logo inverted size={28} /></Link>
          <p className="mt-16 text-[12px] font-semibold uppercase tracking-[0.16em] text-brand-400">Prepare Smarter. Interview Better. Get Hired.</p>
          <h2 className="mt-3 max-w-md text-[34px] font-bold leading-[1.1] tracking-tight text-slate-950 xl:text-[40px]">
            Your Intelligence. Your Interview. Your Future.
          </h2>
          <ul className="mt-8 space-y-3">
            {POINTS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-center gap-3 text-[14.5px] text-slate-600">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/10 text-slate-800"><Icon size={15} /></span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <div className="relative min-h-[300px] flex-1">
          <InterviewerStage who="aria" caption={false} className="absolute inset-y-0 left-0 right-[24%] fade-edges" />
          <div className="absolute bottom-10 right-8 z-10 motion-safe:animate-fade-up xl:right-12"><SampleFeedback /></div>
        </div>
        <p className="relative z-10 px-10 pb-8 text-[12.5px] text-slate-500 xl:px-14">For students, recruiters, mentors and placement offices.</p>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-16 items-center justify-between px-5 sm:px-8">
          <Link to="/" className="rounded-md lg:hidden" aria-label="HireSense home"><Logo size={26} /></Link>
          <Link to="/" className="ml-auto inline-flex items-center gap-1.5 rounded-md text-[13px] font-medium text-slate-500 transition-colors hover:text-slate-900">
            <ArrowLeft size={14} /> Back to home
          </Link>
        </div>
        <main className="flex flex-1 items-center justify-center px-5 pb-12 pt-4 sm:px-8">
          <div className="w-full max-w-[400px] motion-safe:animate-fade-up">
            <h1 className="text-[28px] font-bold leading-tight tracking-tight text-slate-950">{title}</h1>
            {subtitle && <p className="mt-2 text-[15px] leading-relaxed text-slate-500">{subtitle}</p>}
            <div className="mt-8">{children}</div>
          </div>
        </main>
        <p className="pb-6 text-center text-xs text-slate-500">
          <Link to="/privacy" className="hover:text-slate-800 hover:underline">Privacy notice</Link>
        </p>
      </div>
    </div>
  );
}
