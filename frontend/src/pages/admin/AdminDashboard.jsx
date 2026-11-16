// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/admin/AdminDashboard.jsx
//
// FILE PURPOSE:
// Admin analytics home page.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /admin/dashboard.
// 2. Shows platform counts (users, interviews, jobs...) and charts.
//
// HOW THIS FILE WORKS:
// A React page component. It loads its data with useApi()/get() from apiClient.js, keeps form and
// modal state with useState, sends changes with post/put/patch/del and shows the result with the
// shared components from SharedUiComponents.jsx. API calls used: GET /admin/dashboard.
//
// IMPORTANT FUNCTIONS:
//    Other helper functions: AdminDashboard
//
// INPUT:
// Dashboard data.
//
// OUTPUT:
// Stat cards and charts.
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
 * Admin home: platform overview (people, activity, placements), 30-day usage, placement funnel, readiness
 * distribution, branch scores, popular activities, AI service health and shortcuts to management pages
 * (GET /admin/dashboard).
 */

import { Link } from "react-router-dom";
import {
  Activity, Briefcase, CheckCircle2, ClipboardCheck, GraduationCap, MessagesSquare, ScrollText, ShieldAlert,
  Sparkles, UserCheck, UserPlus, Users,
} from "lucide-react";
import { get } from "../../apiClient";
import { SimpleBar, TimelineChart } from "../../components/DashboardCharts";
import { CardLink, LinkRow, Meter } from "../../components/DashboardWidgets";
import { Card, EmptyState, ErrorBox, Notice, PageHeader, PageSkeleton, Pill, StatCard, buttonClass, useApi } from "../../components/SharedUiComponents";

const FUNNEL = ["applied", "shortlisted", "interview_scheduled", "selected", "rejected"];
const label = (k) => { const s = k.replace(/_/g, " ").replace(/hr/gi, "HR"); return s.charAt(0).toUpperCase() + s.slice(1); };

function HealthRow({ name, ok, detail }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2.5">
      <span className="flex items-center gap-2.5 text-sm text-slate-700">
        <span className={`h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-amber-500"}`} aria-hidden />{name}
      </span>
      <span className={`text-sm font-medium ${ok ? "text-slate-900" : "text-amber-700"}`}>{detail}</span>
    </div>
  );
}

