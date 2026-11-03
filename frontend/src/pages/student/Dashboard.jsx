/*
 * Student home: summary stats, readiness score, today's challenges, progress, upcoming events,
 * weak areas, recent achievements, applications and interviews (GET /student/dashboard), plus on-demand AI job-role
 * suggestions (POST /student/role-recommendations).
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Award, Briefcase, CalendarClock, CheckCircle2, Circle, FileText, Flame, MessagesSquare, Mic, Sparkles, Target, TrendingUp } from "lucide-react";
import { get, post } from "../../api";
import { useAuth } from "../../auth";
import { ProgressChart } from "../../components/charts";
import InterviewerStage from "../../components/InterviewerStage";
import { ReadinessCard } from "../../components/Readiness";
import {
  Button, Card, EmptyState, ErrorBox, Pill, ScoreBar, Spinner, StatCard, StatusPill, fmtDate,
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
                <div className="flex items-center justify-between"><p className="font-medium">{r.role}</p><span className="num text-sm font-semibold text-slate-900">{r.fit_score}%</span></div>
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

const QUICK = [
  { to: "/student/interviews", title: "Mock interview", text: "Aria, Victor, Marcus or Elena", icon: Mic },
  { to: "/student/english", title: "English conversation", text: "Talk about anything you like", icon: MessagesSquare },
  { to: "/student/resume", title: "Resume analysis", text: "Strengths, gaps and fixes", icon: FileText },
  { to: "/student/jobs", title: "Jobs & drives", text: "Roles that match your profile", icon: Briefcase },
];

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};

export default function StudentDashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi(() => get("/student/dashboard"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.summary;
  const upcomingCount = data.upcoming.mentor_sessions.length + data.upcoming.job_interviews.length + data.upcoming.goals.length;

  return (
    <div className="space-y-6">
      <section className="card card-glow grid overflow-hidden lg:grid-cols-[1fr_400px]">
        <div className="flex flex-col justify-between gap-6 p-6 sm:p-8">
          <div>
            <p className="text-sm text-slate-500">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</p>
            <h1 className="text-gradient mt-1 text-[30px] font-semibold leading-tight tracking-tight sm:text-[34px]">{greeting()}, {user.full_name.split(" ")[0]}</h1>
            <p className="mt-2 max-w-md text-[15px] leading-relaxed text-slate-500">
              {s.interviews.completed
                ? `You've completed ${s.interviews.completed} mock interview${s.interviews.completed === 1 ? "" : "s"}. Keep the streak going with one more today.`
                : "Start with a short mock interview - it takes about 10 minutes and shows exactly where to improve."}
            </p>
          </div>
          {s.readiness && (
            <div className="flex items-center gap-5">
              <div>
                <p className="text-xs font-medium text-slate-500">Placement readiness</p>
                <p className="num mt-0.5 text-3xl font-semibold tracking-tight text-slate-900">{Math.round(s.readiness.score)}<span className="text-base font-normal text-slate-400">/100</span></p>
              </div>
              <div className="h-10 w-px bg-slate-200" />
              <div className="min-w-0 flex-1">
                <div className="h-1.5 max-w-xs overflow-hidden rounded-full bg-slate-100">
                  <div className={`h-full rounded-full ${s.readiness.score >= s.readiness.threshold ? "bg-emerald-500" : "bg-gradient-to-r from-brand-500 to-violet-500"}`} style={{ width: `${Math.min(100, s.readiness.score)}%` }} />
                </div>
                <p className="mt-1.5 text-xs text-slate-500">"Placement ready" from {s.readiness.threshold}</p>
              </div>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <Link to="/student/interviews"><Button size="lg"><Mic size={16} /> Start mock interview</Button></Link>
            <Link to="/student/english"><Button size="lg" variant="secondary"><MessagesSquare size={16} /> Practise English</Button></Link>
          </div>
        </div>
        <Link to="/student/interviews" className="group relative block min-h-[280px] bg-night-950 lg:min-h-0" aria-label="Start a mock interview with Aria">
          <InterviewerStage who="aria" className="absolute inset-0" />
          <div className="absolute inset-x-3 bottom-3 flex items-center justify-between gap-3 rounded-lg border border-snow/10 bg-black/45 px-3.5 py-2.5 text-snow backdrop-blur-md transition-colors group-hover:bg-black/60">
            <span className="min-w-0">
              <span className="block text-sm font-medium">Ready when you are</span>
              <span className="block truncate text-xs text-snow/60">Live voice interview · 4 interviewer styles</span>
            </span>
            <ArrowUpRight size={16} className="shrink-0 text-snow/70 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </div>
        </Link>
      </section>

      <div className="grid gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 shadow-soft sm:grid-cols-2 lg:grid-cols-4">
        {QUICK.map(({ to, title, text, icon: Icon }) => (
          <Link key={to} to={to} className="group flex items-center gap-3 bg-white px-4 py-3.5 transition-colors hover:bg-slate-50">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-50 text-slate-600 transition-colors group-hover:border-slate-300 group-hover:text-slate-900"><Icon size={17} /></span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium text-slate-900">{title}</span>
              <span className="block truncate text-xs text-slate-500">{text}</span>
            </span>
            <ArrowUpRight size={15} className="shrink-0 text-slate-600 transition-colors group-hover:text-slate-600" />
          </Link>
        ))}
      </div>

      {data.profile_completeness < 100 && (
        <div className="card flex flex-wrap items-center gap-4 p-4">
          <div className="min-w-[12rem] flex-1">
            <p className="text-sm font-medium">Profile {data.profile_completeness}% complete</p>
            <ScoreBar value={data.profile_completeness} />
          </div>
          <Link to={s.resume ? "/profile" : "/student/resume"}><Button variant="secondary" size="sm">{s.resume ? "Complete profile" : "Upload resume"}</Button></Link>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Reward points" value={s.rewards.points} icon={Award} tone="amber" hint={`${s.rewards.badges} badges earned`} />
        <StatCard label="Avg interview score" value={s.interviews.average_score ?? "—"} icon={TrendingUp} tone="violet" hint={`${s.interviews.completed} interviews completed`} />
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
                    <span className={`flex items-center gap-2 ${c.completed ? "text-slate-500 line-through decoration-slate-300" : "text-slate-800"}`}>
                      {c.completed ? <CheckCircle2 size={15} className="shrink-0 text-emerald-600" /> : <Circle size={15} className="shrink-0 text-slate-600" />} {c.title}
                    </span>
                    <Pill tone="gray">{c.period}</Pill>
                  </div>
                  <div className="mt-1"><ScoreBar value={c.percent} /></div>
                  <p className="num mt-1 text-[11px] text-slate-500">{c.progress}/{c.target} · +{c.points} pts</p>
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
            <ul className="space-y-2">{s.weak_areas.slice(0, 6).map((w) => <li key={w} className="flex gap-2 text-sm text-slate-700"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-slate-400" />{w}</li>)}</ul>
          )}
          {s.remedies.length > 0 && (
            <div className="mt-3 space-y-1 border-t border-slate-100 pt-3">
              <p className="eyebrow">Suggested next steps</p>
              {s.remedies.slice(0, 3).map((r) => <p key={r.weakness} className="text-sm text-slate-700">{r.remedy}</p>)}
            </div>
          )}
          <Link to="/student/progress" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700">Get AI recommendations <ArrowUpRight size={14} /></Link>
        </Card>
        <Card title="Recent achievements" actions={<Link className="text-sm text-brand-600 hover:underline" to="/student/rewards">All rewards</Link>}>
          {data.recent_badges.length === 0 ? <p className="text-sm text-slate-500">Complete your first mock interview to earn the <b>First Interview</b> badge.</p> : (
            <ul className="grid grid-cols-2 gap-3">
              {data.recent_badges.map((b) => (
                <li key={b.name} className="rounded-lg border border-slate-200 p-3 text-center">
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
              <Link key={i.id} to={`/student/interviews/${i.id}`} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm transition-colors hover:border-slate-300 hover:bg-slate-50">
                <span className="font-medium">{i.job_role}</span> <Pill tone="brand">{i.category}</Pill>
                <span className="num ml-1 font-semibold text-slate-900">{i.score ?? "—"}</span>
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
