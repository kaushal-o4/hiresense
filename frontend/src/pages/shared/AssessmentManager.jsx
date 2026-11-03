/*
 * Create, edit, AI-draft and see results of assessments. Used by recruiters (job-specific tests)
 * and admins, at /recruiter/assessments and /admin/assessments.
 */

import { useState } from "react";
import { Plus, Sparkles, Trash2 } from "lucide-react";
import { del, get, post, put } from "../../api";
import { useAuth } from "../../auth";
import {
  Button, Card, ConfirmButton, ErrorBox, Field, Modal, PageHeader, Pagination, Pill, Spinner, Table, fmtDateTime,
  useApi, useToast,
} from "../../components/ui";

const blankQ = () => ({ question: "", options: ["", "", "", ""], answer_index: 0, explanation: "" });
const EMPTY = { title: "", description: "", topic: "", time_limit_minutes: 15, pass_percent: 60, job_id: "", active: true, questions: [blankQ()] };

function AssessmentForm({ open, initial, onClose, onSaved, jobs, isRecruiter }) {
  const toast = useToast();
  const [f, setF] = useState(initial || EMPTY);
  const [busy, setBusy] = useState(false);
  const [gen, setGen] = useState({ count: 5, difficulty: "medium", busy: false });
  const [lastOpen, setLastOpen] = useState(false);
  if (open !== lastOpen) { setLastOpen(open); if (open) setF(initial ? { ...initial, job_id: initial.job_id || "" } : { ...EMPTY, questions: [blankQ()] }); }

  const updQ = (i, patch) => setF({ ...f, questions: f.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) });

  const generate = async () => {
    if (!f.topic.trim()) return toast("Enter a topic first", "error");
    setGen({ ...gen, busy: true });
    try {
      const res = await post("/assessments/generate", { topic: f.topic, count: Number(gen.count), difficulty: gen.difficulty });
      const existing = f.questions.filter((q) => q.question.trim());
      setF({ ...f, questions: [...existing, ...res.questions] });
      toast(`Added ${res.questions.length} AI-drafted questions - please review them before saving`);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGen((g) => ({ ...g, busy: false }));
    }
  };

  const save = async () => {
    setBusy(true);
    try {
      const body = { title: f.title, description: f.description || null, topic: f.topic, time_limit_minutes: Number(f.time_limit_minutes),
        pass_percent: Number(f.pass_percent), job_id: f.job_id ? Number(f.job_id) : null, active: f.active,
        questions: f.questions.map((q) => ({ ...q, options: q.options.filter((o) => o.trim()), answer_index: Number(q.answer_index) })) };
      if (initial) await put(`/assessments/${initial.id}`, body);
      else await post("/assessments", body);
      toast("Assessment saved");
      onSaved();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={initial ? "Edit assessment" : "New assessment"} wide
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={busy} onClick={save}>Save</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Title"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Topic"><input className="input" placeholder="e.g. SQL, Aptitude, Java" value={f.topic} onChange={(e) => setF({ ...f, topic: e.target.value })} /></Field>
        <div className="sm:col-span-2"><Field label="Description"><textarea className="input" rows={2} value={f.description || ""} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field></div>
        <Field label="Time limit (minutes)"><input className="input" type="number" min="1" max="180" value={f.time_limit_minutes} onChange={(e) => setF({ ...f, time_limit_minutes: e.target.value })} /></Field>
        <Field label="Pass mark (%)"><input className="input" type="number" min="1" max="100" value={f.pass_percent} onChange={(e) => setF({ ...f, pass_percent: e.target.value })} /></Field>
        <Field label={isRecruiter ? "Linked job (required)" : "Linked job (optional)"} hint="Job-linked tests are only shown to applicants of that job">
          <select className="input" value={f.job_id} onChange={(e) => setF({ ...f, job_id: e.target.value })}>
            <option value="">{isRecruiter ? "Select a job" : "None - open to all students"}</option>
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title}{j.company_name ? ` · ${j.company_name}` : ""}</option>)}
          </select>
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Active (visible to students)</label>
      </div>
      <div className="mt-6 flex flex-wrap items-end gap-2 rounded-lg bg-brand-50 p-3">
        <span className="text-sm font-medium text-brand-900">Draft questions with AI:</span>
        <select className="input w-24" value={gen.count} onChange={(e) => setGen({ ...gen, count: e.target.value })} aria-label="Number of questions">{[3, 5, 10, 15].map((n) => <option key={n}>{n}</option>)}</select>
        <select className="input w-32" value={gen.difficulty} onChange={(e) => setGen({ ...gen, difficulty: e.target.value })} aria-label="Difficulty"><option>easy</option><option>medium</option><option>hard</option></select>
        <Button size="sm" variant="secondary" loading={gen.busy} onClick={generate}><Sparkles size={14} /> Generate</Button>
      </div>
      <div className="mt-4 space-y-4">
        {f.questions.map((q, i) => (
          <div key={i} className="rounded-lg border border-slate-200 p-3">
            <div className="flex items-center justify-between"><span className="text-xs font-semibold text-slate-500">Question {i + 1}</span>
              <button className="text-slate-400 hover:text-red-600" onClick={() => setF({ ...f, questions: f.questions.filter((_, j) => j !== i) })} aria-label="Remove question"><Trash2 size={16} /></button></div>
            <textarea className="input mt-1" rows={2} value={q.question} onChange={(e) => updQ(i, { question: e.target.value })} placeholder="Question text" />
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {q.options.map((o, j) => (
                <label key={j} className="flex items-center gap-2">
                  <input type="radio" name={`ans${i}`} checked={Number(q.answer_index) === j} onChange={() => updQ(i, { answer_index: j })} aria-label={`Option ${j + 1} is correct`} />
                  <input className="input" value={o} placeholder={`Option ${j + 1}`} onChange={(e) => updQ(i, { options: q.options.map((x, k) => (k === j ? e.target.value : x)) })} />
                </label>
              ))}
            </div>
            <input className="input mt-2" value={q.explanation || ""} placeholder="Explanation (shown after submission)" onChange={(e) => updQ(i, { explanation: e.target.value })} />
          </div>
        ))}
        <Button size="sm" variant="secondary" onClick={() => setF({ ...f, questions: [...f.questions, blankQ()] })}><Plus size={14} /> Add question</Button>
      </div>
    </Modal>
  );
}

