import { Link } from "react-router-dom";
import { CheckCircle2, ExternalLink, GraduationCap } from "lucide-react";
import { get, post } from "../../api";
import { Button, Card, EmptyState, ErrorBox, PageHeader, Pill, ScoreBar, Spinner, StatusPill, fmtDate, fmtDateTime, useApi, useToast } from "../../components/ui";

const GOAL_LINKS = { mock_interview: "/student/interviews", english_practice: "/student/english", assessment: "/student/assessments", resume_update: "/student/resume" };
const AUTO = ["mock_interview", "english_practice", "assessment"];

export default function Mentoring() {
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => get("/student/mentoring"));
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const complete = async (g) => {
    try { await post(`/student/goals/${g.id}/complete`); toast("Goal marked complete"); reload(); } catch (e) { toast(e.message, "error"); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Mentoring" subtitle="Guidance, goals and sessions from your placement mentor." />
      {data.mentors.length === 0 ? (
        <Card><EmptyState icon={GraduationCap} title="No mentor assigned yet" message="The placement office will assign a mentor to you." /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.mentors.map((m) => (
            <Card key={m.id}><p className="font-semibold">{m.full_name}</p><p className="text-sm text-slate-600">{m.department || "Mentor"} · {m.email}</p></Card>
          ))}
        </div>
      )}
      <Card title="Improvement plans & goals">
        {data.plans.length === 0 ? <p className="text-sm text-slate-500">No plans yet.</p> : (
          <div className="space-y-6">
            {data.plans.map((p) => (
              <div key={p.id}>
                <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{p.title}</h3><StatusPill status={p.status} /><span className="text-xs text-slate-500">by {p.mentor_name}</span></div>
                {p.description && <p className="mt-1 text-sm text-slate-600">{p.description}</p>}
                <ul className="mt-3 space-y-3">
                  {p.goals.map((g) => (
                    <li key={g.id} className="rounded-lg border border-slate-200 p-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium">{g.status === "completed" && <CheckCircle2 size={14} className="mr-1 inline text-emerald-600" />}{g.title}</p>
                          <p className="text-xs text-slate-500"><Pill>{g.goal_type.replace(/_/g, " ")}</Pill> {g.deadline && `· due ${fmtDate(g.deadline)}`} {g.target_score != null && `· target score ${g.target_score}+`}</p>
                          {g.description && <p className="mt-1 text-sm text-slate-600">{g.description}</p>}
                          {g.resource_url && <a className="mt-1 inline-flex items-center gap-1 text-sm text-brand-600 hover:underline" href={g.resource_url} target="_blank" rel="noreferrer">Open resource <ExternalLink size={12} /></a>}
                        </div>
                        <div className="flex items-center gap-2">
                          {g.status === "pending" && GOAL_LINKS[g.goal_type] && <Link to={GOAL_LINKS[g.goal_type]}><Button size="sm" variant="secondary">Practise</Button></Link>}
                          {g.status === "pending" && !AUTO.includes(g.goal_type) && <Button size="sm" onClick={() => complete(g)}>Mark done</Button>}
                          {g.status === "completed" && <Pill tone="green">completed {fmtDate(g.completed_at)}</Pill>}
                        </div>
                      </div>
                      {AUTO.includes(g.goal_type) && g.status === "pending" && (
                        <div className="mt-2 max-w-xs"><ScoreBar value={(Math.min(g.progress ?? 0, g.target_count) / g.target_count) * 100} />
                          <p className="mt-1 text-xs text-slate-500">{g.progress ?? 0}/{g.target_count} done - tracked automatically</p></div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Mentor feedback">
          {data.feedback.length === 0 ? <p className="text-sm text-slate-500">No feedback yet.</p> : (
            <ul className="space-y-3">{data.feedback.map((f) => (
              <li key={f.id} className="rounded-lg bg-slate-50 p-3 text-sm">
                <p className="whitespace-pre-line">{f.content}</p>
                <p className="mt-1 text-xs text-slate-500">{f.mentor_name} · <Pill>{f.category}</Pill> · {fmtDateTime(f.created_at)}</p>
              </li>))}</ul>
          )}
        </Card>
        <Card title="Mentoring sessions">
          {data.sessions.length === 0 ? <p className="text-sm text-slate-500">No sessions scheduled.</p> : (
            <ul className="divide-y divide-slate-100">{data.sessions.map((s) => (
              <li key={s.id} className="py-3 text-sm">
                <div className="flex items-center justify-between"><span className="font-medium">{fmtDateTime(s.scheduled_at)}</span><StatusPill status={s.status} /></div>
                <p className="text-slate-600">{s.agenda}</p>
                {s.meeting_link && s.status === "scheduled" && <a className="text-brand-600 hover:underline" href={s.meeting_link} target="_blank" rel="noreferrer">Join meeting</a>}
                {s.outcome_notes && <p className="mt-1 text-xs text-slate-500">Notes: {s.outcome_notes}</p>}
              </li>))}</ul>
          )}
        </Card>
      </div>
    </div>
  );
}
