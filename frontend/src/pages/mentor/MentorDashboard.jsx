// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/mentor/MentorDashboard.jsx
//
// FILE PURPOSE:
// Mentor home page.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /mentor/dashboard.
// 2. Shows assigned students, who is struggling and upcoming sessions.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: GET /mentor/dashboard.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: MentorDashboard
//
// INPUT:
// Dashboard data.
//
// OUTPUT:
// Stats, charts and lists.
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
 * Mentor home: assigned students with readiness and activity, who needs attention, suggested interventions,
 * comparative scores, upcoming sessions and goal deadlines (GET /mentor/dashboard).
 */

import { Link } from "react-router-dom";
import { AlertTriangle, CalendarClock, CheckCircle2, ClipboardList, GraduationCap, Lightbulb, TrendingUp, Users } from "lucide-react";
import { get } from "../../apiClient";
import { MultiBar } from "../../components/DashboardCharts";
import { CardLink, LinkRow, PersonAvatar, scoreTone } from "../../components/DashboardWidgets";
import {
  Card, EmptyState, ErrorBox, PageHeader, PageSkeleton, Pill, StatCard, StatusPill, buttonClass, fmtDate, fmtDateTime, useApi,
} from "../../components/SharedUiComponents";

const LEVEL = { ready: ["green", "Ready"], almost: ["amber", "Almost"], not_ready: ["red", "Preparing"] };

