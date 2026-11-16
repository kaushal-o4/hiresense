// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/SharedUiComponents.jsx
//
// FILE PURPOSE:
// The shared user-interface kit: buttons, cards, tables, pop-ups, toasts, a data-loading hook and date
// helpers used by every page.
//
// MAIN RESPONSIBILITY:
// Reusable UI building blocks so all pages look and behave the same.
//
// WHAT THIS FILE DOES:
// 1. useApi(): loads data from the API and tracks loading / error / data state.
// 2. ToastProvider + useToast(): small pop-up success/error messages.
// 3. Visual components: Button, Card, StatCard, Pill, StatusPill, Spinner, ErrorBox, Notice,
//    EmptyState, PageHeader.
// 4. Form and layout helpers: Field, Modal, ConfirmButton, Table, Pagination, Tabs, ScoreBar,
//    TagInput.
// 5. Date helpers: fmtDate, fmtDateTime, toLocalInput, fromLocalInput.
//
// HOW THIS FILE WORKS:
// Each component is a small React function that takes props and returns Tailwind-styled JSX. useApi
// keeps the loader function in a ref and re-runs it when its dependency list changes; reload() can be
// called after an update.
//
// IMPORTANT FUNCTIONS:
//    - useApi()
//        Hook: runs an async loader (usually get('/...')) and returns {data, setData, error,
//        loading, reload}.
//    - ToastProvider()
//        Context provider that shows toast messages in the bottom-right corner (auto-hide after
//        4-7 s).
//    - useToast()
//        Hook returning the function used to show a toast.
//    - Button()
//        Styled button with variants (primary, secondary, danger, ghost, success) and a loading
//        spinner.
//    - Card()
//        Panel with an optional title and action buttons.
//    - Table()
//        Data table with an empty message; rows can be clickable.
//    - Modal()
//        Pop-up dialog with a title, body and footer buttons.
//    - ConfirmButton()
//        Button that asks 'Are you sure?' in a modal before running onConfirm.
//    - ScoreBar()
//        Horizontal bar that shows a score out of 100 (or another maximum).
//    - TagInput()
//        Input where the user types a skill and presses Enter to add it as a tag.
//    Other helper functions: StatCard, Pill, StatusPill, Spinner, ErrorBox, Notice, EmptyState,
//    PageHeader, Field, Pagination, Tabs, fmtDate, fmtDateTime, toLocalInput, fromLocalInput
//
// INPUT:
// Props from pages (titles, rows, values, callbacks) and loader functions for useApi.
//
// OUTPUT:
// Rendered UI elements; useApi returns loaded data.
//
// FILES CONNECTED TO THIS FILE:
//    Used by: App.jsx, components/AppShellLayout.jsx, components/ConversationMemory.jsx,
//    components/DashboardCharts.jsx, components/EnglishDailyPlan.jsx,
//    components/EnglishMistakeProfile.jsx, components/EnglishProgress.jsx,
//    components/HostedAiConsentGate.jsx, components/PlacementReadinessCard.jsx, main.jsx,
//    monitoring/InterviewMonitorBar.jsx, pages/AccountSettings.jsx, pages/ForgotPassword.jsx,
//    pages/Login.jsx, pages/NotFound.jsx, pages/Notifications.jsx, pages/ProfileEditor.jsx,
//    pages/Register.jsx, pages/ResetPassword.jsx, pages/admin/AdminDashboard.jsx,
//    pages/admin/AdminJobPostings.jsx, pages/admin/AdminMonitoring.jsx,
//    pages/admin/AdminRewardRules.jsx, pages/admin/AuditLogs.jsx, pages/admin/InterviewConfig.jsx,
//    pages/admin/MentorAssignments.jsx, pages/admin/PlacementReports.jsx,
//    pages/admin/PlatformSettings.jsx, pages/admin/SecuritySettings.jsx,
//    pages/admin/UserManagement.jsx, pages/mentor/MentorDashboard.jsx,
//    pages/mentor/MentorSessions.jsx, pages/mentor/MentorStudentDetail.jsx,
//    pages/mentor/MentorStudentList.jsx, pages/recruiter/CandidateDetail.jsx,
//    pages/recruiter/CandidateReport.jsx, pages/recruiter/CandidateSearch.jsx,
//    pages/recruiter/CompareCandidates.jsx, pages/recruiter/IntegrityOverview.jsx,
//    pages/recruiter/RecruiterDashboard.jsx, pages/recruiter/RecruiterJobApplicants.jsx,
//    pages/recruiter/RecruiterJobPostings.jsx, pages/shared/AssessmentManager.jsx,
//    pages/shared/IntegrityReview.jsx, pages/student/EnglishAvatarSession.jsx,
//    pages/student/EnglishPracticeHome.jsx, pages/student/EnglishSession.jsx,
//    pages/student/InterviewSession.jsx, pages/student/InterviewSetup.jsx,
//    pages/student/InterviewerFeedback.jsx, pages/student/InterviewerPicker.jsx,
//    pages/student/JobApplications.jsx, pages/student/LiveVoiceInterview.jsx,
//    pages/student/MockInterviewHome.jsx, pages/student/PerformanceReport.jsx,
//    pages/student/PlacementDrives.jsx, pages/student/PracticeHistory.jsx,
//    pages/student/ProgressOverview.jsx, pages/student/ResumeUploadAndAnalysis.jsx,
//    pages/student/StudentAssessments.jsx, pages/student/StudentDashboard.jsx,
//    pages/student/StudentJobOpenings.jsx, pages/student/StudentMentoring.jsx,
//    pages/student/StudentRewards.jsx, pages/student/VocabularyTrainer.jsx, voice/AnswerDock.jsx,
//    voice/ControlBar.jsx
//
// EXECUTION FLOW:
//    Page imports a component or hook
//       |
//       v
//    Passes props / a loader
//       |
//       v
//    Component renders consistent UI
//       |
//       v
//    User actions call the page's callbacks
//
// IMPORTANT DEPENDENCIES:
//    lucide-react, react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Shared UI kit used by every page: the useApi data-loading hook, toasts, and the Button, Card, Table,
 * Modal, Pagination, Tabs, ErrorBox, EmptyState and form primitives, plus date-formatting helpers.
 * Change styles here (not per page) so the whole app stays consistent.
 *
 * Visual rules: all colours come from the CSS variables in index.css (light + dark themes). Solid brand-blue primary
 * buttons, flat 1px-bordered cards, no gradients or glows; colour is used only where it carries meaning (status, scores).
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Eye, EyeOff, Inbox, Info, Loader2, X } from "lucide-react";

