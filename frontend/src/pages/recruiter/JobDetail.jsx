/*
 * Applicants for one job: rule-based match, on-demand AI match review, side-by-side comparison and
 * status changes (shortlist, schedule interview, select, reject) that notify the student.
 */

import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Scale, Sparkles } from "lucide-react";
import { get, patch, post } from "../../api";
import { chipClass } from "../shared/chips";
import {
  Button, Card, ErrorBox, Field, Modal, Notice, PageHeader, Pill, ScoreBar, Spinner, StatusPill, fromLocalInput,
  useApi, useToast,
} from "../../components/ui";

const STATUSES = ["applied", "shortlisted", "interview_scheduled", "selected", "rejected"];
const REC_TONE = { strong_fit: "green", potential_fit: "amber", not_a_fit: "red" };

export const MATCH_METHOD = {
  "semantic+ai": { label: "semantic match + local AI explanation", tone: "brand" },
  semantic: { label: "semantic match (embeddings)", tone: "brand" },
  rule_based: { label: "keyword match only (embedding model unavailable)", tone: "gray" },
  ai: { label: "AI assessment (older)", tone: "brand" },
  unavailable: { label: "not available", tone: "gray" },
};

function MatchPanel({ match }) {
  if (!match) return null;
  const method = MATCH_METHOD[match.method] || { label: match.method, tone: "gray" };
  const missingRequired = match.missing_required_skills ?? match.missing_skills ?? [];
  return (
    <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">Match {match.score}/100</span>
        <Pill tone={method.tone}>{method.label}</Pill>
        {match.recommendation && <Pill tone={REC_TONE[match.recommendation]}>{match.recommendation.replace(/_/g, " ")}</Pill>}
        {match.score_capped && <Pill tone="amber">capped: required skills missing</Pill>}
      </div>
      {match.explanation && <p className="mt-2 text-slate-600">{match.explanation}</p>}
      {match.score_explanation && <p className="mt-1 text-xs text-slate-500">How the score was calculated: {match.score_explanation}</p>}
      {match.ai_note && <p className="mt-1 text-xs text-amber-700">{match.ai_note}</p>}
      {match.criteria_scores?.length > 0 && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {match.criteria_scores.map((c) => <div key={c.criterion}><ScoreBar label={c.criterion} value={c.score} /><p className="text-[11px] text-slate-500">{c.reason}</p></div>)}
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        {match.matched_skills?.map((s) => <Pill key={s} tone="green">{s}</Pill>)}
        {match.partially_matched_skills?.map((p) => <Pill key={p.skill} tone="amber">{p.skill} ≈ {p.closest}</Pill>)}
        {missingRequired.map((s) => <Pill key={s} tone="red">{s} (required)</Pill>)}
        {match.missing_preferred_skills?.map((s) => <Pill key={s} tone="gray">{s} (preferred)</Pill>)}
      </div>
      {match.relevant_projects?.length > 0 && (
        <p className="mt-2 text-xs text-slate-600"><b>Relevant projects:</b> {match.relevant_projects.map((p) => p.name).join(", ")}</p>
      )}
      {(match.strengths?.length > 0 || match.concerns?.length > 0) && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2 text-xs">
          <div><p className="eyebrow mb-1.5">Strengths</p><ul className="space-y-1">{match.strengths?.map((s, i) => <li key={i} className="flex gap-1.5 text-slate-700"><CheckCircle2 size={13} className="mt-px shrink-0 text-emerald-600" />{s}</li>)}</ul></div>
          <div><p className="eyebrow mb-1.5">Concerns</p><ul className="space-y-1">{match.concerns?.map((s, i) => <li key={i} className="flex gap-1.5 text-slate-700"><AlertTriangle size={13} className="mt-px shrink-0 text-amber-600" />{s}</li>)}</ul></div>
        </div>
      )}
    </div>
  );
}

