/* Points, badges, streaks, daily challenges and the leaderboard (read-only; the backend awards points). */

import { Award, Flame, Medal, Trophy } from "lucide-react";
import { get } from "../../api";
import { Card, ErrorBox, PageHeader, Pill, ScoreBar, Spinner, StatCard, Table, fmtDate, fmtDateTime, useApi } from "../../components/ui";

const CRITERIA = {
  interviews_completed: "interviews completed", english_minutes: "verified English minutes",
  avg_interview_score: "average interview score", technical_best_score: "best technical score",
  streak_days: "day streak", assessments_passed: "assessments passed", english_sessions: "English sessions",
  high_score_interviews: "interviews scoring 80+", english_avg_score: "average English score",
  pronunciation_drills: "pronunciation drills", speaking_exercises: "speaking exercises",
};

export default function Rewards() {
  const r = useApi(() => get("/student/rewards"));
  const lb = useApi(() => get("/student/leaderboard"));
  const ch = useApi(() => get("/student/challenges"));
  if (r.loading) return <Spinner />;
  if (r.error) return <ErrorBox message={r.error} onRetry={r.reload} />;
  const d = r.data;
  return (
    <div className="space-y-6">
      <PageHeader title="Rewards & achievements" subtitle="Earn points and badges for verified practice. Repeated or invalid activities don't count." />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Total points" value={d.points} icon={Trophy} tone="amber" />
        <StatCard label="Badges earned" value={`${d.earned_count}/${d.badges.length}`} icon={Medal} />
        <StatCard label="Current streak" value={`${d.stats.current_streak} days`} icon={Flame} tone="red" hint={`Longest ${d.stats.streak_days} days`} />
        <StatCard label="Verified English" value={`${d.stats.english_minutes} min`} icon={Award} tone="sky" />
      </div>
      <Card title="Challenges" actions={ch.data && <span className="text-xs text-slate-500">{ch.data.completed_total} completed all-time</span>}>
        {ch.loading ? <Spinner /> : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {ch.data?.challenges.map((c) => (
              <div key={c.id} className={`rounded-xl border p-4 ${c.completed ? "border-emerald-300 bg-emerald-50" : "border-slate-200"}`}>
                <div className="flex items-center justify-between"><p className="font-semibold">{c.title}</p><Pill tone={c.period === "daily" ? "amber" : "violet"}>{c.period}</Pill></div>
                <p className="mt-1 text-xs text-slate-600">{c.description}</p>
                <div className="mt-3"><ScoreBar value={c.percent} /></div>
                <p className="mt-1 text-[11px] text-slate-500">{c.progress}/{c.target} · {c.completed ? `completed · +${c.points} pts earned` : `+${c.points} pts`}</p>
              </div>
            ))}
          </div>
        )}
      </Card>
      <Card title="Badges">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {d.badges.map((b) => (
            <div key={b.id} className={`rounded-xl border p-4 ${b.earned ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"}`}>
              <div className="flex items-start gap-3">
                <span className={`text-3xl ${b.earned ? "" : "opacity-30 grayscale"}`}>{b.icon}</span>
                <div className="flex-1">
                  <p className="font-semibold">{b.name}</p>
                  <p className="text-xs text-slate-600">{b.description}</p>
                  {b.earned ? <p className="mt-2 text-xs font-medium text-amber-700">Earned {fmtDate(b.awarded_at)} · +{b.points} pts</p> : (
                    <div className="mt-2">
                      <ScoreBar value={b.progress} />
                      <p className="mt-1 text-[11px] text-slate-500">{b.current_value} / {b.threshold} {CRITERIA[b.criteria_type]}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
      <div className="grid gap-6 lg:grid-cols-3 [&>*]:min-w-0">
        <Card title="Points history" className="lg:col-span-2" bodyClass="">
          <Table rows={d.transactions} empty="No points yet" columns={[
            { label: "Activity", render: (t) => <span className={t.revoked ? "line-through text-slate-400" : ""}>{t.reason}</span> },
            { label: "Points", render: (t) => <span className="font-semibold text-emerald-700">+{t.points}</span> },
            { label: "Status", render: (t) => t.revoked ? <Pill tone="red">revoked</Pill> : <Pill tone="green">verified</Pill> },
            { label: "Date", render: (t) => fmtDateTime(t.created_at) },
          ]} />
        </Card>
        <Card title="Leaderboard">
          {lb.loading ? <Spinner /> : lb.data?.length ? (
            <ol className="space-y-2">
              {lb.data.map((x) => (
                <li key={x.rank} className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${x.is_me ? "bg-brand-50 font-semibold" : ""}`}>
                  <span>#{x.rank} {x.name}{x.is_me && " (you)"}</span><span>{x.points} pts</span>
                </li>
              ))}
            </ol>
          ) : <p className="text-sm text-slate-500">No points awarded on the platform yet.</p>}
        </Card>
      </div>
    </div>
  );
}
