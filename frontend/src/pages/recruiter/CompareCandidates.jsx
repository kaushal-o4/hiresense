/*
 * Side-by-side comparison of 2-4 applicants to one job (POST /recruiter/jobs/:id/compare).
 * URL: /recruiter/jobs/:id/compare?ids=12,15 - shareable and printable. Advisory only; integrity is shown apart.
 */

import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, FileText, Printer } from "lucide-react";
import { post } from "../../api";
import {
  Button, Card, ErrorBox, Notice, PageHeader, Pill, ScoreBar, Spinner, StatusPill, fmtDate, useApi,
} from "../../components/ui";
import IntegrityOverview from "./IntegrityOverview";
import { MATCH_METHOD } from "./JobDetail";

const REC_TONE = { strong_fit: "green", potential_fit: "amber", not_a_fit: "red" };

const SCORE_ROWS = [
  ["Job match", "match_score"],
  ["Interview average", "interview_avg"],
  ["Interview best", "interview_best"],
  ["Technical interviews", "technical_avg"],
  ["English", "english_avg"],
  ["Assessments", "assessment_avg"],
  ["Resume", "resume_score"],
  ["Readiness", "readiness"],
];

export function parseIds(raw) {
  return [...new Set(String(raw || "").split(",").map((x) => parseInt(x, 10)).filter((n) => Number.isInteger(n) && n > 0))].slice(0, 4);
}

/** Index of the highest value in a row, or -1 when there is no clear leader (missing values or a tie). */
export function leaderIndex(values) {
  const nums = values.map((v) => (typeof v === "number" ? v : null));
  const present = nums.filter((v) => v != null);
  if (present.length < 2) return -1;
  const max = Math.max(...present);
  return nums.filter((v) => v === max).length === 1 ? nums.indexOf(max) : -1;
}

function Row({ label, children, cols }) {
  return (
    <div className="grid gap-3 border-t border-slate-200/70 py-3 first:border-t-0 print:break-inside-avoid"
      style={{ gridTemplateColumns: `minmax(8rem, 10rem) repeat(${cols}, minmax(12rem, 1fr))` }}>
      <div className="eyebrow pt-0.5">{label}</div>
      {children}
    </div>
  );
}

