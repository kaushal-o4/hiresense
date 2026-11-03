/* Full performance report (GET /student/report): readiness, weekly activity chart and all attempts. */

import { Link } from "react-router-dom";
import { CheckCircle2, CircleDashed, Printer, TrendingDown, TrendingUp } from "lucide-react";
import { get } from "../../api";
import { MultiBar } from "../../components/charts";
import { ReadinessCard } from "../../components/Readiness";
import { Button, Card, ErrorBox, PageHeader, Pill, ScoreBar, Spinner, StatCard, Table, fmtDate, fmtDateTime, useApi } from "../../components/ui";

const Bullets = ({ items, icon: Icon, cls }) => (
  <ul className="space-y-2">{items.map((x) => <li key={x} className="flex gap-2.5 text-sm leading-relaxed text-slate-700"><Icon size={15} className={`mt-[3px] shrink-0 ${cls}`} />{x}</li>)}</ul>
);

function AreaScores({ title, entries, max = 100 }) {
  return (
    <div>
      <p className="eyebrow mb-3">{title}</p>
      {entries.length ? <div className="space-y-3">{entries.map(([k, v]) => <ScoreBar key={k} label={k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())} value={v} max={max} />)}</div>
        : <p className="text-sm text-slate-400">No data yet</p>}
    </div>
  );
}

export function AttemptsTable({ attempts }) {
  return (
    <Table rows={attempts} empty="No completed interviews yet" columns={[
      { label: "Date", render: (a) => fmtDate(a.date) },
      { label: "Interview", render: (a) => <span>{a.role} <Pill>{a.category}</Pill> <Pill>{a.difficulty}</Pill></span> },
      { label: "Score", render: (a) => <span className="num font-semibold text-slate-900">{a.score}</span> },
      { label: "Vs previous (same type)", render: (a) => a.change == null ? <span className="text-slate-400">first attempt</span>
        : <span className={`num inline-flex items-center gap-1 font-medium ${a.change >= 0 ? "text-emerald-700" : "text-rose-700"}`}>{a.change >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />} {Math.abs(a.change)}</span> },
    ]} />
  );
}

export function WeeklyChart({ weekly }) {
  return <MultiBar data={weekly.map((w) => ({ ...w, name: w.week.slice(5), avg_score: w.avg_score || 0 }))} nameKey="name"
    keys={[{ key: "activities", label: "Activities" }, { key: "avg_score", label: "Avg score" }, { key: "minutes", label: "English minutes" }]} />;
}

export default function PerformanceReport() {
  const { data, error, loading, reload } = useApi(() => get("/student/report"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.summary;
  return (
    <div className="space-y-6 print:space-y-4">
      <PageHeader title="Performance report" subtitle={`${s.student.full_name} · generated ${fmtDateTime(data.generated_at)}`}
        actions={<Button variant="secondary" onClick={() => window.print()} className="print:hidden"><Printer size={16} /> Print / save as PDF</Button>} />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Interview average" value={s.interviews.average_score ?? "—"} hint={`${s.interviews.completed} interviews · best ${s.interviews.best_score ?? "—"}`} />
        <StatCard label="Assessment average" value={s.assessments.average_score != null ? `${s.assessments.average_score}%` : "—"} tone="green" hint={`${s.assessments.passed}/${s.assessments.taken} passed`} />
        <StatCard label="English average" value={s.english.average_score ?? "—"} tone="sky" hint={`${s.english.minutes} verified minutes`} />
        <StatCard label="Readiness" value={s.readiness ? Math.round(s.readiness.score) : "—"} hint="Placement readiness, out of 100" />
      </div>
      <ReadinessCard readiness={s.readiness} />
      <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
        <Card title="Strengths">{data.strengths.length ? <Bullets items={data.strengths} icon={CheckCircle2} cls="text-emerald-600" /> : <p className="text-sm text-slate-500">Complete more practice to identify strengths.</p>}</Card>
        <Card title="Weaknesses">{data.weaknesses.length ? <Bullets items={data.weaknesses} icon={CircleDashed} cls="text-rose-500" /> : <p className="text-sm text-slate-500">No weaknesses detected yet.</p>}</Card>
      </div>
      <Card title="Scores by area">
        <div className="grid gap-8 sm:grid-cols-3">
          <AreaScores title="Interviews" entries={Object.entries(s.interviews.by_category)} />
          <AreaScores title="Assessments (%)" entries={Object.entries(s.assessments.by_category)} />
          <AreaScores title="English (out of 10)" entries={Object.entries(s.english.by_criterion)} max={10} />
        </div>
      </Card>
      <Card title="Weekly progress (last 8 weeks)"><WeeklyChart weekly={data.weekly} /></Card>
      <Card title="Progress across attempts" bodyClass=""><AttemptsTable attempts={data.attempts} /></Card>
      <Card title={`Mistakes to review (${data.mistakes.length})`}>
        {data.mistakes.length === 0 ? <p className="text-sm text-slate-500">No mistakes recorded yet.</p> : (
          <ul className="space-y-4">
            {data.mistakes.map((m, i) => (
              <li key={i} className="rounded-lg border border-slate-200 p-4 text-sm leading-relaxed print:break-inside-avoid">
                <div className="flex flex-wrap items-center gap-2"><Pill>{m.type}</Pill>
                  <span className="text-xs text-slate-500">{m.source} · {fmtDate(m.date)}</span>{m.score != null && <span className="num ml-auto font-semibold text-slate-900">{m.score}/100</span>}</div>
                <p className="mt-2 font-medium text-slate-900">{m.question}</p>
                {m.your_answer && <p className="mt-2 text-slate-700"><span className="font-medium text-rose-700">Your answer: </span>{m.your_answer}</p>}
                {m.correct_answer && <p className="mt-1 text-slate-700"><span className="font-medium text-emerald-700">Correct: </span>{m.correct_answer}</p>}
                {m.explanation && <p className="text-slate-600">{m.explanation}</p>}
                {m.feedback && <p className="mt-1 whitespace-pre-line text-slate-600">{m.feedback}</p>}
                {m.sample_answer && <details className="mt-1"><summary className="cursor-pointer font-medium text-slate-700 hover:text-slate-900">Sample answer</summary><p className="mt-2 whitespace-pre-line rounded-lg border border-slate-200 bg-slate-50 p-3 text-slate-700">{m.sample_answer}</p></details>}
                {m.link && <Link className="mt-1 inline-block text-xs text-brand-600 hover:underline print:hidden" to={m.link}>Open</Link>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
