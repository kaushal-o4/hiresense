// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/recruiter/RecruiterDashboard.jsx
//
// FILE PURPOSE:
// Recruiter home page.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /recruiter/dashboard.
// 2. Shows job and applicant counts and charts.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: GET /recruiter/dashboard.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: RecruiterDashboard
//
// INPUT:
// Dashboard data.
//
// OUTPUT:
// Stats and charts.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, components/DashboardCharts.jsx, components/SharedUiComponents.jsx
//    Used by: App.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Recruiter home: hiring stats, application pipeline, funnel per job, job listings, recent applications (searchable,
 * filterable by status) and upcoming interviews (GET /recruiter/dashboard).
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Briefcase, CalendarClock, CheckCircle2, Plus, Search, Users } from "lucide-react";
import { get } from "../../apiClient";
import { MultiBar } from "../../components/DashboardCharts";
import { CardLink, LinkRow, PersonAvatar, scoreTone } from "../../components/DashboardWidgets";
import {
  Card, EmptyState, ErrorBox, PageHeader, PageSkeleton, StatCard, StatusPill, buttonClass, fmtDate, fmtDateTime, useApi,
} from "../../components/SharedUiComponents";

const PIPELINE = [
  { key: "applied", label: "Applied" }, { key: "shortlisted", label: "Shortlisted" },
  { key: "interview_scheduled", label: "Interview" }, { key: "selected", label: "Selected" }, { key: "rejected", label: "Not selected" },
];
const STAGE_COLOR = { applied: "bg-sky-500", shortlisted: "bg-brand-500", interview_scheduled: "bg-amber-500", selected: "bg-emerald-500", rejected: "bg-slate-300" };

