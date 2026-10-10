import { Link } from "react-router-dom";
import { Activity, Briefcase, CheckCircle2, GraduationCap, ShieldAlert, Sparkles, UserCheck, Users } from "lucide-react";
import { get } from "../../api";
import { SimpleBar, TimelineChart } from "../../components/charts";
import { Card, ErrorBox, Notice, PageHeader, Spinner, StatCard, useApi } from "../../components/ui";

export default function AdminDashboard() {
  const { data, error, loading, reload } = useApi(() => get("/admin/dashboard"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const { users, activity, placements, ai } = data;
  const funnel = ["applied", "shortlisted", "interview_scheduled", "selected", "rejected"].map((k) => ({ name: k.replace(/_/g, " "), count: placements.by_status[k] || 0 }));

  return (
    <div className="space-y-6">
      <PageHeader title="Platform analytics" subtitle="Users, activity, placements and system health." />
      {!ai.available && <Notice>{ai.configured ? "AI is disabled in settings." : `The local AI is not ready: ${ai.setup_hint || "check that Ollama is running"}`} Resume analysis, AI interview questions and English practice need it (see README, section 2).</Notice>}
      {users.pending_approval > 0 && <Notice tone="blue"><Link className="font-medium underline" to="/admin/users?status=pending">{users.pending_approval} account(s) awaiting approval</Link></Notice>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Students" value={users.students} icon={GraduationCap} hint={`${users.active_students_7d} active in last 7 days`} />
        <StatCard label="Recruiters" value={users.recruiters} icon={Briefcase} tone="sky" />
        <StatCard label="Mentors" value={users.mentors} icon={UserCheck} tone="green" />
        <StatCard label="Flagged activity" value={data.flagged_items} icon={ShieldAlert} tone="red" hint="Awaiting review" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Mock interviews" value={activity.interviews_completed} icon={Activity} tone="violet" hint={`Avg score ${activity.average_interview_score ?? "—"}`} />
        <StatCard label="English practice" value={`${activity.english_minutes} min`} icon={Users} tone="sky" hint={`${activity.english_sessions} sessions`} />
        <StatCard label="Applications" value={placements.applications} icon={Briefcase} tone="amber" hint={`${placements.jobs_published} open jobs`} />
        <StatCard label="Selections" value={placements.selected} icon={CheckCircle2} tone="green" />
      </div>
      <Card title="Platform usage - last 30 days">
        <TimelineChart data={data.timeline} keys={[{ key: "interviews", label: "Interviews" }, { key: "english", label: "English sessions" }, { key: "applications", label: "Applications" }, { key: "signups", label: "Sign-ups" }]} />
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Placement funnel"><SimpleBar data={funnel} dataKey="count" nameKey="name" color="#f59e0b" /></Card>
        <Card title="Average interview score by branch"><SimpleBar data={data.branch_scores} dataKey="avg_score" nameKey="branch" max={100} color="#10b981" /></Card>
      </div>
      <Card title="AI service (last 24h)" actions={<Link className="text-sm text-brand-600 hover:underline" to="/admin/monitoring">Details</Link>}>
        <div className="flex flex-wrap gap-6 text-sm">
          <span className="flex items-center gap-2"><Sparkles size={16} /> Model: <b>{ai.model}</b></span>
          <span>Status: <b className={ai.available ? "text-emerald-700" : "text-amber-700"}>{ai.available ? "available" : "unavailable"}</b></span>
          {Object.entries(ai.last_24h).map(([k, v]) => <span key={k}>{k}: <b>{v}</b></span>)}
          {Object.keys(ai.last_24h).length === 0 && <span className="text-slate-500">No AI calls in the last 24 hours.</span>}
        </div>
      </Card>
    </div>
  );
}
