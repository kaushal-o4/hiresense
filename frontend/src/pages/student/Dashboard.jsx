import { useState } from "react";
import { Link } from "react-router-dom";
import { Award, Briefcase, CalendarClock, Flame, MessagesSquare, Mic, Sparkles, Target, TrendingUp } from "lucide-react";
import { get, post } from "../../api";
import { useAuth } from "../../auth";
import { ProgressChart } from "../../components/charts";
import { ReadinessCard } from "../../components/Readiness";
import {
  Button, Card, EmptyState, ErrorBox, PageHeader, Pill, ScoreBar, Spinner, StatCard, StatusPill, fmtDate,
  fmtDateTime, useApi, useToast,
} from "../../components/ui";

function RoleRecommendations() {
  const toast = useToast();
  const [rec, setRec] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    try { setRec(await post("/student/role-recommendations")); } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  return (
    <Card title="Job roles that suit you" actions={<Button size="sm" variant="secondary" onClick={load} loading={busy}><Sparkles size={14} /> {rec ? "Refresh" : "Suggest roles"}</Button>}>
      {!rec ? <p className="text-sm text-slate-500">AI suggests suitable job roles based on your skills, projects, scores and career interests.</p> : (
        <>
          <p className="mb-3 text-sm">{rec.summary}</p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {rec.roles.map((r) => (
              <div key={r.role} className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between"><p className="font-medium">{r.role}</p><span className="text-sm font-semibold text-brand-700">{r.fit_score}%</span></div>
                <ul className="mt-1 list-disc pl-4 text-xs text-slate-600">{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>
                {r.skills_to_learn.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{r.skills_to_learn.map((x) => <Pill key={x} tone="amber">{x}</Pill>)}</div>}
                {r.open_jobs.length > 0 && <p className="mt-2 text-xs">Open now: {r.open_jobs.map((j) => <Link key={j.id} className="text-brand-600 hover:underline" to="/student/jobs">{j.title} ({j.company_name}) </Link>)}</p>}
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

export default function StudentDashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi(() => get("/student/dashboard"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.summary;
  const upcomingCount = data.upcoming.mentor_sessions.length + data.upcoming.job_interviews.length + data.upcoming.goals.length;

  return (
    <div className="space-y-6">
      <PageHeader title={`Hi ${user.full_name.split(" ")[0]} 👋`} subtitle="Here's your placement readiness at a glance."
        actions={<>
          <Link to="/student/interviews"><Button><Mic size={16} /> Start mock interview</Button></Link>
          <Link to="/student/english"><Button variant="secondary"><MessagesSquare size={16} /> Practise English</Button></Link>
        </>} />

      {data.profile_completeness < 100 && (
        <div className="card flex flex-wrap items-center gap-4 p-4">
          <div className="min-w-[12rem] flex-1">
            <p className="text-sm font-medium">Profile {data.profile_completeness}% complete</p>
            <ScoreBar value={data.profile_completeness} />
          </div>
          <Link to={s.resume ? "/profile" : "/student/resume"}><Button variant="secondary" size="sm">{s.resume ? "Complete profile" : "Upload resume"}</Button></Link>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Reward points" value={s.rewards.points} icon={Award} tone="amber" hint={`${s.rewards.badges} badges earned`} />
        <StatCard label="Avg interview score" value={s.interviews.average_score ?? "—"} icon={TrendingUp} hint={`${s.interviews.completed} interviews completed`} />
        <StatCard label="English practice" value={`${s.english.minutes} min`} icon={MessagesSquare} tone="sky" hint={`${s.english.sessions} sessions`} />
        <StatCard label="Practice streak" value={`${s.rewards.current_streak} day${s.rewards.current_streak === 1 ? "" : "s"}`} icon={Flame} tone="red" hint={`Longest: ${s.rewards.longest_streak}`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <ReadinessCard readiness={s.readiness} className="lg:col-span-2" />
        <Card title="Today's challenges" actions={<Link className="text-sm text-brand-600 hover:underline" to="/student/rewards">All</Link>}>
          {data.challenges.length === 0 ? <p className="text-sm text-slate-500">No active challenges.</p> : (
            <ul className="space-y-3">
              {data.challenges.slice(0, 4).map((c) => (
                <li key={c.id}>
                  <div className="flex items-center justify-between text-sm">
                    <span className={c.completed ? "text-emerald-700" : ""}>{c.completed ? "✅" : "🔥"} {c.title}</span>
                    <Pill tone={c.period === "daily" ? "amber" : "violet"}>{c.period}</Pill>
                  </div>
                  <div className="mt-1"><ScoreBar value={c.percent} /></div>
                  <p className="text-[11px] text-slate-500">{c.progress}/{c.target} · +{c.points} pts</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <RoleRecommendations />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Learning progress" className="lg:col-span-2" actions={<Link className="text-sm text-brand-600 hover:underline" to="/student/progress">Details</Link>}>
          <ProgressChart series={data.progress} />
        </Card>
        <Card title="Upcoming">
          {upcomingCount === 0 ? <EmptyState icon={CalendarClock} title="Nothing scheduled" message="Mentor sessions, job interviews and goals will appear here." /> : (
            <ul className="space-y-3 text-sm">
              {data.upcoming.job_interviews.map((i) => (
                <li key={`j${i.application_id}`} className="flex gap-2"><Briefcase size={16} className="mt-0.5 text-amber-600" />
                  <div><p className="font-medium">{i.job_title} interview</p><p className="text-xs text-slate-500">{i.company} · {fmtDateTime(i.interview_at)}</p></div></li>
              ))}
              {data.upcoming.mentor_sessions.map((m) => (
                <li key={`m${m.id}`} className="flex gap-2"><CalendarClock size={16} className="mt-0.5 text-brand-600" />
                  <div><p className="font-medium">Mentor session with {m.mentor_name}</p><p className="text-xs text-slate-500">{fmtDateTime(m.scheduled_at)}</p></div></li>
              ))}
              {data.upcoming.goals.map((g) => (
                <li key={`g${g.id}`} className="flex gap-2"><Target size={16} className="mt-0.5 text-emerald-600" />
                  <div><p className="font-medium">{g.title}</p><p className="text-xs text-slate-500">{g.deadline ? `Due ${fmtDate(g.deadline)}` : "No deadline"}</p></div></li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Areas to improve">
          {s.weak_areas.length === 0 ? <p className="text-sm text-slate-500">No weak areas detected yet. Keep practising to get personalised insights.</p> : (
            <ul className="space-y-2">{s.weak_areas.slice(0, 6).map((w) => <li key={w} className="text-sm">• {w}</li>)}</ul>
          )}
          {s.remedies.length > 0 && (
            <div className="mt-3 space-y-1 border-t border-slate-100 pt-3">
              <p className="text-xs font-semibold uppercase text-slate-500">Suggested next steps</p>
              {s.remedies.slice(0, 3).map((r) => <p key={r.weakness} className="text-sm">→ {r.remedy}</p>)}
            </div>
          )}
          <Link to="/student/progress" className="mt-4 inline-block text-sm text-brand-600 hover:underline">Get AI recommendations →</Link>
        </Card>
        <Card title="Recent achievements" actions={<Link className="text-sm text-brand-600 hover:underline" to="/student/rewards">All rewards</Link>}>
          {data.recent_badges.length === 0 ? <p className="text-sm text-slate-500">Complete your first mock interview to earn the <b>First Interview</b> badge.</p> : (
            <ul className="grid grid-cols-2 gap-3">
              {data.recent_badges.map((b) => (
                <li key={b.name} className="rounded-lg bg-amber-50 p-3 text-center">
                  <div className="text-2xl">{b.icon}</div><p className="text-xs font-semibold">{b.name}</p><p className="text-[11px] text-slate-500">{fmtDate(b.awarded_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="My applications" actions={<Link className="text-sm text-brand-600 hover:underline" to="/student/jobs">Browse jobs</Link>}>
          {data.recent_applications.length === 0 ? <p className="text-sm text-slate-500">You haven't applied to any jobs yet.</p> : (
            <ul className="divide-y divide-slate-100">
              {data.recent_applications.map((a) => (
                <li key={a.id} className="flex items-center justify-between py-2">
                  <div className="min-w-0"><p className="truncate text-sm font-medium">{a.job?.title}</p><p className="text-xs text-slate-500">{a.job?.company_name}</p></div>
                  <StatusPill status={a.status} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {s.interviews.recent.length > 0 && (
        <Card title="Recent interviews">
          <div className="flex flex-wrap gap-2">
            {s.interviews.recent.slice().reverse().map((i) => (
              <Link key={i.id} to={`/student/interviews/${i.id}`} className="rounded-lg border border-slate-200 px-3 py-2 text-sm hover:border-brand-300">
                <span className="font-medium">{i.job_role}</span> <Pill tone="brand">{i.category}</Pill>
                <span className="ml-2 font-semibold">{i.score ?? "—"}</span>
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
