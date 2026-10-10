import { useState } from "react";
import { get, patch } from "../../api";
import { Button, Card, ErrorBox, Modal, Notice, PageHeader, Pagination, Pill, Spinner, Table, fmtDateTime, useApi, useToast } from "../../components/ui";

const STATUS_TONE = { none: "green", warning: "amber", review: "red", unavailable: "slate" };
const SEV_TONE = { info: "slate", low: "blue", medium: "amber", high: "red" };
const REVIEW = [
  { value: "pending", label: "Not reviewed" }, { value: "no_concern", label: "Reviewed - no concern" },
  { value: "concern_noted", label: "Reviewed - concern noted" }, { value: "dismissed", label: "Dismissed (technical / false signal)" },
];
const fmt = (ms) => { if (ms == null) return "—"; const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };

/**
 * Interview integrity review for admins and authorised reviewers. Wording is deliberately neutral: signals are
 * approximate, never a verdict, and are reviewed separately from interview performance.
 */
export function IntegrityReview() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useApi(() => get("/monitoring/sessions", { page, status }), [page, status]);
  const [open, setOpen] = useState(null);
  const toast = useToast();
  const view = async (id) => { try { setOpen(await get(`/monitoring/sessions/${id}`)); } catch (e) { toast(e.message, "error"); } };

  return (
    <div className="space-y-4">
      <Notice tone="blue">Camera and browser signals from monitored live interviews. They are approximate (lighting, camera position, glasses, disability and normal movement cause false signals), they are not evidence of misconduct on their own, and they never change interview scores. The absence of events does not prove that nothing happened. Viewing and reviewing is recorded in the audit log.</Notice>
      <Card title="Monitored interviews" bodyClass="" actions={
        <select className="input w-auto py-1" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} aria-label="Filter by status">
          <option value="">All</option><option value="review">Event requires review</option><option value="warning">Monitoring warning</option>
          <option value="none">No integrity events detected</option><option value="unavailable">Monitoring unavailable</option>
        </select>}>
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No monitored interviews" onRowClick={(r) => view(r.id)} columns={[
              { label: "Student", key: "student_name" }, { label: "Interview", render: (r) => `${r.job_role} (${r.interviewer})` },
              { label: "Interview status", key: "status" },
              { label: "Monitoring", render: (r) => <Pill tone={STATUS_TONE[r.monitoring.status.code]}>{r.monitoring.status.label}</Pill> },
              { label: "Events", render: (r) => <span className="text-xs">{r.monitoring.total} {Object.entries(r.monitoring.counts).map(([k, v]) => `${k}: ${v}`).join(", ")}</span> },
              { label: "Date", render: (r) => fmtDateTime(r.created_at) }]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
      <Modal open={!!open} onClose={() => { setOpen(null); reload(); }} title={open ? `${open.student_name} · ${open.job_role}` : ""} wide>
        {open && <SessionDetail data={open} onChange={setOpen} />}
      </Modal>
    </div>
  );
}

function SessionDetail({ data, onChange }) {
  const cfg = data.monitoring.config || {};
  const on = Object.entries(cfg.features || {}).filter(([, v]) => v).map(([k]) => k.replace("_", " "));
  return (
    <div className="space-y-4 text-sm">
      <div className="grid gap-2 sm:grid-cols-2">
        <p><b>Monitoring status:</b> {data.monitoring.status.label} - {data.monitoring.status.detail}</p>
        <p><b>Interview:</b> {data.interview_status}{data.completed_at ? ` (finished ${fmtDateTime(data.completed_at)})` : ""}</p>
        <p><b>Consented features:</b> {on.join(", ") || "none"}</p>
        <p><b>Camera permission:</b> {cfg.camera_permission || "—"}{cfg.withdrawn_at ? ` · monitoring stopped by the candidate at ${fmtDateTime(cfg.withdrawn_at)}` : ""}</p>
      </div>
      <p className="text-xs text-slate-500">{data.note}</p>
      {data.events.length === 0 ? <p className="text-slate-500">No events were recorded.</p> : (
        <ul className="divide-y divide-slate-100">
          {data.events.map((e) => <EventRow key={e.id} e={e} onSaved={(u) => onChange({ ...data, events: data.events.map((x) => (x.id === u.id ? u : x)) })} />)}
        </ul>
      )}
    </div>
  );
}

function EventRow({ e, onSaved }) {
  const toast = useToast();
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
        <span className="text-xs text-slate-500">at {fmt(e.t_ms)} · duration {fmt(e.duration_ms)}
          {e.confidence != null && ` · frame agreement ${Math.round(e.confidence * 100)}%${e.confidence_sufficient ? "" : " (too low to rely on)"}`}</span>
      </div>
      {e.candidate_explanation && <p className="rounded bg-slate-50 px-2 py-1"><b>Candidate's explanation:</b> {e.candidate_explanation}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <select className="input w-auto py-1 text-sm" value={status} onChange={(ev) => setStatus(ev.target.value)} aria-label="Review status">
          {REVIEW.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <input className="input flex-1 py-1 text-sm" maxLength={2000} placeholder="Reviewer notes (not shown to the student)" value={notes} onChange={(ev) => setNotes(ev.target.value)} />
        <Button size="sm" onClick={save} loading={busy}>Save</Button>
      </div>
    </li>
  );
}

/** Stand-alone page for authorised mentors. */
export default function IntegrityReviewPage() {
  return (
    <div>
      <PageHeader title="Interview integrity review" subtitle="Monitored live interviews of students you support." />
      <IntegrityReview />
    </div>
  );
}
