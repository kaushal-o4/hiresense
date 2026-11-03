/*
 * Shared UI kit used by every page: the useApi data-loading hook, toasts, and the Button, Card, Table,
 * Modal, Pagination, Tabs, ErrorBox, EmptyState and form primitives, plus date-formatting helpers.
 * Change styles here (not per page) so the whole app stays consistent.
 *
 * Visual rules: neutral surfaces with 1px borders, ink (slate-900) for primary actions, one accent (brand/cobalt)
 * for links, focus and data. No gradients, no glows, colour only where it carries meaning (status, scores).
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Inbox, Info, Loader2, X } from "lucide-react";

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
            className="pointer-events-auto flex animate-fade-up items-start gap-3 rounded-xl border border-slate-200 bg-white/90 px-4 py-3 text-sm text-slate-800 shadow-pop backdrop-blur-xl">
            {t.type === "error"
              ? <AlertTriangle size={17} className="mt-0.5 shrink-0 text-rose-600" />
              : <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-emerald-600" />}
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
  primary: "bg-gradient-to-r from-brand-500 to-violet-500 text-snow shadow-glow hover:brightness-110 hover:shadow-[0_0_0_1px_rgb(129_140_248/0.5),0_10px_30px_-6px_rgb(99_102_241/0.7)] active:brightness-95",
  secondary: "border border-slate-200 bg-slate-100/60 text-slate-800 backdrop-blur hover:border-slate-300 hover:bg-slate-200/60 hover:text-slate-900",
  danger: "bg-gradient-to-r from-rose-500 to-rose-600 text-snow shadow-[0_8px_24px_-8px_rgb(244_63_94/0.6)] hover:brightness-110",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  success: "bg-gradient-to-r from-emerald-500 to-teal-500 text-snow shadow-[0_8px_24px_-8px_rgb(16_185_129/0.55)] hover:brightness-110",
  accent: "bg-brand-500 text-snow shadow-glow hover:bg-brand-400",
};

export function Button({ variant = "primary", size = "md", loading, children, className = "", ...props }) {
  const sz = size === "sm" ? "h-8 rounded-lg px-3 text-[13px]" : size === "lg" ? "h-12 rounded-xl px-6 text-[15px]" : "h-10 rounded-xl px-4 text-sm";
  return (
    <button
      className={`inline-flex select-none items-center justify-center gap-2 whitespace-nowrap font-medium transition duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 active:scale-[0.98] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 ${BTN[variant] || BTN.primary} ${sz} ${className}`}
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
        <div className="flex min-h-[56px] flex-wrap items-center justify-between gap-2 border-b border-slate-200/70 px-5 py-3">
          {title && <h2 className="flex items-center gap-2.5 text-[15px] font-semibold"><span className="h-3.5 w-1 rounded-full bg-gradient-to-b from-brand-400 to-violet-500" aria-hidden />{title}</h2>}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

// Each tone: a glowing icon tile + matching corner light, so a row of stats reads as distinct but calm.
const STAT_TONES = {
  brand: ["text-brand-700 bg-brand-500/15 ring-brand-400/30", "rgb(99 102 241 / 0.22)"],
  violet: ["text-brand-700 bg-violet-500/15 ring-violet-400/30", "rgb(139 92 246 / 0.22)"],
  green: ["text-emerald-700 bg-emerald-500/15 ring-emerald-400/30", "rgb(16 185 129 / 0.2)"],
  teal: ["text-teal-700 bg-teal-500/15 ring-teal-400/30", "rgb(20 184 166 / 0.2)"],
  amber: ["text-amber-700 bg-amber-500/15 ring-amber-400/30", "rgb(245 158 11 / 0.2)"],
  red: ["text-rose-700 bg-rose-500/15 ring-rose-400/30", "rgb(244 63 94 / 0.2)"],
  pink: ["text-rose-700 bg-rose-500/15 ring-rose-400/30", "rgb(244 63 94 / 0.2)"],
  sky: ["text-sky-700 bg-sky-500/15 ring-sky-400/30", "rgb(14 165 233 / 0.2)"],
};

export function StatCard({ label, value, icon: Icon, hint, tone = "brand" }) {
  const [tile, light] = STAT_TONES[tone] || STAT_TONES.brand;
  return (
    <div className="card card-hover relative flex flex-col gap-1 overflow-hidden p-4 sm:p-5">
      <div className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full blur-2xl" style={{ background: light }} aria-hidden />
      <div className="relative flex items-start justify-between gap-2">
        <p className="truncate text-[13px] font-medium text-slate-500">{label}</p>
        {Icon && <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset ${tile}`}><Icon size={16} aria-hidden /></span>}
      </div>
      <p className="num relative truncate text-[28px] font-semibold leading-tight tracking-tight text-slate-950">{value ?? "—"}</p>
      {hint && <p className="relative truncate text-xs text-slate-500">{hint}</p>}
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
    <div className="flex items-center justify-center gap-2 py-16 text-slate-400" role="status">
      <Loader2 className="animate-spin" size={18} /> <span className="text-sm text-slate-500">{label}</span>
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
      <div className="relative mb-3">
        <div className="absolute inset-0 rounded-2xl bg-brand-500/30 blur-xl" aria-hidden />
        <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl border border-brand-400/30 bg-gradient-to-br from-brand-500/25 to-violet-500/10 text-brand-700"><Icon size={20} /></div>
      </div>
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      {message && <p className="max-w-sm text-sm text-slate-500">{message}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <h1 className="text-gradient text-[28px] font-semibold leading-tight tracking-tight sm:text-[34px]">{title}</h1>
        {subtitle && <div className="mt-2 max-w-3xl text-[15px] leading-relaxed text-slate-500">{subtitle}</div>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
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
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:items-center" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} ref={dialogRef} tabIndex={-1}
        className={`card my-8 w-full animate-fade-up !bg-white shadow-pop focus:outline-none ${wide ? "max-w-3xl" : "max-w-lg"}`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 pb-1 pt-4">
          <h2 className="text-base font-semibold">{title}</h2>
          <button className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 rounded-b-2xl border-t border-slate-200 bg-slate-100/40 px-5 py-3">{footer}</div>}
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
        <thead className="border-b border-slate-200 bg-slate-100/40">
          <tr>{columns.map((c) => <th key={c.key || c.label} className="th">{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r) => (
            <tr key={rowKey(r)} onClick={() => onRowClick?.(r)}
              className={onRowClick ? "cursor-pointer transition-colors hover:bg-brand-500/[0.06] focus:outline-none focus-visible:bg-brand-50/60 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-400" : ""}
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
    <div className="mb-6 flex w-fit max-w-full gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-slate-100/60 p-1 backdrop-blur" role="tablist">
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={`whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
            value === t.value ? "bg-gradient-to-r from-brand-500 to-violet-500 text-snow shadow-glow" : "text-slate-500 hover:bg-slate-200/60 hover:text-slate-900"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function ScoreBar({ value, max = 100, label }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  const color = pct >= 75 ? "bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_10px_rgb(16_185_129/0.5)]"
    : pct >= 50 ? "bg-gradient-to-r from-amber-500 to-amber-400 shadow-[0_0_10px_rgb(245_158_11/0.45)]"
      : "bg-gradient-to-r from-rose-500 to-rose-400 shadow-[0_0_10px_rgb(244_63_94/0.45)]";
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
    <div className="input flex min-h-9 flex-wrap items-center gap-1.5 focus-within:border-brand-500 focus-within:ring-[3px] focus-within:ring-brand-500/15">
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