// ------------------------------------------------------------------ data loading hook

export function useApi(loader, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await loaderRef.current());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, setData, error, loading, reload };
}

// ------------------------------------------------------------------ toasts

const ToastContext = createContext(() => {});

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback((message, type = "success") => {
    const id = Math.random();
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => dismiss(id), type === "error" ? 7000 : 4000);
  }, [dismiss]);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} role="status"
            className="pointer-events-auto flex animate-scale-in items-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-pop">
            {t.type === "error"
              ? <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-rose-50 text-rose-600"><AlertTriangle size={13} /></span>
              : t.type === "info"
                ? <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600"><Info size={13} /></span>
                : <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600"><CheckCircle2 size={13} /></span>}
            <span className="flex-1 whitespace-pre-line">{t.message}</span>
            <button className="-mr-1 rounded p-0.5 text-slate-400 hover:text-slate-700" onClick={() => dismiss(t.id)} aria-label="Dismiss"><X size={15} /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

// ------------------------------------------------------------------ primitives

const BTN = {
  primary: "bg-brand-500 text-snow shadow-[0_1px_2px_rgb(16_21_29/0.12),inset_0_1px_0_rgb(255_255_255/0.12)] hover:bg-brand-600",
  secondary: "border border-slate-200 bg-white text-slate-800 shadow-soft hover:border-slate-300 hover:bg-slate-50 hover:text-slate-950",
  danger: "bg-rose-500 text-snow shadow-[0_1px_2px_rgb(16_21_29/0.12)] hover:bg-rose-600",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  success: "bg-emerald-500 text-snow shadow-[0_1px_2px_rgb(16_21_29/0.12)] hover:bg-emerald-600",
  accent: "bg-brand-500 text-snow hover:bg-brand-600",
  dark: "bg-slate-950 text-white hover:bg-slate-800",
};

const SIZE = { sm: "h-8 rounded-lg px-3 text-[13px]", md: "h-10 rounded-lg px-4 text-sm", lg: "h-11 rounded-lg px-5 text-[15px]" };
const BASE = "inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-medium transition duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50";

/** Classes for a <Link> that should look like a Button (avoids nesting <button> inside <a>). */
export const buttonClass = (variant = "primary", size = "md") => `${BASE} ${BTN[variant] || BTN.primary} ${SIZE[size] || SIZE.md}`;

export function Button({ variant = "primary", size = "md", loading, children, className = "", ...props }) {
  return (
    <button
      className={`${buttonClass(variant, size)} active:translate-y-px disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <Loader2 size={15} className="animate-spin" />}
      {children}
    </button>
  );
}

export function Card({ title, actions, children, className = "", bodyClass = "p-5" }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="flex min-h-[52px] flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-5 py-3">
          {title && <h2 className="flex items-center gap-2 text-[15px] font-semibold text-slate-900">{title}</h2>}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

// Each tone tints only the small icon tile, so a row of stats reads as distinct but calm.
const STAT_TONES = {
  brand: "text-brand-600 bg-brand-50", violet: "text-brand-600 bg-brand-50", green: "text-emerald-600 bg-emerald-50",
  teal: "text-teal-600 bg-teal-50", amber: "text-amber-600 bg-amber-50", red: "text-rose-600 bg-rose-50",
  pink: "text-rose-600 bg-rose-50", sky: "text-sky-600 bg-sky-50", gray: "text-slate-600 bg-slate-100",
};

export function StatCard({ label, value, icon: Icon, hint, tone = "brand" }) {
  return (
    <div className="card card-hover flex flex-col p-4 sm:p-5">
      <div className="flex items-start justify-between gap-2">
        <p className="truncate text-[13px] font-medium text-slate-500">{label}</p>
        {Icon && <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${STAT_TONES[tone] || STAT_TONES.brand}`}><Icon size={16} aria-hidden /></span>}
      </div>
      <p className="num mt-1 truncate font-display text-[28px] font-bold leading-tight tracking-tight text-slate-950">{value ?? "—"}</p>
      {hint && <p className="mt-0.5 truncate text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

const PILL = {
  gray: "bg-slate-100 text-slate-700 ring-slate-200", green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  red: "bg-rose-50 text-rose-700 ring-rose-200", amber: "bg-amber-50 text-amber-800 ring-amber-200",
  blue: "bg-sky-50 text-sky-700 ring-sky-200", brand: "bg-brand-50 text-brand-700 ring-brand-200",
  violet: "bg-slate-100 text-slate-700 ring-slate-200", pink: "bg-rose-50 text-rose-700 ring-rose-200",
  teal: "bg-teal-50 text-teal-700 ring-teal-200",
};
const DOT = {
  gray: "bg-slate-400", green: "bg-emerald-500", red: "bg-rose-500", amber: "bg-amber-500", blue: "bg-sky-500",
  brand: "bg-brand-500", violet: "bg-slate-500", pink: "bg-rose-400", teal: "bg-teal-500",
};

export function Pill({ tone = "gray", children, className = "", dot = false }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${PILL[tone] || PILL.gray} ${className}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${DOT[tone] || DOT.gray}`} aria-hidden />}
      {children}
    </span>
  );
}

const STATUS_TONES = {
  active: "green", pending: "amber", suspended: "red", deactivated: "gray", published: "green", draft: "gray",
  closed: "red", applied: "blue", shortlisted: "brand", interview_scheduled: "amber", selected: "green",
  rejected: "red", withdrawn: "gray", in_progress: "amber", completed: "green", abandoned: "gray",
  scheduled: "blue", cancelled: "gray", improving: "green", stable: "blue", struggling: "red", no_data: "gray",
  unavailable: "amber", failed: "red", partial: "amber",
};

export function StatusPill({ status }) {
  if (!status) return null;
  const s = String(status).replace(/_/g, " ");
  return <Pill dot tone={STATUS_TONES[status] || "gray"}>{s.charAt(0).toUpperCase() + s.slice(1)}</Pill>;
}

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-2.5 py-16 text-slate-400" role="status">
      <Loader2 className="animate-spin text-brand-500" size={18} /> <span className="text-sm text-slate-500">{label}</span>
    </div>
  );
}

/** Shimmering placeholder block. */
export function Skeleton({ className = "h-4 w-full" }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

/** Page-level loading placeholder shaped like a dashboard (header, stat row, two panels). */
export function PageSkeleton({ stats = 4 }) {
  return (
    <div className="space-y-6" role="status" aria-label="Loading">
      <div className="space-y-2"><Skeleton className="h-8 w-64" /><Skeleton className="h-4 w-96 max-w-full" /></div>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {Array.from({ length: stats }, (_, i) => <div key={i} className="card space-y-3 p-5"><Skeleton className="h-3 w-24" /><Skeleton className="h-7 w-16" /><Skeleton className="h-3 w-32" /></div>)}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card space-y-3 p-5 lg:col-span-2"><Skeleton className="h-4 w-40" /><Skeleton className="h-48 w-full" /></div>
        <div className="card space-y-3 p-5"><Skeleton className="h-4 w-32" />{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-9 w-full" />)}</div>
      </div>
    </div>
  );
}

export function ErrorBox({ message, onRetry }) {
  if (!message) return null;
  return (
    <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
      <AlertTriangle size={17} className="mt-0.5 shrink-0" />
      <div className="flex-1 whitespace-pre-line">{message}</div>
      {onRetry && <Button variant="secondary" size="sm" onClick={onRetry}>Retry</Button>}
    </div>
  );
}

export function Notice({ children, tone = "amber" }) {
  const t = tone === "amber" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-sky-200 bg-sky-50 text-sky-900";
  const Icon = tone === "amber" ? AlertTriangle : Info;
  return (
    <div className={`flex items-start gap-2.5 rounded-lg border px-4 py-3 text-sm ${t}`}>
      <Icon size={16} className="mt-0.5 shrink-0 opacity-80" aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

export function EmptyState({ title, message, action, icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 px-4 py-14 text-center">
      <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500 shadow-soft"><Icon size={19} strokeWidth={1.8} /></div>
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      {message && <p className="max-w-sm text-sm text-slate-500">{message}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        <h1 className="text-[26px] font-bold leading-tight tracking-tight text-slate-950 sm:text-[30px]">{title}</h1>
        {subtitle && <div className="mt-1.5 max-w-3xl text-[15px] leading-relaxed text-slate-500">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

/** Section title inside a page (between PageHeader and cards). */
export function SectionHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
      <div><h2 className="text-base font-semibold text-slate-900">{title}</h2>{subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}</div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Password input with a show/hide toggle. The toggle's accessible name is visually hidden text (not aria-label) and
 * avoids the word "password", so label lookups for "Password" still find only the input. */
export function PasswordInput({ className = "", ...props }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative block">
      <input {...props} type={show ? "text" : "password"} className={`input pr-10 ${className}`} />
      <button type="button" onClick={() => setShow((v) => !v)} aria-pressed={show}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-lg text-slate-400 transition-colors hover:text-slate-700 focus-visible:text-slate-900">
        {show ? <EyeOff size={16} aria-hidden /> : <Eye size={16} aria-hidden />}
        <span className="sr-only">{show ? "Hide" : "Show"} characters</span>
      </button>
    </span>
  );
}

export function Field({ label, error, children, hint }) {
  return (
    <label className="block">
      {label && <span className="label">{label}</span>}
      {children}
      {hint && !error && <span className="mt-1.5 block text-xs text-slate-500">{hint}</span>}
      {error && <span className="mt-1.5 block text-xs text-rose-600">{error}</span>}
    </label>
  );
}

export function Modal({ open, onClose, title, children, footer, wide }) {
  const dialogRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  // Keyboard users: move focus into the dialog when it opens (unless a field inside already took it with
  // autoFocus), and give it back to whatever was focused before (usually the button that opened it) on close.
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    if (dialogRef.current && !dialogRef.current.contains(document.activeElement)) dialogRef.current.focus();
    return () => { if (previous && document.contains(previous)) previous.focus?.(); };
  }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in items-start justify-center overflow-y-auto bg-night-900/50 p-4 backdrop-blur-[2px] sm:items-center" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} ref={dialogRef} tabIndex={-1}
        className={`card my-8 w-full animate-scale-in !bg-white !shadow-pop focus:outline-none ${wide ? "max-w-3xl" : "max-w-lg"}`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pb-1 pt-4">
          <h2 className="text-[17px] font-semibold">{title}</h2>
          <button className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 rounded-b-xl border-t border-slate-200 bg-slate-50 px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmButton({ message = "Are you sure?", onConfirm, children, ...props }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Button {...props} onClick={() => setOpen(true)}>{children}</Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Please confirm"
        footer={<>
          <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant={props.variant === "danger" ? "danger" : "primary"} loading={busy}
            onClick={async () => { setBusy(true); try { await onConfirm(); setOpen(false); } finally { setBusy(false); } }}>
            Confirm
          </Button>
        </>}>
        <p className="text-sm text-slate-600">{message}</p>
      </Modal>
    </>
  );
}

// Data table with an empty state. When `onRowClick` is given, each row is clickable and can also be reached with
// Tab and opened with Enter (Enter on a button or link inside the row still triggers only that control).
export function Table({ columns, rows, empty = "No records found", rowKey = (r) => r.id, onRowClick }) {
  if (!rows?.length) return <EmptyState title={empty} />;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead className="border-b border-slate-200 bg-slate-50">
          <tr>{columns.map((c) => <th key={c.key || c.label} className="th">{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={rowKey(r)} onClick={() => onRowClick?.(r)}
              className={onRowClick ? "cursor-pointer transition-colors hover:bg-slate-50 focus:outline-none focus-visible:bg-brand-50/60 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500" : ""}
              {...(onRowClick && {
                tabIndex: 0,
                onKeyDown: (e) => { if (e.key === "Enter" && e.target === e.currentTarget) { e.preventDefault(); onRowClick(r); } },
              })}>
              {columns.map((c) => <td key={c.key || c.label} className="td">{c.render ? c.render(r) : r[c.key] ?? "—"}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pagination({ page, pages, total, onPage }) {
  if (!pages || pages <= 1) return total ? <p className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">{total} record{total === 1 ? "" : "s"}</p> : null;
  return (
    <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-sm">
      <span className="num text-xs text-slate-500">Page {page} of {pages} · {total} records</span>
      <div className="flex gap-2">
        <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
      </div>
    </div>
  );
}

export function Tabs({ tabs, value, onChange }) {
  return (
    <div className="mb-6 flex w-fit max-w-full gap-0.5 overflow-x-auto rounded-lg border border-slate-200 bg-slate-100 p-0.5" role="tablist">
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={`whitespace-nowrap rounded-md px-3.5 py-1.5 text-sm font-medium transition ${
            value === t.value ? "bg-white text-slate-950 shadow-soft ring-1 ring-slate-200" : "text-slate-500 hover:text-slate-900"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function ScoreBar({ value, max = 100, label }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  const color = pct >= 75 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div>
      {label && (
        <div className="mb-1.5 flex justify-between gap-3 text-xs">
          <span className="text-slate-600">{label}</span>
          <span className="num font-semibold text-slate-900">{value == null ? "—" : `${value}${max === 100 ? "" : `/${max}`}`}</span>
        </div>
      )}
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-[width] duration-700 ${value == null ? "" : color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function TagInput({ value = [], onChange, placeholder = "Type and press Enter" }) {
  const [text, setText] = useState("");
  const add = () => {
    const parts = text.split(",").map((s) => s.trim()).filter(Boolean);
    if (parts.length) onChange([...new Set([...value, ...parts])]);
    setText("");
  };
  return (
    <div className="input flex min-h-9 flex-wrap items-center gap-1.5 focus-within:border-brand-500 focus-within:ring-4 focus-within:ring-brand-500/15">
      {value.map((t) => (
        <span key={t} className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200">
          {t}
          <button type="button" className="text-slate-400 hover:text-slate-700" onClick={() => onChange(value.filter((x) => x !== t))} aria-label={`Remove ${t}`}><X size={12} /></button>
        </span>
      ))}
      <input className="min-w-[8rem] flex-1 border-0 bg-transparent p-0 text-sm focus:outline-none focus:ring-0" value={text}
        placeholder={placeholder} onChange={(e) => setText(e.target.value)} onBlur={add}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(); } }} />
    </div>
  );
}

export const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—");
export const fmtDateTime = (s) => (s ? new Date(s).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
export const toLocalInput = (s) => {
  if (!s) return "";
  const d = new Date(s);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
export const fromLocalInput = (s) => (s ? new Date(s).toISOString() : null);