function Pipeline({ byStatus }) {
  const total = PIPELINE.reduce((n, p) => n + (byStatus[p.key] || 0), 0);
  if (!total) return <p className="flex items-center gap-2.5 text-sm text-slate-500"><Users size={16} className="text-slate-400" /> No applications yet. Stages fill in as candidates apply to your published jobs.</p>;
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-slate-100" aria-hidden>
        {PIPELINE.map((p) => byStatus[p.key] ? <div key={p.key} className={STAGE_COLOR[p.key]} style={{ width: `${(byStatus[p.key] / total) * 100}%` }} /> : null)}
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-5">
        {PIPELINE.map((p) => (
          <div key={p.key}>
            <dt className="flex items-center gap-1.5 text-xs text-slate-500"><span className={`h-2 w-2 rounded-full ${STAGE_COLOR[p.key]}`} />{p.label}</dt>
            <dd className="num mt-0.5 font-display text-xl font-bold text-slate-950">{byStatus[p.key] || 0}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const FILTERS = [{ value: "", label: "All" }, ...PIPELINE.map((p) => ({ value: p.key, label: p.label }))];

function RecentApplications({ rows }) {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const shown = useMemo(() => rows.filter((a) => (!status || a.status === status)
    && (!q || `${a.student?.full_name} ${a.job?.title} ${a.student?.branch || ""}`.toLowerCase().includes(q.toLowerCase()))), [rows, q, status]);
  return (
    <Card title="Recent applications" bodyClass="" actions={<CardLink to="/recruiter/jobs">All jobs</CardLink>}>
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 px-5 py-3">
        <label className="relative min-w-[12rem] flex-1">
          <span className="sr-only">Search recent applications</span>
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input className="input h-9 pl-9" placeholder="Search candidate, job or branch" value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
        <select className="input h-9 w-auto" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          {FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
        </select>
      </div>
      {shown.length === 0 ? <EmptyState icon={Users} title={rows.length ? "No applications match" : "No applications yet"} /> : (
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="border-b border-slate-200 bg-slate-50">
              <tr><th className="th">Candidate</th><th className="th">Job</th><th className="th">Applied</th><th className="th text-right">Match</th><th className="th">Status</th><th className="th"><span className="sr-only">Report</span></th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {shown.map((a) => (
                <tr key={a.id} className="transition-colors hover:bg-slate-50">
                  <td className="td">
                    <Link to={`/recruiter/candidates/${a.student_id}`} className="flex items-center gap-2.5 font-medium text-slate-900 hover:text-brand-600">
                      <PersonAvatar name={a.student?.full_name} size={28} />
                      <span className="min-w-0"><span className="block truncate">{a.student?.full_name}</span>
                        {a.student?.branch && <span className="block truncate text-xs font-normal text-slate-500">{a.student.branch}</span>}</span>
                    </Link>
                  </td>
                  <td className="td"><Link className="hover:text-brand-600" to={`/recruiter/jobs/${a.job_id}`}>{a.job?.title}</Link></td>
                  <td className="td whitespace-nowrap text-slate-500">{fmtDate(a.created_at)}</td>
                  <td className="td text-right">
                    <span className={`num font-semibold ${a.match?.score == null ? "text-slate-400" : scoreTone(a.match.score) === "green" ? "text-emerald-600" : scoreTone(a.match.score) === "amber" ? "text-amber-600" : "text-slate-600"}`}>{a.match?.score ?? "—"}</span>
                  </td>
                  <td className="td"><StatusPill status={a.status} /></td>
                  <td className="td text-right">{a.status !== "withdrawn" && <Link to={`/recruiter/applications/${a.id}/report`} className="text-xs font-medium text-brand-600 hover:underline">Report</Link>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function RecruiterDashboard() {
  const { data, error, loading, reload } = useApi(() => get("/recruiter/dashboard"));
  if (loading) return <PageSkeleton />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const bs = data.applications.by_status;
  const jobs = [...data.per_job].sort((a, b) => (a.status === "published" ? -1 : 1) - (b.status === "published" ? -1 : 1) || b.applications - a.applications);
  const chartJobs = data.per_job.filter((j) => j.applications > 0);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Recruitment workspace" title="Hiring overview" subtitle="Your openings, candidate pipeline and upcoming interviews."
        actions={<>
          <Link to="/recruiter/candidates" className={buttonClass("secondary")}><Search size={16} /> Find candidates</Link>
          <Link to="/recruiter/jobs?new=1" className={buttonClass("primary")}><Plus size={16} /> Post a job</Link>
        </>} />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Active jobs" value={data.jobs.published} icon={Briefcase} hint={`${data.jobs.draft} drafts · ${data.jobs.closed} closed`} />
        <StatCard label="Applications" value={data.applications.total} icon={Users} tone="sky" hint={`${bs.applied || 0} awaiting review`} />
        <StatCard label="In interview stage" value={(bs.shortlisted || 0) + (bs.interview_scheduled || 0)} icon={CalendarClock} tone="amber" hint={`${bs.interview_scheduled || 0} interviews scheduled`} />
        <StatCard label="Selected" value={bs.selected || 0} icon={CheckCircle2} tone="green" hint={`${bs.rejected || 0} not selected`} />
      </div>

      <Card title="Candidate pipeline"><Pipeline byStatus={bs} /></Card>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        {chartJobs.length > 0 && <Card title="Funnel by job" className="lg:col-span-2">
          {(
            <MultiBar data={chartJobs.map((j) => ({ ...j, name: j.title.length > 16 ? `${j.title.slice(0, 16)}…` : j.title }))} nameKey="name"
              keys={[{ key: "applications", label: "Applications" }, { key: "shortlisted", label: "Shortlisted" }, { key: "selected", label: "Selected" }]} />
          )}
        </Card>}
        <Card title="Job listings" className={chartJobs.length ? "" : "lg:col-span-3"} actions={<CardLink to="/recruiter/jobs">Manage</CardLink>}>
          {jobs.length === 0 ? (
            <EmptyState icon={Briefcase} title="No jobs yet" action={<Link to="/recruiter/jobs?new=1" className={buttonClass("secondary", "sm")}><Plus size={14} /> Post a job</Link>} />
          ) : (
            <div className="divide-y divide-slate-100">
              {jobs.slice(0, chartJobs.length ? 6 : 8).map((j) => (
                <LinkRow key={j.id} to={`/recruiter/jobs/${j.id}`} icon={Briefcase} tone={j.status === "published" ? "brand" : "gray"} title={j.title}
                  meta={`${j.applications} applicant${j.applications === 1 ? "" : "s"} · ${j.shortlisted} shortlisted`} right={<StatusPill status={j.status} />} />
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3 [&>*]:min-w-0">
        <div className="xl:col-span-2"><RecentApplications rows={data.recent_applications} /></div>
        <Card title="Upcoming interviews">
          {data.upcoming_interviews.length === 0 ? <EmptyState icon={CalendarClock} title="No interviews scheduled" message="Schedule interviews from a job's applicant list." /> : (
            <div className="divide-y divide-slate-100">
              {data.upcoming_interviews.map((a) => (
                <LinkRow key={a.id} to={`/recruiter/jobs/${a.job_id}`} icon={CalendarClock} tone="amber" title={a.student?.full_name} meta={`${a.job?.title} · ${fmtDateTime(a.interview_at)}`} />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
