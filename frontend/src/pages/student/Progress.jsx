import { useState } from "react";
import { Sparkles } from "lucide-react";
import { get, post } from "../../api";
import { MultiBar, ProgressChart, SimpleBar } from "../../components/charts";
import { Button, Card, ErrorBox, PageHeader, Pill, Spinner, StatCard, StatusPill, useApi, useToast } from "../../components/ui";

export function RecommendationsCard({ endpoint }) {
  const toast = useToast();
  const [rec, setRec] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    try { setRec(await post(endpoint)); } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  return (
    <Card title="AI recommendations" actions={<Button size="sm" onClick={load} loading={busy}><Sparkles size={14} /> {rec ? "Refresh" : "Generate"}</Button>}>
      {!rec ? <p className="text-sm text-slate-500">Generate personalised practice recommendations based on the recorded interview, English and assessment data.</p> : (
        <div className="space-y-4">
          <p className="text-sm">{rec.summary}</p>
          {rec.weak_areas?.length > 0 && <div className="flex flex-wrap gap-2">{rec.weak_areas.map((w) => <Pill key={w} tone="red">{w}</Pill>)}</div>}
          <ul className="space-y-3">
            {rec.recommendations.map((r, i) => (
              <li key={i} className="rounded-lg border border-slate-200 p-3">
                <p className="text-sm font-medium">{r.title} <Pill tone="brand" className="ml-1">{r.activity_type.replace(/_/g, " ")}</Pill></p>
                <p className="mt-1 text-xs text-slate-600">{r.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

export function SummaryCharts({ summary, series }) {
  const cat = Object.entries(summary.interviews.by_category).map(([k, v]) => ({ name: k, score: v }));
  const eng = Object.entries(summary.english.by_criterion).map(([k, v]) => ({ name: k.replace(/_/g, " "), score: v }));
  const topics = Object.entries(summary.assessments.by_topic).map(([k, v]) => ({ name: k, score: v }));
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card title="Score trend" className="lg:col-span-2"><ProgressChart series={series} /></Card>
      <Card title="Interview score by focus area"><SimpleBar data={cat} dataKey="score" nameKey="name" max={100} /></Card>
      <Card title="English skills (out of 10)"><SimpleBar data={eng} dataKey="score" nameKey="name" max={10} color="#0ea5e9" /></Card>
      <Card title="Assessment score by topic"><SimpleBar data={topics} dataKey="score" nameKey="name" max={100} color="#10b981" /></Card>
      <Card title="Interview types over time">
        <ProgressChart series={series} metrics={["technical_score", "hr_score", "behavioral_score", "communication_score"]} />
      </Card>
    </div>
  );
}

export default function Progress() {
  const { data, error, loading, reload } = useApi(() => get("/student/progress"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.summary;
  return (
    <div className="space-y-6">
      <PageHeader title="Performance & progress" subtitle={<span>Overall trend: <StatusPill status={s.trend} /></span>} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Interviews" value={s.interviews.completed} hint={`Avg ${s.interviews.average_score ?? "—"} · best ${s.interviews.best_score ?? "—"}`} />
        <StatCard label="English" value={`${s.english.minutes} min`} tone="sky" hint={`Avg score ${s.english.average_score ?? "—"}`} />
        <StatCard label="Assessments" value={s.assessments.taken} tone="green" hint={`${s.assessments.passed} passed · avg ${s.assessments.average_score ?? "—"}%`} />
        <StatCard label="Resume score" value={s.resume?.resume_score ?? "—"} tone="violet" hint={s.resume ? s.resume.filename : "No resume"} />
      </div>
      <SummaryCharts summary={s} series={data.series} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Weak areas detected">
          {s.weak_areas.length ? <ul className="space-y-1 text-sm">{s.weak_areas.map((w) => <li key={w}>• {w}</li>)}</ul>
            : <p className="text-sm text-slate-500">Nothing flagged yet.</p>}
        </Card>
        <RecommendationsCard endpoint="/student/recommendations" />
      </div>
      <Card title="Skill development" bodyClass="p-5">
        <MultiBar nameKey="name" max={100} keys={[{ key: "score", label: "Average score" }]}
          data={[
            { name: "Interviews", score: s.interviews.average_score || 0 },
            { name: "English", score: s.english.average_score || 0 },
            { name: "Assessments", score: s.assessments.average_score || 0 },
            { name: "Resume", score: s.resume?.resume_score || 0 },
          ]} />
      </Card>
    </div>
  );
}