function Readiness({ value, level }) {
  const tone = { green: "bg-emerald-500", amber: "bg-amber-500", red: "bg-rose-500" }[LEVEL[level]?.[0] || "red"];
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.min(100, value || 0)}%` }} /></div>
      <span className="num w-8 text-sm font-semibold text-slate-900">{Math.round(value || 0)}</span>
    </div>
  );
}

export default function MentorDashboard() {
  const { data, error, loading, reload } = useApi(() => get("/mentor/dashboard"));
  if (loading) return <PageSkeleton />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const c = data.cards || {};
  const rows = [...(data.student_rows || [])].sort((a, b) => (a.readiness ?? 0) - (b.readiness ?? 0));
  const attention = rows.filter((r) => ["struggling", "no_data"].includes(r.trend) || r.inactive);
  const hasScores = data.comparison.some((x) => x.interview_avg != null || x.english_avg != null || x.assessment_avg != null);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Mentor workspace" title="Student overview" subtitle="Progress, weak areas and follow-ups for the students assigned to you."
        actions={<>
          <Link to="/mentor/sessions" className={buttonClass("secondary")}><CalendarClock size={16} /> Sessions</Link>
          <Link to="/mentor/students" className={buttonClass("primary")}><GraduationCap size={16} /> My students</Link>
        </>} />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Assigned students" value={data.assigned_students} icon={Users} hint={`${c.placement_ready ?? 0} placement ready`} />
        <StatCard label="Improving" value={data.trends.improving} icon={TrendingUp} tone="green" hint={`${data.trends.stable} stable`} />
        <StatCard label="Need attention" value={c.need_attention ?? attention.length} icon={AlertTriangle} tone="red" hint={`${data.trends.struggling} struggling · ${data.trends.no_data} no activity`} />
        <StatCard label="Pending goals" value={c.tasks_pending ?? 0} icon={ClipboardList} tone="amber" hint={`${data.goals.completed}/${data.goals.total} done · ${data.goals.overdue} overdue`} />
      </div>

      <Card title="Assigned students" bodyClass="" actions={<CardLink to="/mentor/students">All students</CardLink>}>
        {rows.length === 0 ? <EmptyState icon={GraduationCap} title="No students assigned yet" message="The placement office assigns students to mentors." /> : (
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr><th className="th">Student</th><th className="th">Readiness</th><th className="th">Trend</th><th className="th text-right">Interview avg</th><th className="th text-right">English</th><th className="th text-right">Open goals</th><th className="th">Last practice</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r) => (
                  <tr key={r.id} className="transition-colors hover:bg-slate-50">
                    <td className="td"><Link to={`/mentor/students/${r.id}`} className="flex items-center gap-2.5 font-medium text-slate-900 hover:text-brand-600"><PersonAvatar name={r.full_name} size={28} />{r.full_name}</Link></td>
                    <td className="td"><Readiness value={r.readiness} level={r.readiness_level} /></td>
                    <td className="td"><StatusPill status={r.trend} /></td>
                    <td className={`td num text-right font-medium ${r.interview_avg == null ? "text-slate-400" : scoreTone(r.interview_avg) === "red" ? "text-rose-600" : "text-slate-900"}`}>{r.interview_avg ?? "—"}</td>
                    <td className="td num text-right">{r.english_minutes} min</td>
                    <td className="td num text-right">{r.pending_tasks}</td>
                    <td className="td whitespace-nowrap">{r.last_practice ? <span className={r.inactive ? "text-amber-700" : "text-slate-500"}>{fmtDate(r.last_practice)}</span> : <span className="text-slate-400">Never</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {rows.length > 0 && <>
      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="Needs attention" actions={attention.length > 0 && <Pill tone="red">{attention.length}</Pill>}>
          {attention.length === 0 ? <EmptyState icon={CheckCircle2} title="Everyone is on track" /> : (
            <div className="divide-y divide-slate-100">
              {attention.slice(0, 6).map((r) => (
                <LinkRow key={r.id} to={`/mentor/students/${r.id}`} icon={AlertTriangle} tone={r.trend === "struggling" ? "red" : "amber"} title={r.full_name}
                  meta={r.trend === "no_data" ? "No practice yet" : r.inactive ? `Inactive since ${r.last_practice ? fmtDate(r.last_practice) : "joining"}` : `Interview avg ${r.interview_avg ?? "—"}`} />
              ))}
            </div>
          )}
        </Card>
        <Card title="Suggested interventions" className="lg:col-span-2">
          {(data.recommendations || []).length === 0 ? <EmptyState icon={Lightbulb} title="No suggestions right now" message="Suggestions appear when a student's scores show a clear gap." /> : (
            <ul className="divide-y divide-slate-100">
              {data.recommendations.slice(0, 6).map((r, i) => (
                <li key={`${r.student_id}-${i}`} className="flex flex-wrap items-start gap-3 py-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><Lightbulb size={15} /></span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-slate-900">{r.weakness} <span className="font-normal text-slate-500">· {r.student_name}</span></p>
                    <p className="text-sm text-slate-600">{r.remedy}</p>
                  </div>
                  <Link to={`/mentor/students/${r.student_id}`} className={buttonClass("secondary", "sm")}>Open student</Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="Comparative progress" className="lg:col-span-2">
          {!hasScores ? <EmptyState title="No scores yet" message="Scores appear after your students complete interviews, English sessions or assessments." /> : (
            <MultiBar data={data.comparison.map((x) => ({ ...x, interview_avg: x.interview_avg || 0, english_avg: x.english_avg || 0, assessment_avg: x.assessment_avg || 0 }))}
              nameKey="name" max={100} keys={[{ key: "interview_avg", label: "Interview" }, { key: "english_avg", label: "English" }, { key: "assessment_avg", label: "Assessments" }]} />
          )}
        </Card>
        <div className="space-y-6">
          <Card title="Upcoming sessions" actions={<CardLink to="/mentor/sessions">Manage</CardLink>}>
            {data.upcoming_sessions.length === 0 ? <EmptyState icon={CalendarClock} title="No upcoming sessions" /> : (
              <div className="divide-y divide-slate-100">
                {data.upcoming_sessions.map((s) => <LinkRow key={s.id} to="/mentor/sessions" icon={CalendarClock} tone="brand" title={s.student_name} meta={`${fmtDateTime(s.scheduled_at)}${s.agenda ? ` · ${s.agenda}` : ""}`} />)}
              </div>
            )}
            {data.sessions.pending_follow_ups > 0 && (
              <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{data.sessions.pending_follow_ups} past session{data.sessions.pending_follow_ups === 1 ? "" : "s"} not yet marked completed.</p>
            )}
          </Card>
          <Card title="Goal deadlines">
            {(data.upcoming_tasks || []).length === 0 ? <EmptyState icon={ClipboardList} title="No goal deadlines" /> : (
              <div className="divide-y divide-slate-100">
                {data.upcoming_tasks.map((t) => (
                  <LinkRow key={t.id} to={`/mentor/students/${t.student_id}`} icon={ClipboardList} tone={t.overdue ? "red" : "gray"} title={t.title}
                    meta={`${t.student_name} · ${t.overdue ? "Overdue since" : "Due"} ${fmtDate(t.deadline)}`} />
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
      </>}
    </div>
  );
}
