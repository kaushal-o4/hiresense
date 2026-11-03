/*
 * Everything a mentor needs for one student, in tabs: overview, interviews and English sessions,
 * resume, improvement plans and goals, feedback and private notes, and follow-up sessions.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";
import { Plus, Trash2 } from "lucide-react";
import { del, get, patch, post, put } from "../../api";
import {
  Button, Card, ConfirmButton, ErrorBox, Field, Modal, PageHeader, Pill, ScoreBar, Spinner, StatCard, StatusPill,
  Table, Tabs, fmtDate, fmtDateTime, fromLocalInput, toLocalInput, useApi, useToast,
} from "../../components/ui";
import { RecommendationsCard, SummaryCharts } from "../student/Progress";
import { ResumeAnalysisView } from "../student/Resume";
import { InterviewReport } from "../student/InterviewSession";

const GOAL_TYPES = ["mock_interview", "english_practice", "assessment", "resume_update", "resource", "custom"];
const blankGoal = () => ({ title: "", description: "", goal_type: "mock_interview", resource_url: "", target_count: 1, target_score: "", deadline: "" });

function goalBody(g) {
  return { title: g.title, description: g.description || null, goal_type: g.goal_type, resource_url: g.resource_url || null,
    target_count: Number(g.target_count) || 1, target_score: g.target_score === "" || g.target_score == null ? null : Number(g.target_score),
    deadline: fromLocalInput(g.deadline) };
}

function GoalFields({ g, onChange }) {
  const set = (k) => (e) => onChange({ ...g, [k]: e.target.value });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="sm:col-span-2"><Field label="Goal"><input className="input" value={g.title} onChange={set("title")} placeholder="e.g. Complete 3 technical mock interviews" /></Field></div>
      <Field label="Type" hint="Interview, English and assessment goals are tracked automatically">
        <select className="input" value={g.goal_type} onChange={set("goal_type")}>{GOAL_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</select>
      </Field>
      <Field label="Deadline"><input className="input" type="datetime-local" value={g.deadline} onChange={set("deadline")} /></Field>
      <Field label="Target count"><input className="input" type="number" min="1" max="100" value={g.target_count} onChange={set("target_count")} /></Field>
      <Field label="Minimum score (optional)"><input className="input" type="number" min="0" max="100" value={g.target_score} onChange={set("target_score")} /></Field>
      <div className="sm:col-span-2"><Field label="Learning resource URL (optional)"><input className="input" value={g.resource_url} onChange={set("resource_url")} /></Field></div>
      <div className="sm:col-span-2"><Field label="Details"><textarea className="input" rows={2} value={g.description} onChange={set("description")} /></Field></div>
    </div>
  );
}

export default function MentorStudentDetail() {
  const { id } = useParams();
  const toast = useToast();
  const [tab, setTab] = useState("overview");
  const [fb, setFb] = useState({ content: "", kind: "feedback", category: "general" });
  const [planModal, setPlanModal] = useState(null);
  const [goalModal, setGoalModal] = useState(null);
  const [sessionModal, setSessionModal] = useState(null);
  const [viewInterview, setViewInterview] = useState(null);
  const [viewEnglish, setViewEnglish] = useState(null);
  const [busy, setBusy] = useState(false);
  const { data, error, loading, reload } = useApi(() => get(`/mentor/students/${id}`), [id]);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.summary;

  const run = async (fn, msg) => {
    setBusy(true);
    try { await fn(); if (msg) toast(msg); reload(); return true; } catch (e) { toast(e.message, "error"); return false; } finally { setBusy(false); }
  };

  const openInterview = async (row) => {
    try { setViewInterview(await get(`/mentor/students/${id}/interviews/${row.id}`)); } catch (e) { toast(e.message, "error"); }
  };
  const openEnglish = async (row) => {
    try { setViewEnglish(await get(`/mentor/students/${id}/english/${row.id}`)); } catch (e) { toast(e.message, "error"); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title={s.student.full_name} subtitle={<span className="flex flex-wrap items-center gap-2">{s.student.email} · {s.student.branch || "—"} · CGPA {s.student.cgpa ?? "—"} <StatusPill status={s.trend} /></span>}
        actions={<Button variant="secondary" onClick={() => setSessionModal({ scheduled_at: "", agenda: "", meeting_link: "" })}>Schedule session</Button>} />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <StatCard label="Interview avg" value={s.interviews.average_score ?? "—"} hint={`${s.interviews.completed} completed`} />
        <StatCard label="English" value={`${s.english.minutes} min`} tone="sky" hint={`avg ${s.english.average_score ?? "—"}`} />
        <StatCard label="Assessments" value={s.assessments.average_score != null ? `${s.assessments.average_score}%` : "—"} tone="green" hint={`${s.assessments.passed}/${s.assessments.taken} passed`} />
        <StatCard label="Points" value={s.rewards.points} tone="amber" hint={`${s.rewards.badges} badges · streak ${s.rewards.current_streak}`} />
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[
        { value: "overview", label: "Overview" }, { value: "activity", label: "Interviews & English" }, { value: "resume", label: "Resume" },
        { value: "guidance", label: "Plans & goals" }, { value: "feedback", label: "Feedback & notes" }, { value: "sessions", label: "Sessions" }]} />

      {tab === "overview" && (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
            <Card title="Weak areas">{s.weak_areas.length ? <ul className="space-y-1.5">{s.weak_areas.map((w) => <li key={w} className="flex gap-2 text-sm text-slate-700"><span className="mt-[8px] h-1 w-1 shrink-0 rounded-full bg-slate-400" aria-hidden />{w}</li>)}</ul> : <p className="text-sm text-slate-500">None detected yet.</p>}</Card>
            <RecommendationsCard endpoint={`/mentor/students/${id}/recommendations`} />
          </div>
          <SummaryCharts summary={s} series={data.series} />
        </div>
      )}

      {tab === "activity" && (
        <div className="space-y-6">
          <Card title="Mock interviews" bodyClass="">
            <Table rows={data.interviews} empty="No interviews yet" onRowClick={openInterview} columns={[
              { label: "Role", key: "job_role" }, { label: "Focus", key: "category" }, { label: "Mode", key: "mode" },
              { label: "Score", render: (r) => r.overall_score ?? "—" }, { label: "Status", render: (r) => <span className="flex gap-1"><StatusPill status={r.status} />{r.flagged && <Pill tone="red">flagged</Pill>}</span> },
              { label: "Date", render: (r) => fmtDateTime(r.created_at) }]} />
          </Card>
          <Card title="English practice" bodyClass="">
            <Table rows={data.english_sessions} empty="No English sessions yet" onRowClick={openEnglish} columns={[
              { label: "Topic", key: "topic" }, { label: "Active time", render: (r) => `${Math.round(r.active_seconds / 60)} min` },
              { label: "Score", render: (r) => r.overall_score ?? "—" }, { label: "Status", render: (r) => <StatusPill status={r.status} /> },
              { label: "Date", render: (r) => fmtDateTime(r.created_at) }]} />
          </Card>
          <Card title="Assessment results" bodyClass="">
            <Table rows={data.assessment_results} empty="No assessments taken" columns={[
              { label: "Assessment", key: "assessment_title" }, { label: "Topic", key: "topic" }, { label: "Score", render: (r) => `${r.score}%` },
              { label: "Passed", render: (r) => r.passed ? <Pill tone="green">yes</Pill> : <Pill tone="red">no</Pill> },
              { label: "Date", render: (r) => fmtDateTime(r.submitted_at) }]} />
          </Card>
        </div>
      )}

      {tab === "resume" && (data.resume?.analysis ? <ResumeAnalysisView resume={data.resume} /> : <Card><p className="text-sm text-slate-500">{data.resume ? "The resume has not been analysed yet." : "No resume uploaded yet."}</p></Card>)}

      {tab === "guidance" && (
        <div className="space-y-4">
          <div className="flex justify-end"><Button onClick={() => setPlanModal({ title: "", description: "", goals: [blankGoal()] })}><Plus size={16} /> New improvement plan</Button></div>
          {data.plans.length === 0 && <Card><p className="text-sm text-slate-500">No plans yet. Create one with goals and deadlines.</p></Card>}
          {data.plans.map((p) => (
            <Card key={p.id} title={<span className="flex items-center gap-2">{p.title} <StatusPill status={p.status} /></span>}
              actions={<>
                <Button size="sm" variant="secondary" onClick={() => setGoalModal({ planId: p.id, goal: blankGoal() })}><Plus size={14} /> Goal</Button>
                <select className="input w-auto py-1 text-xs" value={p.status} aria-label="Plan status" onChange={(e) => run(() => patch(`/mentor/plans/${p.id}`, { status: e.target.value }), "Plan updated")}>
                  <option value="active">active</option><option value="completed">completed</option><option value="archived">archived</option>
                </select>
                {p.mentor_id && <ConfirmButton size="sm" variant="ghost" message="Delete this plan and its goals?" onConfirm={() => run(() => del(`/mentor/plans/${p.id}`), "Plan deleted")}><Trash2 size={14} /></ConfirmButton>}
              </>}>
              {p.description && <p className="mb-3 text-sm text-slate-600">{p.description}</p>}
              <ul className="space-y-2">
                {p.goals.map((g) => (
                  <li key={g.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 p-3">
                    <div className="min-w-[12rem] flex-1">
                      <p className="text-sm font-medium">{g.title}</p>
                      <p className="text-xs text-slate-500">{g.goal_type.replace(/_/g, " ")} · {g.progress ?? 0}/{g.target_count}{g.target_score != null && ` · min score ${g.target_score}`}{g.deadline && ` · due ${fmtDate(g.deadline)}`}</p>
                      <div className="mt-1 max-w-xs"><ScoreBar value={(Math.min(g.progress ?? 0, g.target_count) / g.target_count) * 100} /></div>
                    </div>
                    <StatusPill status={g.status} />
                    <Button size="sm" variant="ghost" onClick={() => run(() => post(`/mentor/goals/${g.id}/status?status=${g.status === "completed" ? "pending" : "completed"}`), "Goal updated")}>
                      {g.status === "completed" ? "Reopen" : "Mark done"}</Button>
                    <Button size="sm" variant="ghost" onClick={() => setGoalModal({ goalId: g.id, goal: { ...g, description: g.description || "", resource_url: g.resource_url || "", target_score: g.target_score ?? "", deadline: toLocalInput(g.deadline) } })}>Edit</Button>
                    <ConfirmButton size="sm" variant="ghost" message="Delete this goal?" onConfirm={() => run(() => del(`/mentor/goals/${g.id}`), "Goal deleted")}><Trash2 size={14} /></ConfirmButton>
                  </li>
                ))}
                {p.goals.length === 0 && <li className="text-sm text-slate-500">No goals yet.</li>}
              </ul>
            </Card>
          ))}
        </div>
      )}

      {tab === "feedback" && (
        <div className="grid gap-6 lg:grid-cols-2 [&>*]:min-w-0">
          <Card title="Add feedback or a private note">
            <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); if (await run(() => post(`/mentor/students/${id}/feedback`, fb), fb.kind === "feedback" ? "Feedback sent to the student" : "Note saved")) setFb({ ...fb, content: "" }); }}>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Type"><select className="input" value={fb.kind} onChange={(e) => setFb({ ...fb, kind: e.target.value })}><option value="feedback">Feedback (student sees it)</option><option value="note">Private note</option></select></Field>
                <Field label="Category"><select className="input" value={fb.category} onChange={(e) => setFb({ ...fb, category: e.target.value })}>{["general", "technical", "communication", "interview", "resume"].map((c) => <option key={c}>{c}</option>)}</select></Field>
              </div>
              <Field label="Message"><textarea className="input" rows={5} required minLength={2} value={fb.content} onChange={(e) => setFb({ ...fb, content: e.target.value })} /></Field>
              <Button type="submit" loading={busy}>Save</Button>
            </form>
          </Card>
          <Card title="History">
            {data.feedback.length === 0 ? <p className="text-sm text-slate-500">Nothing yet.</p> : (
              <ul className="space-y-3">{data.feedback.map((f) => (
                <li key={f.id} className={`rounded-lg p-3 text-sm ${f.kind === "note" ? "bg-amber-50" : "bg-slate-50"}`}>
                  <div className="flex items-center gap-2"><Pill tone={f.kind === "note" ? "amber" : "brand"}>{f.kind === "note" ? "private note" : "feedback"}</Pill><Pill>{f.category}</Pill>
                    <span className="ml-auto text-xs text-slate-500">{f.mentor_name} · {fmtDateTime(f.created_at)}</span>
                    <ConfirmButton size="sm" variant="ghost" message="Delete this entry?" onConfirm={() => run(() => del(`/mentor/feedback/${f.id}`), "Deleted")}><Trash2 size={12} /></ConfirmButton></div>
                  <p className="mt-2 whitespace-pre-line">{f.content}</p>
                </li>))}</ul>
            )}
          </Card>
        </div>
      )}

      {tab === "sessions" && (
        <Card title="Follow-up sessions" bodyClass="" actions={<Button size="sm" onClick={() => setSessionModal({ scheduled_at: "", agenda: "", meeting_link: "" })}><Plus size={14} /> Schedule</Button>}>
          <Table rows={data.sessions} empty="No sessions yet" columns={[
            { label: "When", render: (r) => fmtDateTime(r.scheduled_at) }, { label: "Agenda", key: "agenda" },
            { label: "Status", render: (r) => <StatusPill status={r.status} /> }, { label: "Outcome", render: (r) => r.outcome_notes || "—" },
            { label: "", render: (r) => r.status === "scheduled" && <div className="flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => setSessionModal({ ...r, scheduled_at: toLocalInput(r.scheduled_at), meeting_link: r.meeting_link || "", outcome_notes: r.outcome_notes || "" })}>Update</Button>
            </div> }]} />
        </Card>
      )}

      <Modal open={!!planModal} onClose={() => setPlanModal(null)} title="New improvement plan" wide
        footer={<><Button variant="secondary" onClick={() => setPlanModal(null)}>Cancel</Button>
          <Button loading={busy} onClick={async () => { if (await run(() => post(`/mentor/students/${id}/plans`, { title: planModal.title, description: planModal.description || null, goals: planModal.goals.filter((g) => g.title.trim()).map(goalBody) }), "Plan created and shared with the student")) setPlanModal(null); }}>Create plan</Button></>}>
        {planModal && (
          <div className="space-y-4">
            <Field label="Plan title"><input className="input" value={planModal.title} onChange={(e) => setPlanModal({ ...planModal, title: e.target.value })} placeholder="e.g. Technical interview readiness - 4 weeks" /></Field>
            <Field label="Description"><textarea className="input" rows={2} value={planModal.description} onChange={(e) => setPlanModal({ ...planModal, description: e.target.value })} /></Field>
            {planModal.goals.map((g, i) => (
              <div key={i} className="rounded-lg border border-slate-200 p-3">
                <GoalFields g={g} onChange={(ng) => setPlanModal({ ...planModal, goals: planModal.goals.map((x, j) => (j === i ? ng : x)) })} />
              </div>
            ))}
            <Button size="sm" variant="secondary" onClick={() => setPlanModal({ ...planModal, goals: [...planModal.goals, blankGoal()] })}><Plus size={14} /> Add goal</Button>
          </div>
        )}
      </Modal>

      <Modal open={!!goalModal} onClose={() => setGoalModal(null)} title={goalModal?.goalId ? "Edit goal" : "Add goal"}
        footer={<><Button variant="secondary" onClick={() => setGoalModal(null)}>Cancel</Button>
          <Button loading={busy} onClick={async () => {
            const body = goalBody(goalModal.goal);
            const ok = await run(() => (goalModal.goalId ? put(`/mentor/goals/${goalModal.goalId}`, body) : post(`/mentor/plans/${goalModal.planId}/goals`, body)), "Goal saved");
            if (ok) setGoalModal(null);
          }}>Save goal</Button></>}>
        {goalModal && <GoalFields g={goalModal.goal} onChange={(goal) => setGoalModal({ ...goalModal, goal })} />}
      </Modal>

      <Modal open={!!sessionModal} onClose={() => setSessionModal(null)} title={sessionModal?.id ? "Update session" : "Schedule a follow-up session"}
        footer={<><Button variant="secondary" onClick={() => setSessionModal(null)}>Cancel</Button>
          <Button loading={busy} onClick={async () => {
            const m = sessionModal;
            const ok = m.id
              ? await run(() => patch(`/mentor/sessions/${m.id}`, { scheduled_at: fromLocalInput(m.scheduled_at), agenda: m.agenda, meeting_link: m.meeting_link || null, status: m.status, outcome_notes: m.outcome_notes || null }), "Session updated")
              : await run(() => post("/mentor/sessions", { student_id: Number(id), scheduled_at: fromLocalInput(m.scheduled_at), agenda: m.agenda, meeting_link: m.meeting_link || null }), "Session scheduled - the student has been notified");
            if (ok) setSessionModal(null);
          }}>Save</Button></>}>
        {sessionModal && (
          <div className="space-y-3">
            <Field label="Date & time"><input className="input" type="datetime-local" value={sessionModal.scheduled_at} onChange={(e) => setSessionModal({ ...sessionModal, scheduled_at: e.target.value })} /></Field>
            <Field label="Agenda"><textarea className="input" rows={3} value={sessionModal.agenda} onChange={(e) => setSessionModal({ ...sessionModal, agenda: e.target.value })} /></Field>
            <Field label="Meeting link (optional)"><input className="input" value={sessionModal.meeting_link} onChange={(e) => setSessionModal({ ...sessionModal, meeting_link: e.target.value })} /></Field>
            {sessionModal.id && (
              <>
                <Field label="Status"><select className="input" value={sessionModal.status} onChange={(e) => setSessionModal({ ...sessionModal, status: e.target.value })}><option value="scheduled">scheduled</option><option value="completed">completed</option><option value="cancelled">cancelled</option></select></Field>
                <Field label="Outcome notes"><textarea className="input" rows={3} value={sessionModal.outcome_notes} onChange={(e) => setSessionModal({ ...sessionModal, outcome_notes: e.target.value })} /></Field>
              </>
            )}
          </div>
        )}
      </Modal>

      <Modal open={!!viewInterview} onClose={() => setViewInterview(null)} title={viewInterview ? `${viewInterview.job_role} · ${viewInterview.category}` : ""} wide>
        {viewInterview && <InterviewReport session={viewInterview} />}
      </Modal>
      <Modal open={!!viewEnglish} onClose={() => setViewEnglish(null)} title={viewEnglish?.topic} wide>
        {viewEnglish && (
          <div className="space-y-3 text-sm">
            {viewEnglish.feedback && <p className="rounded-lg bg-brand-50 p-3">{viewEnglish.feedback.summary}</p>}
            {viewEnglish.scores && <div className="grid gap-2 sm:grid-cols-2">{Object.entries(viewEnglish.scores).map(([k, v]) => <ScoreBar key={k} label={k.replace(/_/g, " ")} value={v} max={10} />)}</div>}
            {viewEnglish.messages.map((m) => (
              <div key={m.id} className={m.sender === "student" ? "text-right" : ""}>
                <span className={`inline-block max-w-[85%] rounded-xl px-3 py-2 text-left ${m.sender === "student" ? "bg-brand-100" : "bg-slate-100"}`}>{m.content}</span>
                {m.corrections?.map((c, i) => <p key={i} className="text-xs text-slate-500">{c.original} → <b>{c.corrected}</b></p>)}
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
}