export default function RecruiterJobDetail() {
  const { id } = useParams();
  const toast = useToast();
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState([]);
  const [compare, setCompare] = useState(null);
  const [statusModal, setStatusModal] = useState(null);
  const [busy, setBusy] = useState(null);
  const { data, error, loading, reload } = useApi(() => get(`/recruiter/jobs/${id}/applications`, { status: filter }), [id, filter]);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const job = data.job;

  const runMatch = async (appId) => {
    setBusy(appId);
    try {
      const res = await post(`/recruiter/applications/${appId}/match`);
      if (res.ai_error) toast(`Match score updated. AI explanation unavailable: ${res.ai_error}`, "error");
      else toast("Match updated with AI explanation");
      reload();
    } catch (e) { toast(e.message, "error"); } finally { setBusy(null); }
  };

  const runCompare = async () => {
    try { setCompare(await post(`/recruiter/jobs/${id}/compare`, { application_ids: selected })); } catch (e) { toast(e.message, "error"); }
  };

  const saveStatus = async () => {
    setBusy("status");
    try {
      await patch(`/recruiter/applications/${statusModal.app.id}/status`, {
        status: statusModal.status, note: statusModal.note || null, interview_at: fromLocalInput(statusModal.interview_at),
      });
      toast("Status updated - the candidate has been notified");
      setStatusModal(null);
      reload();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={job.title} subtitle={<span className="flex items-center gap-2">{job.location} · <StatusPill status={job.status} /></span>}
        actions={<>
          <Link to={`/recruiter/candidates?job_id=${job.id}`}><Button variant="secondary">Find matching candidates</Button></Link>
          <Button disabled={selected.length < 2} onClick={runCompare}><Scale size={16} /> Compare ({selected.length})</Button>
        </>} />
      <Card>
        <div className="flex flex-wrap gap-1">{job.required_skills.map((s) => <Pill key={s} tone="brand">{s}</Pill>)}{job.preferred_skills.map((s) => <Pill key={s}>{s}</Pill>)}</div>
        <p className="mt-2 line-clamp-3 text-sm text-slate-600">{job.description}</p>
      </Card>
      <div className="flex flex-wrap gap-2">
        {["", ...STATUSES, "withdrawn"].map((s) => (
          <button key={s || "all"} onClick={() => setFilter(s)} aria-pressed={filter === s} className={chipClass(filter === s)}>{s ? s.replace(/_/g, " ") : "All"}</button>
        ))}
      </div>
      <Notice tone="blue">AI recommendations are advisory. Review the evidence and make the final decision yourself. Select 2-5 candidates to compare side by side.</Notice>
      {data.items.length === 0 && <Card><p className="py-6 text-center text-sm text-slate-500">No applications in this view.</p></Card>}
      <div className="space-y-4">
        {data.items.map((a) => (
          <Card key={a.id}>
            <div className="flex flex-wrap items-start gap-3">
              <input type="checkbox" className="mt-1" aria-label={`Select ${a.student.full_name}`} checked={selected.includes(a.id)} disabled={!selected.includes(a.id) && selected.length >= 5}
                onChange={(e) => setSelected(e.target.checked ? [...selected, a.id] : selected.filter((x) => x !== a.id))} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <Link className="font-semibold text-brand-700 hover:underline" to={`/recruiter/candidates/${a.student_id}`}>{a.student.full_name}</Link>
                  <StatusPill status={a.status} />
                </div>
                <p className="text-sm text-slate-600">{a.student.college || "—"} · {a.student.branch || "—"} · CGPA {a.student.cgpa ?? "—"} · {a.student.graduation_year || "—"}</p>
                <div className="mt-2 grid max-w-2xl grid-cols-2 gap-3 sm:grid-cols-4">
                  <ScoreBar label="Interview" value={a.scores.interview_avg} />
                  <ScoreBar label="English" value={a.scores.english_avg} />
                  <ScoreBar label="Assessments" value={a.scores.assessment_avg} />
                  <ScoreBar label="Resume" value={a.scores.resume_score} />
                </div>
                {a.cover_letter && <p className="mt-2 whitespace-pre-line text-sm italic text-slate-600">“{a.cover_letter}”</p>}
                <MatchPanel match={a.match} />
              </div>
              <div className="flex flex-col gap-2">
                <Button size="sm" variant="secondary" loading={busy === a.id} onClick={() => runMatch(a.id)}><Sparkles size={14} /> {["ai", "semantic+ai"].includes(a.match?.method) ? "Re-run AI match" : "AI match"}</Button>
                {a.status !== "withdrawn" && <Button size="sm" onClick={() => setStatusModal({ app: a, status: a.status, note: "", interview_at: "" })}>Update status</Button>}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Modal open={!!statusModal} onClose={() => setStatusModal(null)} title={`Update status · ${statusModal?.app.student.full_name}`}
        footer={<><Button variant="secondary" onClick={() => setStatusModal(null)}>Cancel</Button><Button loading={busy === "status"} onClick={saveStatus}>Save & notify candidate</Button></>}>
        {statusModal && (
          <div className="space-y-4">
            <Field label="New status">
              <select className="input" value={statusModal.status} onChange={(e) => setStatusModal({ ...statusModal, status: e.target.value })}>
                {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
              </select>
            </Field>
            {statusModal.status === "interview_scheduled" && (
              <Field label="Interview date & time"><input className="input" type="datetime-local" value={statusModal.interview_at} onChange={(e) => setStatusModal({ ...statusModal, interview_at: e.target.value })} /></Field>
            )}
            <Field label="Note (visible in status history)"><textarea className="input" rows={3} value={statusModal.note} onChange={(e) => setStatusModal({ ...statusModal, note: e.target.value })} /></Field>
          </div>
        )}
      </Modal>

      <Modal open={!!compare} onClose={() => setCompare(null)} title="Candidate comparison" wide>
        {compare && (
          <div className="space-y-3">
            <p className="text-xs text-slate-500">{compare.note}</p>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <tbody className="divide-y divide-slate-100">
                  {[["Candidate", "name"], ["Status", "status"], ["Match score", "match_score"], ["Method", "match_method"], ["Recommendation", "recommendation"],
                    ["Required skills covered", "required_skills_covered"], ["CGPA", "cgpa"], ["Interview avg", "interview_avg"], ["Interview best", "interview_best"],
                    ["Technical avg", "technical_avg"], ["English avg", "english_avg"], ["Assessment avg", "assessment_avg"], ["Resume completeness", "resume_score"]].map(([label, key]) => (
                    <tr key={key}><th className="th whitespace-nowrap">{label}</th>{compare.candidates.map((c) => <td key={c.application_id} className="td font-medium">{c[key] ?? "—"}</td>)}</tr>
                  ))}
                  <tr><th className="th">Missing skills</th>{compare.candidates.map((c) => <td key={c.application_id} className="td text-xs">{c.missing_skills.join(", ") || "—"}</td>)}</tr>
                  <tr><th className="th">Why</th>{compare.candidates.map((c) => <td key={c.application_id} className="td text-xs">{c.explanation || "Run an AI match for an explanation"}</td>)}</tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