export default function AdminDashboard() {
  const { data, error, loading, reload } = useApi(() => get("/admin/dashboard"));
  if (loading) return <PageSkeleton />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const { users, activity, placements, ai } = data;
  const funnel = FUNNEL.map((k) => ({ name: label(k), count: placements.by_status[k] || 0 }));
  const readiness = data.readiness;
  const readyTotal = readiness ? Object.values(readiness.levels).reduce((a, b) => a + b, 0) : 0;
  const aiCalls = Object.entries(ai.last_24h || {});
  const aiTotal = aiCalls.reduce((n, [, v]) => n + v, 0);
  const aiOk = aiCalls.filter(([k]) => /ok|success/i.test(k)).reduce((n, [, v]) => n + v, 0);
  const placementRate = users.students ? Math.round((placements.selected / users.students) * 100) : null;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Administration" title="Platform overview" subtitle="Users, preparation activity, placements and system health across HireSense."
        actions={<>
          <Link to="/admin/reports" className={buttonClass("secondary")}><ScrollText size={16} /> Reports</Link>
          <Link to="/admin/users" className={buttonClass("primary")}><Users size={16} /> Manage users</Link>
        </>} />

      {!ai.available && <Notice>{ai.configured ? "AI is disabled in settings." : `The AI is not ready: ${ai.setup_hint || "check GEMINI_API_KEY or that Ollama is running"}`} Resume analysis, AI interview questions and English practice need it.</Notice>}
      {users.pending_approval > 0 && (
        <div className="card flex flex-wrap items-center gap-3 p-4">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><UserPlus size={17} /></span>
          <p className="flex-1 text-sm text-slate-700"><b className="font-semibold text-slate-900">{users.pending_approval} account{users.pending_approval === 1 ? "" : "s"}</b> awaiting approval.</p>
          <Link to="/admin/users?status=pending" className={buttonClass("secondary", "sm")}>Review</Link>
        </div>
      )}

      <section aria-labelledby="people">
        <h2 id="people" className="eyebrow mb-3">People</h2>
        <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
          <StatCard label="Students" value={users.students} icon={GraduationCap} hint={`${users.active_students_7d} active in last 7 days`} />
          <StatCard label="Recruiters" value={users.recruiters} icon={Briefcase} tone="sky" hint={`${users.pending_approval} pending approval`} />
          <StatCard label="Mentors" value={users.mentors} icon={UserCheck} tone="green" hint={`${users.admins} admin${users.admins === 1 ? "" : "s"}`} />
          <StatCard label="Flagged activity" value={data.flagged_items} icon={ShieldAlert} tone="red" hint={`${users.suspended} suspended account${users.suspended === 1 ? "" : "s"}`} />
        </div>
      </section>

      <section aria-labelledby="activity">
        <h2 id="activity" className="eyebrow mb-3">Preparation & placements</h2>
        <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
          <StatCard label="Mock interviews" value={activity.interviews_completed} icon={Activity} hint={`Average score ${activity.average_interview_score ?? "—"}`} />
          <StatCard label="English practice" value={`${activity.english_minutes} min`} icon={MessagesSquare} tone="sky" hint={`${activity.english_sessions} sessions`} />
          <StatCard label="Applications" value={placements.applications} icon={ClipboardCheck} tone="amber" hint={`${placements.jobs_published} open of ${placements.jobs_total} jobs`} />
          <StatCard label="Selections" value={placements.selected} icon={CheckCircle2} tone="green" hint={placementRate == null ? "No students yet" : `${placementRate}% of students`} />
        </div>
      </section>

      <Card title="Platform usage · last 30 days">
        <TimelineChart data={data.timeline} keys={[{ key: "interviews", label: "Interviews" }, { key: "english", label: "English sessions" }, { key: "applications", label: "Applications" }, { key: "signups", label: "Sign-ups" }]} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="Placement funnel" className="lg:col-span-2" actions={<CardLink to="/admin/jobs">Jobs & placements</CardLink>}>
          {placements.applications === 0 ? <EmptyState icon={Briefcase} title="No applications yet" /> : <SimpleBar data={funnel} dataKey="count" nameKey="name" />}
        </Card>
        <Card title="Student readiness">
          {!readiness || readyTotal === 0 ? <EmptyState icon={GraduationCap} title="No active students yet" /> : (
            <div className="space-y-3">
              <div className="flex items-baseline gap-2"><span className="num font-display text-3xl font-bold text-slate-950">{readiness.average ?? "—"}</span><span className="text-sm text-slate-500">average readiness</span></div>
              <Meter label="Placement ready" value={readiness.levels.ready} max={readyTotal} tone="green" suffix={` of ${readyTotal}`} />
              <Meter label="Almost ready" value={readiness.levels.almost} max={readyTotal} tone="amber" suffix={` of ${readyTotal}`} />
              <Meter label="Needs preparation" value={readiness.levels.not_ready} max={readyTotal} tone="red" suffix={` of ${readyTotal}`} />
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="Average interview score by branch" className="lg:col-span-2">
          <SimpleBar data={data.branch_scores} dataKey="avg_score" nameKey="branch" max={100} tone={1} />
        </Card>
        <Card title="Popular activities · 30 days">
          {(data.popular_activities || []).length === 0 ? <EmptyState icon={Activity} title="No activity yet" /> : (
            <ol className="space-y-2.5">
              {data.popular_activities.slice(0, 6).map((a, i) => (
                <li key={a.activity} className="flex items-center gap-3 text-sm">
                  <span className="num w-4 text-xs text-slate-400">{i + 1}</span>
                  <span className="flex-1 truncate text-slate-700">{label(a.activity)}</span>
                  <span className="num font-semibold text-slate-900">{a.count}</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="AI service health" className="lg:col-span-2" actions={<CardLink to="/admin/monitoring">Details</CardLink>}>
          <div className="divide-y divide-slate-100">
            <HealthRow name="Model" ok={ai.available} detail={<span className="flex items-center gap-1.5"><Sparkles size={14} className="text-slate-400" />{ai.model || "—"}</span>} />
            <HealthRow name="Status" ok={ai.available} detail={ai.available ? "Available" : "Unavailable"} />
            <HealthRow name="Calls in last 24 hours" ok detail={<span className="num">{aiTotal}</span>} />
            {aiTotal > 0 && <HealthRow name="Successful calls" ok={aiOk === aiTotal} detail={<span className="num">{aiOk} of {aiTotal}</span>} />}
          </div>
          {aiCalls.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{aiCalls.map(([k, v]) => <Pill key={k} tone={/ok|success/i.test(k) ? "green" : "amber"}>{label(k)} · {v}</Pill>)}</div>}
        </Card>
        <Card title="Administration">
          <div className="divide-y divide-slate-100">
            <LinkRow to="/admin/users" icon={Users} title="User management" meta="Students, recruiters, mentors, admins" />
            <LinkRow to="/admin/assignments" icon={GraduationCap} title="Mentor assignments" meta="Who mentors whom" />
            <LinkRow to="/admin/jobs" icon={Briefcase} title="Jobs & placements" meta="Postings and drives" />
            <LinkRow to="/admin/audit" icon={ScrollText} title="Audit logs" meta="Every administrative action" />
          </div>
        </Card>
      </div>
    </div>
  );
}
