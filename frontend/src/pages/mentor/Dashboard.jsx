/* Mentor home: assigned students, who is struggling, upcoming sessions (GET /mentor/dashboard). */

import { Link } from "react-router-dom";
import { CalendarClock, CheckCircle2, GraduationCap, TrendingDown, TrendingUp } from "lucide-react";
import { get } from "../../api";
import { MultiBar } from "../../components/charts";
import { Card, EmptyState, ErrorBox, PageHeader, Pill, Spinner, StatCard, StatusPill, fmtDateTime, useApi } from "../../components/ui";

export default function MentorDashboard() {
  const { data, error, loading, reload } = useApi(() => get("/mentor/dashboard"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-6">
      <PageHeader title="Mentor dashboard" subtitle="Your students' progress, weaknesses and follow-ups." />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Assigned students" value={data.assigned_students} icon={GraduationCap} />
        <StatCard label="Improving" value={data.trends.improving} icon={TrendingUp} tone="green" hint={`${data.trends.stable} stable`} />
        <StatCard label="Struggling" value={data.trends.struggling} icon={TrendingDown} tone="red" hint={`${data.trends.no_data} with no activity yet`} />
        <StatCard label="Meeting all goals" value={data.students_meeting_goals} icon={CheckCircle2} tone="amber" hint={`${data.goals.completed}/${data.goals.total} goals done · ${data.goals.overdue} overdue`} />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Sessions completed" value={data.sessions.completed} icon={CalendarClock} tone="sky" />
        <StatCard label="Upcoming sessions" value={data.sessions.upcoming} icon={CalendarClock} tone="violet" />
        <StatCard label="Pending follow-ups" value={data.sessions.pending_follow_ups} icon={CalendarClock} tone="red" hint="Past sessions not yet marked completed" />
      </div>
      <Card title="Comparative progress">
        <MultiBar data={data.comparison.map((c) => ({ ...c, interview_avg: c.interview_avg || 0, english_avg: c.english_avg || 0, assessment_avg: c.assessment_avg || 0 }))}
          nameKey="name" max={100} keys={[{ key: "interview_avg", label: "Interview" }, { key: "english_avg", label: "English" }, { key: "assessment_avg", label: "Assessments" }]} />
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Needs attention">
          {data.needs_attention.length === 0 ? <EmptyState title="Everyone is on track" /> : (
            <ul className="divide-y divide-slate-100">
              {data.needs_attention.map((s) => (
                <li key={s.id} className="py-3">
                  <div className="flex items-center justify-between">
                    <Link className="font-medium text-brand-700 hover:underline" to={`/mentor/students/${s.id}`}>{s.full_name}</Link>
                    <StatusPill status={s.trend} />
                  </div>
                  <p className="text-xs text-slate-500">Interview avg {s.interview_avg ?? "—"}</p>
                  <div className="mt-1 flex flex-wrap gap-1">{s.weak_areas.map((w) => <Pill key={w} tone="red">{w}</Pill>)}</div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Upcoming sessions" actions={<Link className="text-sm text-brand-600 hover:underline" to="/mentor/sessions">Manage</Link>}>
          {data.upcoming_sessions.length === 0 ? <EmptyState title="No upcoming sessions" /> : (
            <ul className="divide-y divide-slate-100">
              {data.upcoming_sessions.map((s) => (
                <li key={s.id} className="py-3 text-sm"><p className="font-medium">{s.student_name} · {fmtDateTime(s.scheduled_at)}</p><p className="text-slate-600">{s.agenda}</p></li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
