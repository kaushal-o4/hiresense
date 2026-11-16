// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/student/StudentDashboard.jsx
//
// FILE PURPOSE:
// The student's home page.
//
// WHAT THIS FILE DOES:
// 1. Loads GET /student/dashboard: summary stats, readiness score, challenges, progress, upcoming
//    events, weak areas, achievements, applications and interviews.
// 2. Shows the placement readiness card, the English daily plan and a 3D interviewer hero.
// 3. On request, asks the AI for suitable job roles (POST /student/role-recommendations).
//
// HOW THIS FILE WORKS:
// A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with
// useState and sends changes with post/put/patch/del, then shows results with the shared UI
// components. API calls used: GET /student/dashboard, POST /student/role-recommendations.
//
// IMPORTANT FUNCTIONS:
//    - StudentDashboard()
//        Page component.
//    - RoleRecommendations()
//        Card that requests and shows AI job-role suggestions.
//    - greeting()
//        Good morning/afternoon/evening text.
//
// INPUT:
// Dashboard data from the backend.
//
// OUTPUT:
// The dashboard screen.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx, apiClient.js, components/DashboardCharts.jsx,
//    components/EnglishDailyPlan.jsx, components/InterviewerStage.jsx,
//    components/SharedUiComponents.jsx
//    Used by: App.jsx
//
// EXECUTION FLOW:
//    Page opens
//       |
//       v
//    GET /student/dashboard
//       |
//       v
//    Stats, readiness and charts shown
//       |
//       v
//    Optional: AI role suggestions
//
// IMPORTANT DEPENDENCIES:
//    lucide-react, react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Student home: welcome, headline stats, placement readiness, recommended next steps (derived from the backend's
 * weak areas / remedies / missing readiness parts), progress chart, live-interviewer entry, AI job-role suggestions,
 * applications, upcoming events, challenges and achievements (GET /student/dashboard; POST /student/role-recommendations).
 * Everything shown comes from the API; nothing is filled in with sample numbers.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight, Award, BarChart3, Briefcase, CalendarClock, CheckCircle2, Circle, ClipboardCheck, FileText, Flame,
  Gauge, MessagesSquare, Mic, Sparkles, Target, UserRound,
} from "lucide-react";
import { get, post } from "../../apiClient";
import { useAuth } from "../../AuthContext";
import { ProgressChart } from "../../components/DashboardCharts";
import { CardLink, LinkRow, Meter, scoreTone } from "../../components/DashboardWidgets";
import DailyPlan from "../../components/EnglishDailyPlan";
import InterviewerStage from "../../components/InterviewerStage";
import {
  Button, Card, EmptyState, ErrorBox, PageHeader, PageSkeleton, Pill, StatCard, StatusPill, buttonClass, fmtDate,
  fmtDateTime, useApi, useToast,
} from "../../components/SharedUiComponents";

// Where each kind of recommended step is practised (same mapping as the mentoring goals page).
const GOAL_LINKS = { mock_interview: "/student/interviews", english_practice: "/student/english", assessment: "/student/assessments", resume_update: "/student/resume" };
const GOAL_ICONS = { mock_interview: Mic, english_practice: MessagesSquare, assessment: ClipboardCheck, resume_update: FileText };
const MISSING_STEP = {
  interviews: { title: "Take your first mock interview", meta: "About 10 minutes with an AI interviewer", to: "/student/interviews", icon: Mic },
  assessments: { title: "Complete an assessment", meta: "Aptitude, technical or coding", to: "/student/assessments", icon: ClipboardCheck },
  english: { title: "Start an English conversation", meta: "Build spoken confidence", to: "/student/english", icon: MessagesSquare },
  resume: { title: "Upload your resume for analysis", meta: "Strengths, gaps and fixes", to: "/student/resume", icon: FileText },
};

