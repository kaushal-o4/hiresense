import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Download, FileUp, Pencil, RefreshCw, Trash2, Wand2 } from "lucide-react";
import { api, del, download, get, patch, post } from "../../api";
import {
  Button, Card, ConfirmButton, EmptyState, ErrorBox, Field, Modal, Notice, PageHeader, Pill, ScoreBar, Spinner,
  StatusPill, fmtDateTime, useApi, useToast,
} from "../../components/ui";

const splitList = (text, sep) => text.split(sep).map((s) => s.trim()).filter(Boolean);

function CorrectAnalysisModal({ resume, open, onClose, onSaved }) {
  const toast = useToast();
  const a = resume.analysis || {};
  const tech = (a.skills || []).filter((s) => s.category !== "soft_skill").map((s) => s.name);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const f = form || { full_name: a.full_name || "", technical_skills: tech.join(", "),
    soft_skills: (a.soft_skills || []).join(", "), certifications: (a.certifications || []).join("\n") };
  const save = async () => {
    setSaving(true);
    try {
      await patch(`/student/resumes/${resume.id}/analysis`, {
        full_name: f.full_name, technical_skills: splitList(f.technical_skills, ","),
        soft_skills: splitList(f.soft_skills, ","), certifications: splitList(f.certifications, "\n"),
      });
      toast("Your corrections were saved");
      setForm(null);
      onSaved();
      onClose();
    } catch (e) { toast(e.message, "error"); } finally { setSaving(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Correct extracted details">
      <div className="space-y-3">
        <p className="text-sm text-slate-500">The AI can make mistakes. Fix anything that is wrong or missing - your edits replace the AI's version.
          Projects and experience can be edited on your <Link className="text-brand-600 hover:underline" to="/profile">profile</Link>.</p>
        <Field label="Full name"><input className="input" value={f.full_name} onChange={(e) => setForm({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Technical skills (comma separated)"><textarea className="input" rows={3} value={f.technical_skills} onChange={(e) => setForm({ ...f, technical_skills: e.target.value })} /></Field>
        <Field label="Soft skills (comma separated)"><input className="input" value={f.soft_skills} onChange={(e) => setForm({ ...f, soft_skills: e.target.value })} /></Field>
        <Field label="Certifications (one per line)"><textarea className="input" rows={3} value={f.certifications} onChange={(e) => setForm({ ...f, certifications: e.target.value })} /></Field>
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={save} loading={saving}>Save corrections</Button></div>
      </div>
    </Modal>
  );
}

export function ResumeAnalysisView({ resume }) {
  const a = resume.analysis;
  if (!a) return null;
  const List = ({ items, empty = "None identified" }) =>
    items?.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{items.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="text-sm text-slate-500">{empty}</p>;
  const Jobs = ({ items }) => items?.length ? items.map((e, i) => (
    <div key={i} className="mb-2 text-sm"><p className="font-medium">{e.role} · {e.organization}</p><p className="text-slate-500">{e.duration}</p><p>{e.summary}</p></div>
  )) : <p className="text-sm text-slate-500">Not found</p>;
  const technical = a.skills?.filter((s) => s.category !== "soft_skill") || [];
  const soft = a.soft_skills || a.skills?.filter((s) => s.category === "soft_skill").map((s) => s.name) || [];
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title={a.score_breakdown ? "Resume completeness" : "Placement readiness"}>
          <p className="text-4xl font-bold text-brand-700">{a.resume_score}<span className="text-lg text-slate-400">/100</span></p>
          <ScoreBar value={a.resume_score} />
          {a.score_breakdown && (
            <ul className="mt-3 space-y-0.5 text-xs text-slate-500">
              {a.score_breakdown.map((p) => <li key={p.section} className="flex justify-between"><span>{p.section}</span><span>{p.points}/{p.max}</span></li>)}
            </ul>
          )}
          {a.full_name && <p className="mt-3 text-sm font-medium">{a.full_name}</p>}
          <p className="mt-1 text-sm text-slate-600">{a.candidate_summary}</p>
        </Card>
        <Card title="Strengths"><List items={a.strengths} /></Card>
        <Card title="Missing skills for your target role"><div className="flex flex-wrap gap-2">{a.missing_skills?.length ? a.missing_skills.map((s) => <Pill key={s} tone="red">{s}</Pill>) : <p className="text-sm text-slate-500">None identified</p>}</div></Card>
      </div>
      <Card title="Extracted skills">
        <div className="flex flex-wrap gap-2">{technical.map((s) => <Pill key={s.name} tone="brand">{s.name} <span className="ml-1 text-[10px] opacity-60">{(s.category || "other").replace(/_/g, " ")}</span></Pill>)}</div>
        {soft.length > 0 && <div className="mt-3 flex flex-wrap items-center gap-2"><span className="text-xs text-slate-500">Soft skills:</span>{soft.map((s) => <Pill key={s} tone="violet">{s}</Pill>)}</div>}
        {a.validation?.removed_unsupported?.length > 0 && (
          <p className="mt-3 text-xs text-slate-500">{a.validation.removed_unsupported.length} item(s) suggested by the AI were removed because they could not be found in your resume.</p>
        )}
        {a.edited_by_student && <p className="mt-1 text-xs text-slate-500">You corrected these details.</p>}
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Education">
          {a.education?.length ? a.education.map((e, i) => (
            <div key={i} className="mb-2 text-sm"><p className="font-medium">{e.degree} {e.field && `· ${e.field}`}</p><p className="text-slate-500">{e.institution} {e.year && `· ${e.year}`} {e.score && `· ${e.score}`}</p></div>
          )) : <p className="text-sm text-slate-500">Not found</p>}
        </Card>
        <Card title="Work experience"><Jobs items={a.experience} /></Card>
        {a.internships && <Card title="Internships"><Jobs items={a.internships} /></Card>}
        <Card title="Projects">
          {a.projects?.length ? a.projects.map((p, i) => (
            <div key={i} className="mb-3 text-sm"><p className="font-medium">{p.name}</p><p className="text-slate-600">{p.description}</p>
              <div className="mt-1 flex flex-wrap gap-1">{p.technologies?.map((t) => <Pill key={t}>{t}</Pill>)}</div></div>
          )) : <p className="text-sm text-slate-500">Not found</p>}
        </Card>
        <Card title="Certifications"><List items={a.certifications} empty="Not found" /></Card>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="How to improve"><List items={a.improvement_areas} /></Card>
        {a.missing_information && <Card title="Missing or unclear information"><List items={a.missing_information} empty="Nothing obvious is missing" /></Card>}
      </div>
      {a.recommended_topics?.length > 0 && (
        <Card title="Topics to prepare for interviews">
          <div className="flex flex-wrap gap-2">{a.recommended_topics.map((t) => <Pill key={t} tone="amber">{t}</Pill>)}</div>
        </Card>
      )}
      <Card title="Personalised interview questions">
        <ol className="list-decimal space-y-2 pl-5 text-sm">{a.suggested_interview_questions?.map((q, i) => <li key={i}>{q}</li>)}</ol>
      </Card>
    </div>
  );
}

export default function Resume() {
  const toast = useToast();
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [editing, setEditing] = useState(false);
  const { data, error, loading, reload } = useApi(() => get("/student/resumes"));
  const current = data?.find((r) => r.is_current);

  const upload = async (file) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) return toast("File must be 5 MB or smaller", "error");
    const fd = new FormData();
    fd.append("file", file);
    setUploading(true);
    try {
      const res = await api("/student/resumes", { method: "POST", body: fd });
      if (res.ai_error) toast(`Resume saved, but AI analysis is unavailable: ${res.ai_error}`, "error");
      else toast("Resume uploaded and analysed");
      reload();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const action = async (id, fn, msg) => {
    setBusyId(id);
    try { await fn(); toast(msg); reload(); } catch (e) { toast(e.message, "error"); } finally { setBusyId(null); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Resume analysis" subtitle="Upload your resume (PDF or DOCX, max 5 MB). A local AI model on this server extracts your details, finds skill gaps and writes interview questions for you - your resume is not sent to any outside service."
        actions={<>
          <input ref={fileRef} type="file" accept=".pdf,.docx" className="hidden" onChange={(e) => upload(e.target.files[0])} />
          <Button onClick={() => fileRef.current?.click()} loading={uploading}><FileUp size={16} /> {uploading ? "Analysing…" : "Upload resume"}</Button>
        </>} />
      {(uploading || busyId === current?.id) && <Notice>The local AI is reading your resume. This usually takes 1-2 minutes - please keep this page open.</Notice>}
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data && data.length === 0 && (
        <Card><EmptyState icon={FileUp} title="No resume uploaded yet" message="Upload your resume to unlock personalised mock interviews and skill-gap analysis."
          action={<Button onClick={() => fileRef.current?.click()}>Upload resume</Button>} /></Card>
      )}
      {current && (
        <>
          <Card title={<span className="flex items-center gap-2">Current resume: {current.filename} <StatusPill status={current.analysis_status} /></span>}
            actions={<>
              {current.analysis_status !== "completed" && (
                <Button size="sm" loading={busyId === current.id} onClick={() => action(current.id, () => post(`/student/resumes/${current.id}/analyze`), "Analysis complete")}>
                  <RefreshCw size={14} /> Retry AI analysis
                </Button>
              )}
              {current.analysis_status === "completed" && (
                <Button size="sm" variant="secondary" onClick={() => setEditing(true)}><Pencil size={14} /> Correct details</Button>
              )}
              {current.analysis_status === "completed" && (
                <Button size="sm" variant="secondary" loading={busyId === "apply"} onClick={() => action("apply", () => post(`/student/resumes/${current.id}/apply-skills`), "Profile updated with resume skills")}>
                  <Wand2 size={14} /> Add skills to my profile
                </Button>
              )}
              <Button size="sm" variant="secondary" onClick={() => download(`/resumes/${current.id}/download`, current.filename).catch((e) => toast(e.message, "error"))}><Download size={14} /> Download</Button>
            </>}>
            <p className="text-sm text-slate-500">Uploaded {fmtDateTime(current.created_at)}</p>
            {current.analysis_status === "unavailable" && <div className="mt-3"><Notice>{current.analysis_error} Your resume is saved; retry the analysis once AI is available.</Notice></div>}
            {current.analysis_status === "completed" && (
              <div className="mt-3"><Link to="/student/interviews" className="text-sm font-medium text-brand-600 hover:underline">Practise these questions in a mock interview →</Link></div>
            )}
          </Card>
          <ResumeAnalysisView resume={current} />
          {current.analysis_status === "completed" && (
            <CorrectAnalysisModal key={current.analyzed_at} resume={current} open={editing} onClose={() => setEditing(false)} onSaved={reload} />
          )}
        </>
      )}
      {data && data.length > 1 && (
        <Card title="Previous versions" bodyClass="divide-y divide-slate-100">
          {data.filter((r) => !r.is_current).map((r) => (
            <div key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
              <div><p className="text-sm font-medium">{r.filename}</p><p className="text-xs text-slate-500">{fmtDateTime(r.created_at)} · score {r.analysis?.resume_score ?? "—"}</p></div>
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" loading={busyId === r.id} onClick={() => action(r.id, () => post(`/student/resumes/${r.id}/make-current`), "Set as current resume")}><CheckCircle2 size={14} /> Make current</Button>
                <ConfirmButton size="sm" variant="ghost" message="Delete this resume version permanently?" onConfirm={() => action(r.id, () => del(`/student/resumes/${r.id}`), "Resume deleted")}><Trash2 size={14} /></ConfirmButton>
              </div>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