export default function CompareCandidates() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const ids = parseIds(params.get("ids"));
  const { data, error, loading, reload } = useApi(
    () => (ids.length >= 2 ? post(`/recruiter/jobs/${id}/compare`, { application_ids: ids }) : Promise.resolve(null)),
    [id, ids.join(",")],
  );

  const back = <Link to={`/recruiter/jobs/${id}`} className="print:hidden"><Button variant="secondary"><ArrowLeft size={16} /> Back to applicants</Button></Link>;

  if (ids.length < 2) {
    return (
      <div>
        <PageHeader title="Compare candidates" actions={back} />
        <Notice>Pick 2-4 applicants on the job page, then choose Compare.</Notice>
      </div>
    );
  }
  if (loading && !data) return <Spinner />;
  if (error) return <div className="space-y-4">{back}<ErrorBox message={error} onRetry={reload} /></div>;

  const cs = data.candidates;
  const cols = cs.length;
  const cells = (render) => cs.map((c, i) => <div key={c.application_id} className="min-w-0 text-sm">{render(c, i)}</div>);

  return (
    <div className="space-y-6">
      <PageHeader title="Compare candidates" subtitle={`${data.job.title} · ${cols} applicants`}
        actions={<>{back}<Button variant="secondary" className="print:hidden" onClick={() => window.print()}><Printer size={16} /> Print / save as PDF</Button></>} />
      <Notice tone="blue">{data.note}</Notice>

      <Card bodyClass="overflow-x-auto px-5 py-2">
        <div className="min-w-max sm:min-w-0">
          <Row label="Candidate" cols={cols}>
            {cells((c) => (
              <div className="space-y-1">
                <p className="font-semibold text-slate-900">{c.name}</p>
                <StatusPill status={c.status} />
                <p className="text-xs text-slate-500">{c.college || "—"} · {c.branch || "—"}</p>
                <p className="text-xs text-slate-500">CGPA {c.cgpa ?? "—"} · {c.graduation_year || "—"} · applied {fmtDate(c.applied_at)}</p>
                <div className="flex flex-wrap gap-2 pt-1 print:hidden">
                  <Link className="text-xs font-medium text-brand-700 hover:underline" to={`/recruiter/applications/${c.application_id}/report`}><FileText size={12} className="mr-1 inline" />Report</Link>
                  <Link className="text-xs font-medium text-brand-700 hover:underline" to={`/recruiter/candidates/${c.student_id}`}>Profile</Link>
                </div>
              </div>
            ))}
          </Row>

          {SCORE_ROWS.map(([label, key]) => {
            const lead = leaderIndex(cs.map((c) => c[key]));
            return (
              <Row key={key} label={label} cols={cols}>
                {cells((c, i) => (
                  <div className={`rounded-lg p-1.5 ${i === lead ? "bg-brand-500/10 ring-1 ring-inset ring-brand-400/40" : ""}`}>
                    <ScoreBar label={i === lead ? "Highest" : " "} value={c[key]} />
                  </div>
                ))}
              </Row>
            );
          })}

          <Row label="Match" cols={cols}>
            {cells((c) => (
              <div className="flex flex-wrap gap-1">
                {c.recommendation && <Pill tone={REC_TONE[c.recommendation]}>{c.recommendation.replace(/_/g, " ")}</Pill>}
                {c.match_method && <Pill tone={(MATCH_METHOD[c.match_method] || {}).tone || "gray"}>{c.match_method}</Pill>}
                <Pill>required {c.required_skills_covered}</Pill>
                {c.match_score == null && <span className="text-xs text-slate-500">Not matched yet</span>}
              </div>
            ))}
          </Row>

          <Row label="Match breakdown" cols={cols}>
            {cells((c) => {
              const b = c.match_breakdown || {};
              return (
                <div className="space-y-2">
                  {(b.criteria_scores || []).map((x) => <ScoreBar key={x.criterion} label={x.criterion} value={x.score} />)}
                  {!b.criteria_scores?.length && <span className="text-xs text-slate-500">—</span>}
                  {b.eligible === false && <p className="text-xs text-amber-700">Not eligible: {(b.eligibility_issues || []).join("; ")}</p>}
                </div>
              );
            })}
          </Row>

          <Row label="Skills" cols={cols}>
            {cells((c) => {
              const b = c.match_breakdown || {};
              return (
                <div className="flex flex-wrap gap-1">
                  {(b.matched_skills || []).map((s) => <Pill key={s} tone="green">{s}</Pill>)}
                  {(b.partially_matched_skills || []).map((p) => <Pill key={p.skill} tone="amber">{p.skill} ≈ {p.closest}</Pill>)}
                  {(b.missing_required_skills || []).map((s) => <Pill key={s} tone="red">{s}</Pill>)}
                  {(b.missing_preferred_skills || []).map((s) => <Pill key={s}>{s}</Pill>)}
                </div>
              );
            })}
          </Row>

          <Row label="Interviews" cols={cols}>
            {cells((c) => (
              <div className="space-y-2">
                <p className="text-xs text-slate-500">{c.interview_count || 0} completed</p>
                {Object.entries(c.interviews_by_category || {}).map(([k, v]) => <ScoreBar key={k} label={k} value={v} />)}
                <ul className="space-y-1 text-xs text-slate-600">
                  {(c.recent_interviews || []).map((iv) => (
                    <li key={iv.id} className="flex justify-between gap-2"><span className="truncate">{iv.job_role} · {iv.category}</span><span className="num font-medium text-slate-800">{iv.score ?? "—"}</span></li>
                  ))}
                </ul>
              </div>
            ))}
          </Row>

          <Row label="Assessments for this job" cols={cols}>
            {cells((c) => (
              c.job_assessments?.length ? (
                <ul className="space-y-1 text-xs">
                  {c.job_assessments.map((a) => (
                    <li key={a.id} className="flex flex-wrap items-center justify-between gap-2">
                      <span className="truncate text-slate-700">{a.title}</span>
                      <span className="flex items-center gap-1.5">{a.score != null && <span className="num font-medium text-slate-800">{a.score}%</span>}
                        {a.passed != null ? <Pill tone={a.passed ? "green" : "red"}>{a.passed ? "passed" : "not passed"}</Pill> : <StatusPill status={a.status} />}</span>
                    </li>
                  ))}
                </ul>
              ) : <span className="text-xs text-slate-500">None assigned · {c.assessments_taken || 0} taken overall</span>
            ))}
          </Row>

          <Row label="Strengths / concerns" cols={cols}>
            {cells((c) => (
              <div className="space-y-1 text-xs">
                {(c.strengths || []).map((s, i) => <p key={`s${i}`} className="text-emerald-700">+ {s}</p>)}
                {(c.concerns || []).map((s, i) => <p key={`c${i}`} className="text-amber-700">− {s}</p>)}
                {!c.strengths?.length && !c.concerns?.length && <span className="text-slate-500">Run an AI match for strengths and concerns</span>}
              </div>
            ))}
          </Row>
        </div>
      </Card>

      <Card title="Integrity signals (separate from performance)" bodyClass="overflow-x-auto px-5 py-2">
        <div className="min-w-max sm:min-w-0">
          <Row label="Monitoring" cols={cols}>{cells((c) => <IntegrityOverview data={c.integrity} compact />)}</Row>
        </div>
      </Card>
    </div>
  );
}