function RoleRecommendations() {
  const toast = useToast();
  const [rec, setRec] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    try { setRec(await post("/student/role-recommendations")); } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  return (
    <Card title="Roles that suit you" actions={<Button size="sm" variant="secondary" onClick={load} loading={busy}><Sparkles size={14} /> {rec ? "Refresh" : "Suggest roles"}</Button>}>
      {!rec ? (
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Sparkles size={16} /></span>
          <p className="text-sm leading-relaxed text-slate-500">HireSense matches your skills, projects, scores and interests against job roles and links any openings that fit right now.</p>
        </div>
      ) : (
        <>
          {rec.summary && <p className="mb-4 text-sm leading-relaxed text-slate-600">{rec.summary}</p>}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {rec.roles.map((r) => (
              <div key={r.role} className="rounded-lg border border-slate-200 p-4">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-slate-900">{r.role}</p>
                  <span className={`num shrink-0 text-sm font-semibold ${scoreTone(r.fit_score) === "green" ? "text-emerald-600" : scoreTone(r.fit_score) === "amber" ? "text-amber-600" : "text-slate-600"}`}>{r.fit_score}% fit</span>
                </div>
                <ul className="mt-2 space-y-1 text-xs leading-relaxed text-slate-600">
                  {r.reasons.map((x, i) => <li key={i} className="flex gap-2"><span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-slate-400" />{x}</li>)}
                </ul>
                {r.skills_to_learn.length > 0 && <div className="mt-3 flex flex-wrap gap-1">{r.skills_to_learn.map((x) => <Pill key={x} tone="amber">{x}</Pill>)}</div>}
                {r.open_jobs.length > 0 && (
                  <div className="mt-3 border-t border-slate-100 pt-2">
                    <p className="eyebrow mb-1">Open now</p>
                    {r.open_jobs.map((j) => <Link key={j.id} className="block truncate text-xs font-medium text-brand-600 hover:underline" to="/student/jobs">{j.title} · {j.company_name}</Link>)}
                  </div>
                )}
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
  if (loading) return <PageSkeleton />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.summary;
  const first = (user.full_name || "").split(" ")[0];
  const upcomingCount = data.upcoming.mentor_sessions.length + data.upcoming.job_interviews.length + data.upcoming.goals.length;
  const sessions = s.interviews.completed + s.english.sessions + s.assessments.taken;
  const resume = s.resume;

  // Recommended next steps: backend remedies first (each maps to a practice area), then readiness parts not started.
  const steps = [];
  for (const r of s.remedies || []) {
    if (steps.length >= 4) break;
    steps.push({ key: r.weakness, title: r.goal?.title || r.remedy, meta: r.weakness, to: GOAL_LINKS[r.goal?.goal_type], icon: GOAL_ICONS[r.goal?.goal_type] || Target });
  }
  for (const k of s.readiness?.missing || []) {
    if (steps.length >= 4 || !MISSING_STEP[k] || steps.some((x) => x.to === MISSING_STEP[k].to)) continue;
    steps.push({ key: k, ...MISSING_STEP[k] });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}
        title={`Welcome back, ${first}`}
        subtitle="Let's take another step towards your career goals."
        actions={<>
          <Link to="/student/english" className={buttonClass("secondary")}><MessagesSquare size={16} /> Practise English</Link>
          <Link to="/student/interviews" className={buttonClass("primary")}><Mic size={16} /> Start mock interview</Link>
        </>} />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Practice streak" value={`${s.rewards.current_streak} day${s.rewards.current_streak === 1 ? "" : "s"}`} icon={Flame} tone="amber"
          hint={`Longest ${s.rewards.longest_streak} · ${s.rewards.points} points`} />
        <StatCard label="Resume score" value={resume?.resume_score ?? "—"} icon={FileText} tone="sky"
          hint={!resume ? "No resume uploaded" : resume.analysis_status === "completed" ? `Analysed ${fmtDate(resume.uploaded_at)}` : `Analysis ${String(resume.analysis_status || "pending").replace(/_/g, " ")}`} />
        <StatCard label="Practice sessions" value={sessions} icon={BarChart3} tone="green"
          hint={`${s.interviews.completed} interviews · ${s.english.sessions} English · ${s.assessments.taken} tests`} />
        <StatCard label="Interview readiness" value={s.readiness ? Math.round(s.readiness.score) : "—"} icon={Gauge}
          hint={s.readiness ? `Placement ready from ${s.readiness.threshold}` : "Not calculated yet"} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        {/* Practice section - shown first, in place of the placement-readiness card. */}
        <Card title="Practice" className="lg:col-span-2">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { to: "/student/interviews", label: "Mock interview", icon: Mic, count: s.interviews.completed, unit: "completed" },
              { to: "/student/english", label: "English practice", icon: MessagesSquare, count: s.english.sessions, unit: "sessions" },
              { to: "/student/assessments", label: "Assessments", icon: ClipboardCheck, count: s.assessments.taken, unit: "taken" },
            ].map(({ to, label, icon: Icon, count, unit }) => (
              <Link key={to} to={to} className="card-hover flex flex-col gap-2 rounded-lg border border-slate-200 p-4">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Icon size={18} aria-hidden /></span>
                <span className="font-medium text-slate-900">{label}</span>
                <span className="text-xs text-slate-500"><span className="num font-semibold text-slate-700">{count}</span> {unit}</span>
                <span className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-brand-600">Start <ArrowUpRight size={14} /></span>
              </Link>
            ))}
          </div>
        </Card>
        <Card title="Recommended next steps">
          {data.profile_completeness < 100 && (
            <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
              <Meter label="Profile completion" value={data.profile_completeness} suffix="%" />
              <Link to={resume ? "/profile" : "/student/resume"} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline">
                {resume ? "Complete your profile" : "Upload your resume"} <ArrowUpRight size={12} />
              </Link>
            </div>
          )}
          {steps.length === 0 ? (
            <EmptyState icon={CheckCircle2} title="You're on track" message="No gaps detected right now. Keep a steady practice rhythm." />
          ) : (
            <div className="divide-y divide-slate-100">
              {steps.map((x) => <LinkRow key={x.key} to={x.to} icon={x.icon} title={x.title} meta={x.meta} tone="brand" />)}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="Score progress" className="lg:col-span-2" actions={<CardLink to="/student/progress">Details</CardLink>}>
          <ProgressChart series={data.progress} />
        </Card>
        <Link to="/student/interviews" aria-label="Open the live mock interview room"
          className="group relative flex min-h-[300px] flex-col overflow-hidden rounded-xl bg-night-900 ring-1 ring-slate-200 transition hover:ring-slate-300">
          <InterviewerStage who="aria" className="absolute inset-0" />
          <div className="relative mt-auto bg-gradient-to-t from-night-950/90 via-night-950/60 to-transparent p-5 pt-16 text-snow">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-snow/60">Live interview room</p>
            <p className="mt-1 font-display text-lg font-semibold">Practise out loud with a 3D interviewer</p>
            <p className="mt-1 text-sm text-snow/70">Voice questions, follow-ups and a scored report. Four interviewer styles.</p>
            <span className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-snow">Choose an interviewer <ArrowUpRight size={15} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" /></span>
          </div>
        </Link>
      </div>

      <RoleRecommendations />

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="My applications" actions={<CardLink to="/student/applications">All applications</CardLink>}>
          {data.recent_applications.length === 0 ? (
            <EmptyState icon={Briefcase} title="No applications yet" message="Browse openings that match your profile."
              action={<Link to="/student/jobs" className={buttonClass("secondary", "sm")}>Browse jobs</Link>} />
          ) : (
            <div className="divide-y divide-slate-100">
              {data.recent_applications.map((a) => (
                <LinkRow key={a.id} to="/student/applications" icon={Briefcase} title={a.job?.title} meta={a.job?.company_name} right={<StatusPill status={a.status} />} />
              ))}
            </div>
          )}
        </Card>
        <Card title="Upcoming">
          {upcomingCount === 0 ? <EmptyState icon={CalendarClock} title="Nothing scheduled" message="Mentor sessions, job interviews and goals will appear here." /> : (
            <div className="divide-y divide-slate-100">
              {data.upcoming.job_interviews.map((i) => (
                <LinkRow key={`j${i.application_id}`} to="/student/applications" icon={Briefcase} tone="amber" title={`${i.job_title} interview`} meta={`${i.company} · ${fmtDateTime(i.interview_at)}`} />
              ))}
              {data.upcoming.mentor_sessions.map((m) => (
                <LinkRow key={`m${m.id}`} to="/student/mentoring" icon={CalendarClock} tone="brand" title={`Mentor session with ${m.mentor_name}`} meta={fmtDateTime(m.scheduled_at)} />
              ))}
              {data.upcoming.goals.map((g) => (
                <LinkRow key={`g${g.id}`} to="/student/mentoring" icon={Target} tone="green" title={g.title} meta={g.deadline ? `Due ${fmtDate(g.deadline)}` : "No deadline"} />
              ))}
            </div>
          )}
        </Card>
        <DailyPlan compact />
      </div>

      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="Today's challenges" actions={<CardLink to="/student/rewards">All</CardLink>}>
          {data.challenges.length === 0 ? <EmptyState icon={Target} title="No active challenges" /> : (
            <ul className="space-y-4">
              {data.challenges.slice(0, 4).map((c) => (
                <li key={c.id}>
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className={`flex min-w-0 items-center gap-2 ${c.completed ? "text-slate-500 line-through decoration-slate-300" : "text-slate-800"}`}>
                      {c.completed ? <CheckCircle2 size={15} className="shrink-0 text-emerald-600" /> : <Circle size={15} className="shrink-0 text-slate-400" />}
                      <span className="truncate">{c.title}</span>
                    </span>
                    <span className="num shrink-0 text-xs text-slate-500">{c.progress}/{c.target}</span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full ${c.completed ? "bg-emerald-500" : "bg-brand-500"}`} style={{ width: `${Math.min(100, c.percent)}%` }} />
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">{c.period} · +{c.points} points</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Areas to improve" actions={<CardLink to="/student/progress">Insights</CardLink>}>
          {s.weak_areas.length === 0 ? <EmptyState icon={CheckCircle2} title="No weak areas detected yet" message="Keep practising to get personalised insights." /> : (
            <ul className="space-y-2.5">
              {s.weak_areas.slice(0, 6).map((w) => <li key={w} className="flex gap-2.5 text-sm text-slate-700"><span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />{w}</li>)}
            </ul>
          )}
        </Card>
        <Card title="Achievements" actions={<CardLink to="/student/rewards">All rewards</CardLink>}>
          <div className="mb-4 flex items-baseline gap-2">
            <span className="num font-display text-2xl font-bold text-slate-950">{s.rewards.points}</span>
            <span className="text-sm text-slate-500">points · {s.rewards.badges} badge{s.rewards.badges === 1 ? "" : "s"}</span>
          </div>
          {data.recent_badges.length === 0 ? <p className="text-sm text-slate-500">Complete your first mock interview to earn the <b className="font-medium text-slate-700">First Interview</b> badge.</p> : (
            <ul className="grid grid-cols-2 gap-2">
              {data.recent_badges.map((b) => (
                <li key={b.name} className="flex items-center gap-2.5 rounded-lg border border-slate-200 p-2.5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><Award size={16} aria-hidden /></span>
                  <span className="min-w-0"><span className="block truncate text-xs font-semibold text-slate-900">{b.name}</span><span className="block text-[11px] text-slate-500">{fmtDate(b.awarded_at)}</span></span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {s.interviews.recent.length > 0 && (
        <Card title="Recent interviews" bodyClass="" actions={<CardLink to="/student/progress?tab=history">Practice history</CardLink>}>
          <div className="overflow-x-auto">
            <table className="min-w-full">
              <thead className="border-b border-slate-200 bg-slate-50"><tr><th className="th">Role</th><th className="th">Category</th><th className="th">Completed</th><th className="th text-right">Score</th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                {s.interviews.recent.slice().reverse().slice(0, 6).map((i) => (
                  <tr key={i.id} className="transition-colors hover:bg-slate-50">
                    <td className="td"><Link to={`/student/interviews/${i.id}`} className="font-medium text-slate-900 hover:text-brand-600">{i.job_role}</Link></td>
                    <td className="td"><Pill>{i.category}</Pill></td>
                    <td className="td text-slate-500">{fmtDate(i.completed_at)}</td>
                    <td className="td text-right"><span className={`num font-semibold ${i.score == null ? "text-slate-400" : scoreTone(i.score) === "green" ? "text-emerald-600" : scoreTone(i.score) === "amber" ? "text-amber-600" : "text-rose-600"}`}>{i.score ?? "—"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {!resume && s.interviews.completed === 0 && (
        <p className="flex items-center justify-center gap-2 text-xs text-slate-400"><UserRound size={13} /> New here? Upload your resume first — it personalises interview questions and job matches.</p>
      )}
    </div>
  );
}