export default function AssessmentManager() {
  const { user } = useAuth();
  const toast = useToast();
  const isRecruiter = user.role === "recruiter";
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState(null);
  const { data, error, loading, reload } = useApi(() => get("/assessments", { page }), [page]);
  const jobs = useApi(() => (isRecruiter ? get("/recruiter/jobs", { page_size: 100 }) : get("/admin/jobs", { page_size: 100 })));

  const showResults = async (a) => {
    try { setResults({ a, rows: await get(`/assessments/${a.id}/results`) }); } catch (e) { toast(e.message, "error"); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Assessments" subtitle={isRecruiter ? "Create job-specific tests for your applicants." : "Manage skill assessments for all students."}
        actions={<Button onClick={() => { setEditing(null); setOpen(true); }}><Plus size={16} /> New assessment</Button>} />
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No assessments yet" columns={[
              { label: "Title", render: (a) => <span className="font-medium">{a.title}</span> },
              { label: "Topic", key: "topic" },
              { label: "Questions", key: "question_count" },
              { label: "Job", render: (a) => a.job_id ? jobs.data?.items.find((j) => j.id === a.job_id)?.title || `#${a.job_id}` : "All students" },
              { label: "Status", render: (a) => <Pill dot tone={a.active ? "green" : "gray"}>{a.active ? "Active" : "Inactive"}</Pill> },
              { label: "Created", render: (a) => fmtDateTime(a.created_at) },
              { label: "", render: (a) => (
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => showResults(a)}>Results</Button>
                  <Button size="sm" variant="ghost" onClick={() => { setEditing(a); setOpen(true); }}>Edit</Button>
                  <ConfirmButton size="sm" variant="ghost" message="Delete this assessment and all its results?" onConfirm={async () => {
                    try { await del(`/assessments/${a.id}`); toast("Assessment deleted"); reload(); } catch (e) { toast(e.message, "error"); }
                  }}>Delete</ConfirmButton>
                </div>) },
            ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
      <AssessmentForm open={open} initial={editing} isRecruiter={isRecruiter} jobs={jobs.data?.items || []}
        onClose={() => setOpen(false)} onSaved={() => { setOpen(false); reload(); }} />
      <Modal open={!!results} onClose={() => setResults(null)} title={`Results · ${results?.a.title}`} wide>
        {results && <Table rows={results.rows} empty="No submissions yet" columns={[
          { label: "Student", key: "student_name" }, { label: "Score", render: (r) => `${r.score}%` },
          { label: "Passed", render: (r) => r.passed ? <Pill tone="green">yes</Pill> : <Pill tone="red">no</Pill> },
          { label: "Flag", render: (r) => r.flagged ? <Pill tone="amber">{r.flag_reason}</Pill> : "—" },
          { label: "Submitted", render: (r) => fmtDateTime(r.submitted_at) },
        ]} />}
      </Modal>
    </div>
  );
}
