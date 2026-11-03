/*
 * Review of interview-security events (camera, browser, audio, connection) for admins, authorised mentors and
 * recruiters (completed interviews of their own applicants). Events are signals for a person to judge, never
 * automatic penalties, and the security summary is kept apart from interview performance.
 */

import { useState } from "react";
import { get, patch } from "../../api";
import { useAuth } from "../../auth";
import { AttentionReport } from "../../monitoring/AttentionPanels";
import { Button, Card, ErrorBox, Modal, Notice, PageHeader, Pagination, Pill, Spinner, Table, fmtDateTime, useApi, useToast } from "../../components/ui";

const STATUS_TONE = { none: "green", warning: "amber", review: "red", unavailable: "slate" };
const SEV_TONE = { info: "slate", low: "blue", medium: "amber", high: "red" };
const RISK_TONE = { none: "green", low: "blue", moderate: "amber", high: "red" };
export const REVIEW = [
  { value: "pending", label: "Not reviewed" }, { value: "no_concern", label: "Reviewed - no concern" },
  { value: "concern_noted", label: "Reviewed - concern noted" }, { value: "false_positive", label: "False positive" },
  { value: "dismissed", label: "Dismissed (technical / false signal)" }, { value: "needs_review", label: "Further review requested" },
];
const REVIEW_LABEL = Object.fromEntries(REVIEW.map((r) => [r.value, r.label]));
const fmt = (ms) => { if (ms == null) return "—"; const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const clock = (iso) => (iso ? new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : null);
const pretty = (c) => c.toLowerCase().replaceAll("_", " ");
const EMPTY = { q: "", date_from: "", date_to: "", category: "", severity: "", review_status: "", status: "", risk: "" };

/**
 * Monitored interviews with filters. `studentId` fixes the list to one candidate (recruiter candidate page).
 * Wording is deliberately neutral: signals are approximate, never a verdict.
 */
export function IntegrityReview({ studentId = null, compact = false }) {
  const [page, setPage] = useState(1);
  const [f, setF] = useState(EMPTY);
  const params = { page, ...f, ...(studentId ? { q: String(studentId) } : {}) };
  const { data, error, loading, reload } = useApi(() => get("/monitoring/sessions", params), [page, JSON.stringify(f), studentId]);
  const [open, setOpen] = useState(null);
  const toast = useToast();
  const view = async (id) => { try { setOpen(await get(`/monitoring/sessions/${id}`)); } catch (e) { toast(e.message, "error"); } };
  const set = (k) => (e) => { setF((x) => ({ ...x, [k]: e.target.value })); setPage(1); };

  if (compact && data && !data.total) return null; // nothing to show on a candidate page
  return (
    <div className="space-y-4">
      {!compact && <Notice tone="blue">Camera, browser, audio and connection signals from monitored live interviews. They are approximate (lighting, camera position, glasses, disability and normal movement cause false signals), they are not evidence of misconduct on their own, and they never change interview scores. The security summary must never be the only basis for a hiring decision. The absence of events does not prove that nothing happened. Viewing and reviewing is recorded in the audit log.</Notice>}
      <Card title={compact ? "Interview security reports" : "Monitored interviews"} bodyClass="">
        {!compact && (
          <div className="grid gap-2 border-b border-slate-100 p-4 sm:grid-cols-2 lg:grid-cols-4">
            {!studentId && <input className="input py-1" placeholder="Candidate name or id" value={f.q} onChange={set("q")} aria-label="Candidate" />}
            <input className="input py-1" type="date" value={f.date_from} onChange={set("date_from")} aria-label="Interview date from" />
            <input className="input py-1" type="date" value={f.date_to} onChange={set("date_to")} aria-label="Interview date to" />
            <select className="input py-1" value={f.category} onChange={set("category")} aria-label="Event category">
              <option value="">All event categories</option>
              {(data?.categories || []).map((c) => <option key={c} value={c}>{pretty(c)}</option>)}
            </select>
            <select className="input py-1" value={f.severity} onChange={set("severity")} aria-label="Severity">
              <option value="">Any severity</option>{["info", "low", "medium", "high"].map((s) => <option key={s}>{s}</option>)}
            </select>
            <select className="input py-1" value={f.review_status} onChange={set("review_status")} aria-label="Review status">
              <option value="">Any review status</option>{REVIEW.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
            <select className="input py-1" value={f.status} onChange={set("status")} aria-label="Monitoring status">
              <option value="">Any monitoring status</option><option value="review">Event requires review</option><option value="warning">Monitoring warning</option>
              <option value="none">No integrity events detected</option><option value="unavailable">Monitoring unavailable</option>
            </select>
            <select className="input py-1" value={f.risk} onChange={set("risk")} aria-label="Summary">
              <option value="">Any summary</option><option value="none">No significant events</option><option value="low">Low</option>
              <option value="moderate">Moderate</option><option value="high">High - requires review</option>
            </select>
          </div>
        )}
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No monitored interviews match" onRowClick={(r) => view(r.id)} columns={[
              ...(studentId ? [] : [{ label: "Candidate", render: (r) => <span>{r.student_name} <span className="text-xs text-slate-400">#{r.student_id}</span></span> }]),
              { label: "Interview", render: (r) => <span>{r.job_role} <span className="text-xs text-slate-400">#{r.id} · {r.interviewer}</span></span> },
              { label: "Date", render: (r) => fmtDateTime(r.created_at) },
              { label: "Duration", render: (r) => (r.duration_s != null ? fmt(r.duration_s * 1000) : r.status) },
              { label: "Summary", render: (r) => <Pill tone={RISK_TONE[r.monitoring.risk.band.code]}>{r.monitoring.risk.band.label}</Pill> },
              { label: "Monitoring", render: (r) => <Pill tone={STATUS_TONE[r.monitoring.status.code]}>{r.monitoring.status.label}</Pill> },
              { label: "Events", render: (r) => <span className="text-xs">{r.monitoring.total} {Object.entries(r.monitoring.counts).map(([k, v]) => `${k}: ${v}`).join(", ")}</span> }]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
      <Modal open={!!open} onClose={() => { setOpen(null); reload(); }} title={open ? `${open.student_name} · ${open.job_role} · interview #${open.id}` : ""} wide>
        {open && <SessionDetail data={open} onChange={setOpen} />}
      </Modal>
    </div>
  );
}

function SessionDetail({ data, onChange }) {
  const [view, setView] = useState("timeline");
  const [only, setOnly] = useState("");
  const cfg = data.monitoring.config || {};
  const on = Object.entries(cfg.features || {}).filter(([, v]) => v).map(([k]) => k.replaceAll("_", " "));
  const risk = data.monitoring.risk;
  const events = only ? data.events.filter((e) => e.category === only) : data.events;
  const saved = (u) => onChange({ ...data, events: data.events.map((x) => (x.id === u.id ? { ...x, ...u } : x)) });
  return (
    <div className="space-y-4 text-sm">
      <div className="grid gap-2 sm:grid-cols-2">
        <p><b>Candidate:</b> {data.student_name} (#{data.student_id}) · <b>Interview:</b> #{data.id}</p>
        <p><b>Interview:</b> {data.interview_status} · started {fmtDateTime(data.created_at)}{data.completed_at ? ` · finished ${fmtDateTime(data.completed_at)}` : ""}</p>
        <p><b>Monitoring status:</b> {data.monitoring.status.label} - {data.monitoring.status.detail}</p>
        {cfg.features && <p><b>Consented features:</b> {on.join(", ") || "none"}{cfg.withdrawn_at ? ` · monitoring stopped by the candidate at ${fmtDateTime(cfg.withdrawn_at)}` : ""}</p>}
      </div>
      <RiskPanel risk={risk} />
      <AttentionReport a={data.attention} />
      <p className="text-xs text-slate-500">{data.note}</p>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1" role="tablist">
          {["timeline", "review"].map((v) => (
            <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}
              className={`rounded-lg px-3 py-1 text-xs font-semibold ${view === v ? "bg-brand-500 text-snow shadow-glow" : "bg-slate-100 text-slate-600"}`}>
              {v === "timeline" ? "Timeline" : "Review events"}
            </button>))}
        </div>
        <select className="input ml-auto w-auto py-1 text-xs" value={only} onChange={(e) => setOnly(e.target.value)} aria-label="Show category">
          <option value="">All categories</option>
          {[...new Set(data.events.map((e) => e.category))].map((c) => <option key={c} value={c}>{pretty(c)}</option>)}
        </select>
      </div>
      {events.length === 0 ? <p className="text-slate-500">No events were recorded{only ? " in this category" : ""}.</p>
        : view === "timeline" ? <Timeline events={events} /> : (
          <ul className="divide-y divide-slate-100">{events.map((e) => <EventRow key={e.id} e={e} onSaved={saved} />)}</ul>
        )}
    </div>
  );
}

/** How the summary was calculated: which rules contributed, with what weight, and what was not counted. */
function RiskPanel({ risk }) {
  if (!risk) return null;
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="flex flex-wrap items-center gap-2"><b>Security summary:</b> <Pill tone={RISK_TONE[risk.band.code]}>{risk.band.label}</Pill>
        <span className="text-xs text-slate-500">{risk.points} points</span></p>
      {risk.contributions.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-slate-700">
          {risk.contributions.map((c) => <li key={c.rule}>{c.label}: {c.occurrences} × weight {c.weight}{c.occurrences > c.capped_at ? ` (capped at ${c.capped_at})` : ""} = <b>{c.points}</b> <span className="text-slate-400">— counted as {c.counted_as}</span></li>)}
        </ul>
      )}
      <p className="mt-1 text-xs text-slate-500">Not counted: {risk.excluded.low_confidence} low-confidence event(s), {risk.excluded.cleared_by_reviewer} cleared by a reviewer. {risk.method}</p>
      <p className="mt-1 text-xs font-medium text-slate-600">{risk.disclaimer}</p>
    </div>
  );
}

/** Chronological start / end entries built from the recorded events only. */
function Timeline({ events }) {
  const rows = [];
  for (const e of events) {
    rows.push({ key: `${e.id}s`, t: e.t_ms, at: clock(e.start_timestamp), e, text: e.description });
    if (e.duration_ms && e.end_timestamp) rows.push({ key: `${e.id}e`, t: e.t_ms + e.duration_ms, at: clock(e.end_timestamp), e, text: `${e.label} - ended`, end: true });
  }
  rows.sort((a, b) => a.t - b.t);
  return (
    <ol className="space-y-1 border-l-2 border-slate-200 pl-4">
      {rows.map((r) => (
        <li key={r.key} className={`relative ${r.end ? "text-slate-500" : ""}`}>
          <span className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ${r.end ? "bg-slate-300" : r.e.severity === "high" ? "bg-red-500" : r.e.severity === "medium" ? "bg-amber-500" : r.e.severity === "low" ? "bg-sky-500" : "bg-slate-400"}`} />
          <span className="font-mono text-xs">{r.at || fmt(r.t)}</span> <span className="text-xs text-slate-400">({fmt(r.t)} into the interview)</span> — {r.text}
          {!r.end && <> <Pill tone={SEV_TONE[r.e.severity]}>{r.e.severity}</Pill>{r.e.confidence != null && <span className="text-xs text-slate-500"> agreement {Math.round(r.e.confidence * 100)}%{r.e.confidence_sufficient ? "" : " (too low to rely on)"}</span>}
            <span className="text-xs text-slate-400"> · {REVIEW_LABEL[r.e.review_status] || r.e.review_status}</span></>}
        </li>
      ))}
    </ol>
  );
}

function EventRow({ e, onSaved }) {
  const toast = useToast();
  const { user } = useAuth();
  const [status, setStatus] = useState(e.review_status);
  const [notes, setNotes] = useState(e.reviewer_notes || "");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try { onSaved(await patch(`/monitoring/events/${e.id}`, { review_status: status, reviewer_notes: notes || null })); toast("Review saved"); }
    catch (err) { toast(err.message, "error"); }
    finally { setBusy(false); }
  };
  return (
    <li className="space-y-2 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{e.label}</span>
        <Pill tone={SEV_TONE[e.severity]}>{e.severity}</Pill>
        <span className="text-xs text-slate-500">{pretty(e.category)} · {e.start_timestamp ? clock(e.start_timestamp) : `at ${fmt(e.t_ms)}`} · duration {fmt(e.duration_ms)}
          {e.confidence != null && ` · frame agreement ${Math.round(e.confidence * 100)}%${e.confidence_sufficient ? "" : " (too low to rely on)"}`} · source {e.detection_source}</span>
      </div>
      <p className="text-xs text-slate-600">{e.description}</p>
      {e.candidate_explanation && <p className="rounded bg-slate-50 px-2 py-1"><b>Candidate's explanation:</b> {e.candidate_explanation}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <select className="input w-auto py-1 text-sm" value={status} onChange={(ev) => setStatus(ev.target.value)} aria-label="Review status">
          {REVIEW.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <input className="input flex-1 py-1 text-sm" maxLength={2000} placeholder="Reviewer notes (not shown to the candidate)" value={notes} onChange={(ev) => setNotes(ev.target.value)} aria-label="Reviewer notes" />
        <Button size="sm" onClick={save} loading={busy}>Save</Button>
      </div>
      {user?.role === "admin" && e.review_history?.length > 0 && (
        <details className="text-xs text-slate-500"><summary>Review history ({e.review_history.length})</summary>
          <ul className="mt-1 space-y-0.5">{e.review_history.map((h, i) => <li key={i}>{fmtDateTime(h.at)} · {h.role} #{h.reviewer_id ?? "?"} · {REVIEW_LABEL[h.status] || h.status}{h.notes ? ` — ${h.notes}` : ""}</li>)}</ul>
        </details>
      )}
    </li>
  );
}

/** Stand-alone page for authorised mentors and recruiters. */
export default function IntegrityReviewPage() {
  const { user } = useAuth();
  return (
    <div>
      <PageHeader title={user?.role === "recruiter" ? "Interview security reports" : "Interview integrity review"}
        subtitle={user?.role === "recruiter" ? "Completed, monitored interviews of candidates who applied to your jobs." : "Monitored live interviews of students you support."} />
      <IntegrityReview />
    </div>
  );
}
