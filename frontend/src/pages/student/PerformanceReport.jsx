import { Link } from "react-router-dom";
import { Printer } from "lucide-react";
import { get } from "../../api";
import { MultiBar } from "../../components/charts";
import { ReadinessCard } from "../../components/Readiness";
import { Button, Card, ErrorBox, PageHeader, Pill, Spinner, StatCard, Table, fmtDate, fmtDateTime, useApi } from "../../components/ui";

export function AttemptsTable({ attempts }) {
  return (
    <Table rows={attempts} empty="No completed interviews yet" columns={[
      { label: "Date", render: (a) => fmtDate(a.date) },
      { label: "Interview", render: (a) => <span>{a.role} <Pill>{a.category}</Pill> <Pill>{a.difficulty}</Pill></span> },
      { label: "Score", render: (a) => <b>{a.score}</b> },
      { label: "Vs previous (same type)", render: (a) => a.change == null ? <span className="text-slate-400">first attempt</span>
        : <span className={a.change >= 0 ? "text-emerald-700" : "text-red-700"}>{a.change >= 0 ? "▲" : "▼"} {Math.abs(a.change)}</span> },
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
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Interview average" value={s.interviews.average_score ?? "—"} hint={`${s.interviews.completed} interviews · best ${s.interviews.best_score ?? "—"}`} />
        <StatCard label="Assessment average" value={s.assessments.average_score != null ? `${s.assessments.average_score}%` : "—"} tone="green" hint={`${s.assessments.passed}/${s.assessments.taken} passed`} />
        <StatCard label="English average" value={s.english.average_score ?? "—"} tone="sky" hint={`${s.english.minutes} verified minutes`} />
        <StatCard label="Pronunciation" value={s.english.pronunciation_avg ?? "—"} tone="violet" hint={`${s.english.pronunciation_drills} drills`} />
      </div>
      <ReadinessCard readiness={s.readiness} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Strengths">{data.strengths.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{data.strengths.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-sm text-slate-500">Complete more practice to identify strengths.</p>}</Card>
        <Card title="Weaknesses">{data.weaknesses.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{data.weaknesses.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-sm text-slate-500">No weaknesses detected yet.</p>}</Card>
      </div>
      <Card title="Scores by area">
        <div className="grid gap-4 text-sm sm:grid-cols-3">
          <div><p className="mb-1 font-semibold">Interviews</p>{Object.entries(s.interviews.by_category).map(([k, v]) => <p key={k}>{k}: <b>{v}</b></p>)}{!Object.keys(s.interviews.by_category).length && <p className="text-slate-400">—</p>}</div>
          <div><p className="mb-1 font-semibold">Assessments</p>{Object.entries(s.assessments.by_category).map(([k, v]) => <p key={k}>{k}: <b>{v}%</b></p>)}{!Object.keys(s.assessments.by_category).length && <p className="text-slate-400">—</p>}</div>
          <div><p className="mb-1 font-semibold">English (out of 10)</p>{Object.entries(s.english.by_criterion).map(([k, v]) => <p key={k}>{k.replace(/_/g, " ")}: <b>{v}</b></p>)}{!Object.keys(s.english.by_criterion).length && <p className="text-slate-400">—</p>}</div>
        </div>
      </Card>
      <Card title="Weekly progress (last 8 weeks)"><WeeklyChart weekly={data.weekly} /></Card>
      <Card title="Progress across attempts" bodyClass=""><AttemptsTable attempts={data.attempts} /></Card>
      <Card title={`Mistakes to review (${data.mistakes.length})`}>
        {data.mistakes.length === 0 ? <p className="text-sm text-slate-500">No mistakes recorded yet.</p> : (
          <ul className="space-y-4">
            {data.mistakes.map((m, i) => (
              <li key={i} className="rounded-lg border border-slate-200 p-4 text-sm print:break-inside-avoid">
                <div className="flex flex-wrap items-center gap-2"><Pill tone={m.type === "interview" ? "brand" : m.type === "coding" ? "violet" : "amber"}>{m.type}</Pill>
                  <span className="text-xs text-slate-500">{m.source} · {fmtDate(m.date)}</span>{m.score != null && <span className="ml-auto font-semibold">{m.score}/100</span>}</div>
                <p className="mt-2 font-medium">{m.question}</p>
                {m.your_answer && <p className="mt-1 text-red-700"><b>Your answer:</b> {m.your_answer}</p>}
                {m.correct_answer && <p className="text-emerald-700"><b>Correct:</b> {m.correct_answer}</p>}
                {m.explanation && <p className="text-slate-600">{m.explanation}</p>}
                {m.feedback && <p className="mt-1 whitespace-pre-line text-slate-600">{m.feedback}</p>}
                {m.sample_answer && <details className="mt-1"><summary className="cursor-pointer text-brand-600">Sample answer</summary><p className="mt-1 whitespace-pre-line rounded bg-brand-50 p-2">{m.sample_answer}</p></details>}
                {m.link && <Link className="mt-1 inline-block text-xs text-brand-600 hover:underline print:hidden" to={m.link}>Open</Link>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
