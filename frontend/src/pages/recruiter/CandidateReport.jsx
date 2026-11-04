/*
 * Printable candidate report for one application (GET /recruiter/applications/:id/report).
 * "Save as PDF" uses the browser print dialog; index.css switches to a light palette and hides the app chrome
 * when printing, so no PDF library is needed. Viewing it is audit-logged (candidate.report).
 */

import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Printer } from "lucide-react";
import { get } from "../../api";
import Logo from "../../components/Logo";
import {
  Button, Card, ErrorBox, Pill, ScoreBar, Spinner, StatusPill, fmtDate, fmtDateTime, useApi,
} from "../../components/ui";
import IntegrityOverview from "./IntegrityOverview";
import { MatchPanel } from "./JobDetail";

function Section({ title, children }) {
  return (
    <Card title={title} className="print:break-inside-avoid">
      {children}
    </Card>
  );
}

function KV({ label, value }) {
  return (
    <div>
      <p className="eyebrow">{label}</p>
      <p className="mt-0.5 text-sm text-slate-900">{value ?? "—"}</p>
    </div>
  );
}

export default function CandidateReport() {
  const { id } = useParams();
  const { data, error, loading, reload } = useApi(() => get(`/recruiter/applications/${id}/report`), [id]);
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const { candidate: c, job, profile, contact, resume } = data;
  const edu = profile.education || {};
  const scores = [["Job match", c.match_score], ["Interview avg", c.interview_avg], ["Interview best", c.interview_best],
    ["English", c.english_avg], ["Assessments", c.assessment_avg], ["Resume", c.resume_score], ["Readiness", c.readiness]];

  return (
    <article className="mx-auto max-w-4xl space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link to={`/recruiter/jobs/${job.id}`}><Button variant="secondary"><ArrowLeft size={16} /> Back to applicants</Button></Link>
        <Button onClick={() => window.print()}><Printer size={16} /> Print / save as PDF</Button>
      </div>

      <header className="card flex flex-wrap items-start justify-between gap-4 p-6">
        <div className="min-w-0">
          <p className="eyebrow">Candidate report · {job.title}{job.company_name ? ` · ${job.company_name}` : ""}</p>
          <h1 className="mt-1 text-[28px] font-semibold leading-tight">{c.name}</h1>
          <p className="mt-1 text-sm text-slate-600">{edu.college || "—"} · {edu.branch || "—"} · CGPA {edu.cgpa ?? "—"} · {edu.graduation_year || "—"}</p>
          <p className="mt-1 text-sm text-slate-600">{contact.email}{contact.linkedin_url ? ` · ${contact.linkedin_url}` : ""}{contact.github_url ? ` · ${contact.github_url}` : ""}</p>
        </div>
        <div className="flex flex-col items-end gap-2 text-right">
          <Logo size={22} />
          <StatusPill status={c.status} />
          <p className="text-xs text-slate-500">Applied {fmtDate(c.applied_at)}</p>
          {data.interview_at && <p className="text-xs text-slate-500">Interview {fmtDateTime(data.interview_at)}</p>}
          <p className="text-xs text-slate-500">Generated {fmtDateTime(data.generated_at)}</p>
        </div>
      </header>

      <Section title="Scores">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {scores.map(([label, v]) => <ScoreBar key={label} label={label} value={v} />)}
        </div>
      </Section>

      <Section title="Job match">
        {c.match_score == null ? <p className="text-sm text-slate-500">Not matched yet. Run a match on the applicants page.</p>
          : <MatchPanel match={{ ...c.match_breakdown, score: c.match_score, method: c.match_method, recommendation: c.recommendation,
            explanation: c.explanation, strengths: c.strengths, concerns: c.concerns }} />}
      </Section>

      <Section title="Skills, projects and experience">
        <div className="space-y-4">
          <div className="flex flex-wrap gap-1">{(profile.skills || []).map((s) => <Pill key={s}>{s}</Pill>)}{!profile.skills?.length && <span className="text-sm text-slate-500">No skills listed</span>}</div>
          {profile.projects?.length > 0 && (
            <div><p className="eyebrow mb-1.5">Projects</p>
              <ul className="space-y-2 text-sm">{profile.projects.map((p, i) => (
                <li key={i} className="print:break-inside-avoid"><span className="font-medium text-slate-900">{p.name}</span>{p.technologies?.length ? <span className="text-slate-500"> · {p.technologies.join(", ")}</span> : null}{p.description && <p className="text-slate-600">{p.description}</p>}</li>
              ))}</ul>
            </div>
          )}
          {profile.experience?.length > 0 && (
            <div><p className="eyebrow mb-1.5">Experience</p>
              <ul className="space-y-2 text-sm">{profile.experience.map((e, i) => (
                <li key={i} className="print:break-inside-avoid"><span className="font-medium text-slate-900">{e.role}</span>{e.organization && <span className="text-slate-500"> · {e.organization}</span>}{e.summary && <p className="text-slate-600">{e.summary}</p>}</li>
              ))}</ul>
            </div>
          )}
          {resume && (
            <div><p className="eyebrow mb-1.5">Resume ({resume.filename})</p>
              {resume.analysis_summary && <p className="text-sm text-slate-700">{resume.analysis_summary}</p>}
              {resume.strengths?.length > 0 && <p className="mt-1 text-xs text-slate-600"><b>Strengths:</b> {resume.strengths.join("; ")}</p>}
            </div>
          )}
        </div>
      </Section>

      <Section title="Interviews">
        <div className="grid gap-4 sm:grid-cols-3">
          <KV label="Completed" value={c.interview_count} />
          <KV label="Average" value={c.interview_avg} />
          <KV label="Best" value={c.interview_best} />
        </div>
        {Object.keys(c.interviews_by_category || {}).length > 0 && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">{Object.entries(c.interviews_by_category).map(([k, v]) => <ScoreBar key={k} label={k} value={v} />)}</div>
        )}
        {c.recent_interviews?.length > 0 && (
          <table className="mt-4 min-w-full text-sm">
            <thead><tr><th className="th pl-0">Role</th><th className="th">Type</th><th className="th">Level</th><th className="th">Score</th><th className="th">Date</th></tr></thead>
            <tbody className="divide-y divide-slate-100">{c.recent_interviews.map((iv) => (
              <tr key={iv.id}><td className="td pl-0">{iv.job_role}</td><td className="td">{iv.category}</td><td className="td">{iv.difficulty}</td><td className="td num font-medium">{iv.score ?? "—"}</td><td className="td">{fmtDate(iv.completed_at)}</td></tr>
            ))}</tbody>
          </table>
        )}
      </Section>

      <Section title="Assessments">
        <div className="grid gap-4 sm:grid-cols-3">
          <KV label="Taken" value={c.assessments_taken} />
          <KV label="Passed" value={c.assessments_passed} />
          <KV label="Average" value={c.assessment_avg != null ? `${c.assessment_avg}%` : null} />
        </div>
        {c.job_assessments?.length > 0 && (
          <ul className="mt-4 divide-y divide-slate-100 text-sm">{c.job_assessments.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2"><span>{a.title}</span>
              <span className="flex items-center gap-2">{a.score != null && <span className="num">{a.score}%</span>}{a.passed != null ? <Pill tone={a.passed ? "green" : "red"}>{a.passed ? "passed" : "not passed"}</Pill> : <StatusPill status={a.status} />}</span></li>
          ))}</ul>
        )}
      </Section>

      {(data.cover_letter || data.history?.length > 0) && (
        <Section title="Application">
          {data.cover_letter && <p className="whitespace-pre-line text-sm italic text-slate-600">“{data.cover_letter}”</p>}
          {data.history?.length > 0 && (
            <ol className="mt-3 space-y-1.5 text-sm">{data.history.map((h, i) => (
              <li key={i} className="flex flex-wrap gap-2"><span className="text-slate-500">{fmtDateTime(h.at)}</span><StatusPill status={h.to} />{h.note && <span className="text-slate-600">{h.note}</span>}</li>
            ))}</ol>
          )}
        </Section>
      )}

      <Section title="Integrity signals (separate from performance)">
        <IntegrityOverview data={c.integrity} />
      </Section>

      <p className="pb-6 text-xs leading-relaxed text-slate-500">{data.note}</p>
    </article>
  );
}
