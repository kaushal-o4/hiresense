/*
 * Resume upload and AI analysis: upload versions, run/retry the analysis, edit the extracted result,
 * copy extracted skills to the profile, download (/student/resumes endpoints).
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Download, FileUp, Loader2, Mic, Pencil, RefreshCw, Trash2, Wand2 } from "lucide-react";
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

const CATEGORY_LABEL = {
  programming_language: "Languages", framework: "Frameworks", tool: "Tools", database: "Databases",
  cloud: "Cloud", domain: "Domains", other: "Other",
};

function Section({ title, count, children, aside }) {
  return (
    <section className="card">
      <div className="flex min-h-[52px] items-center justify-between gap-2 border-b border-slate-200 px-5 py-2.5">
        <h3 className="flex items-center gap-2 text-[15px] font-semibold">
          {title}{count != null && <span className="num rounded bg-slate-100 px-1.5 text-xs font-medium text-slate-500">{count}</span>}
        </h3>
        {aside}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

const Muted = ({ children }) => <p className="text-sm text-slate-500">{children}</p>;

function Entry({ title, meta, children }) {
  return (
    <div className="relative border-l border-slate-200 pb-5 pl-4 last:pb-0">
      <span className="absolute -left-[4.5px] top-1.5 h-2 w-2 rounded-full border border-slate-300 bg-white" aria-hidden />
      <p className="text-sm font-medium text-slate-900">{title}</p>
      {meta && <p className="text-xs text-slate-500">{meta}</p>}
      {children && <div className="mt-1 text-sm leading-relaxed text-slate-600">{children}</div>}
    </div>
  );
}

export function ResumeAnalysisView({ resume, practiceLink = false }) {
  const a = resume.analysis;
  if (!a) return null;
  const technical = a.skills?.filter((s) => s.category !== "soft_skill") || [];
  const soft = a.soft_skills || a.skills?.filter((s) => s.category === "soft_skill").map((s) => s.name) || [];
  const groups = technical.reduce((g, s) => { (g[s.category || "other"] ||= []).push(s.name); return g; }, {});
  const jobs = [...(a.internships || []).map((e) => ({ ...e, kind: "Internship" })), ...(a.experience || []).map((e) => ({ ...e, kind: "Work" }))];
  const actions = [...(a.improvement_areas || []), ...(a.missing_information || [])];
  const score = a.resume_score ?? 0;
  const level = score >= 75 ? ["green", "Strong"] : score >= 50 ? ["amber", "Getting there"] : ["red", "Needs work"];

  return (
    <div className="space-y-6">
      {/* summary band */}
      <div className="card grid overflow-hidden lg:grid-cols-[280px_1fr]">
        <div className="border-b border-slate-200 p-5 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between">
            <p className="text-[13px] font-medium text-slate-500">{a.score_breakdown ? "Resume completeness" : "Resume score"}</p>
            <Pill dot tone={level[0]}>{level[1]}</Pill>
          </div>
          <p className="num mt-2 text-5xl font-semibold tracking-tight text-slate-900">{score}<span className="text-lg font-normal text-slate-400">/100</span></p>
          {a.score_breakdown && (
            <ul className="mt-4 space-y-2">
              {a.score_breakdown.map((p) => (
                <li key={p.section}>
                  <div className="mb-1 flex justify-between text-xs"><span className="text-slate-600">{p.section}</span><span className="num text-slate-500">{p.points}/{p.max}</span></div>
                  <div className="h-1 rounded-full bg-slate-100"><div className={`h-1 rounded-full ${p.points >= p.max ? "bg-emerald-500" : "bg-brand-500"}`} style={{ width: `${(p.points / p.max) * 100}%` }} /></div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex flex-col p-5">
          {a.full_name && <p className="text-lg font-semibold tracking-tight text-slate-900">{a.full_name}</p>}
          {a.candidate_summary && <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-600">{a.candidate_summary}</p>}
          <dl className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 sm:grid-cols-4">
            {[["Skills", technical.length], ["Projects", a.projects?.length || 0], ["Experience", jobs.length], ["Certifications", a.certifications?.length || 0]].map(([k, v]) => (
              <div key={k} className="bg-white px-3 py-2.5"><dt className="text-xs text-slate-500">{k}</dt><dd className="num text-lg font-semibold text-slate-900">{v}</dd></div>
            ))}
          </dl>
          {a.strengths?.length > 0 && (
            <div className="mt-5">
              <p className="eyebrow mb-2">Strengths</p>
              <ul className="grid gap-1.5 sm:grid-cols-2">
                {a.strengths.map((s, i) => <li key={i} className="flex gap-2 text-sm text-slate-700"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />{s}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* action plan */}
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <Section title="What to fix first" count={actions.length}>
          {actions.length ? (
            <ol className="space-y-3">
              {actions.map((x, i) => (
                <li key={i} className="flex gap-3 text-sm text-slate-700">
                  <span className="num flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-300 text-[11px] font-medium text-slate-500">{i + 1}</span>
                  <span className="leading-relaxed">{x}</span>
                </li>
              ))}
            </ol>
          ) : <Muted>Nothing obvious to fix.</Muted>}
        </Section>
        <Section title="Skill gaps for the role" count={a.missing_skills?.length || 0}>
          {a.missing_skills?.length ? (
            <div className="flex flex-wrap gap-1.5">{a.missing_skills.map((s) => <Pill key={s} tone="amber">{s}</Pill>)}</div>
          ) : <Muted>No gaps identified.</Muted>}
          <p className="mt-4 text-xs leading-relaxed text-slate-500">Commonly expected for the target role but not found in the resume. Add them only if they are true.</p>
        </Section>
      </div>

      {/* extracted profile */}
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <Section title="Projects" count={a.projects?.length || 0}>
            {a.projects?.length ? a.projects.map((p, i) => (
              <Entry key={i} title={p.name}>
                {p.description}
                {p.technologies?.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{p.technologies.map((t) => <Pill key={t}>{t}</Pill>)}</div>}
              </Entry>
            )) : <Muted>No projects found.</Muted>}
          </Section>
          <Section title="Experience" count={jobs.length}>
            {jobs.length ? jobs.map((e, i) => (
              <Entry key={i} title={`${e.role || e.kind} · ${e.organization}`} meta={[e.kind, e.duration].filter(Boolean).join(" · ")}>{e.summary}</Entry>
            )) : <Muted>No internships or jobs found.</Muted>}
          </Section>
          <Section title="Education" count={a.education?.length || 0}>
            {a.education?.length ? a.education.map((e, i) => (
              <Entry key={i} title={[e.degree, e.field].filter(Boolean).join(" · ")} meta={[e.institution, e.year, e.score].filter(Boolean).join(" · ")} />
            )) : <Muted>No education details found.</Muted>}
          </Section>
        </div>
        <div className="space-y-6">
          <Section title="Skills" count={technical.length}>
            {technical.length ? (
              <div className="space-y-3">
                {Object.entries(groups).map(([cat, names]) => (
                  <div key={cat}>
                    <p className="mb-1.5 text-xs font-medium text-slate-500">{CATEGORY_LABEL[cat] || cat}</p>
                    <div className="flex flex-wrap gap-1.5">{names.map((n) => <Pill key={n}>{n}</Pill>)}</div>
                  </div>
                ))}
              </div>
            ) : <Muted>No technical skills found.</Muted>}
            {soft.length > 0 && (
              <div className="mt-4 border-t border-slate-100 pt-3">
                <p className="mb-1.5 text-xs font-medium text-slate-500">Soft skills</p>
                <div className="flex flex-wrap gap-1.5">{soft.map((s) => <Pill key={s} tone="blue">{s}</Pill>)}</div>
              </div>
            )}
            {(a.validation?.removed_unsupported?.length > 0 || a.edited_by_student) && (
              <p className="mt-4 text-xs leading-relaxed text-slate-500">
                {a.validation?.removed_unsupported?.length > 0 && `${a.validation.removed_unsupported.length} AI suggestion(s) were removed because they are not in the resume. `}
                {a.edited_by_student && "Corrected by the student."}
              </p>
            )}
          </Section>
          <Section title="Certifications" count={a.certifications?.length || 0}>
            {a.certifications?.length ? <ul className="space-y-1.5 text-sm text-slate-700">{a.certifications.map((c, i) => <li key={i}>{c}</li>)}</ul> : <Muted>None found.</Muted>}
          </Section>
        </div>
      </div>

      {/* interview prep */}
      <Section title="Interview preparation" aside={practiceLink && <Link to="/student/interviews"><Button size="sm"><Mic size={14} /> Practise in a mock interview</Button></Link>}>
        {a.recommended_topics?.length > 0 && (
          <div className="mb-5">
            <p className="eyebrow mb-2">Topics to revise</p>
            <div className="flex flex-wrap gap-1.5">{a.recommended_topics.map((t) => <Pill key={t}>{t}</Pill>)}</div>
          </div>
        )}
        <p className="eyebrow mb-2">Likely questions</p>
        {a.suggested_interview_questions?.length ? (
          <ol className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {a.suggested_interview_questions.map((q, i) => (
              <li key={i} className="flex gap-3 px-4 py-2.5 text-sm text-slate-700"><span className="num w-5 shrink-0 text-slate-400">{i + 1}</span>{q}</li>
            ))}
          </ol>
        ) : <Muted>No questions generated.</Muted>}
      </Section>
    </div>
  );
}

function AnalysingNotice() {
  const [secs, setSecs] = useState(0);
  useEffect(() => { const t = setInterval(() => setSecs((s) => s + 1), 1000); return () => clearInterval(t); }, []);
  return (
    <div className="card flex items-center gap-4 p-4" role="status">
      <Loader2 size={18} className="shrink-0 animate-spin text-slate-400" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-900">Analysing the resume…</p>
        <p className="text-xs text-slate-500">Reading the file, extracting details, then checking every item against the resume text. Keep this page open.</p>
      </div>
      <span className="num text-sm text-slate-500">{secs}s</span>
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
      <PageHeader title="Resume analysis" subtitle="Upload your resume (PDF or DOCX, max 5 MB). An AI model extracts your details, finds skill gaps and writes interview questions for you."
        actions={<>
          <input ref={fileRef} type="file" accept=".pdf,.docx" className="hidden" onChange={(e) => upload(e.target.files[0])} />
          <Button onClick={() => fileRef.current?.click()} loading={uploading}><FileUp size={16} /> {uploading ? "Analysing…" : "Upload resume"}</Button>
        </>} />
      {(uploading || busyId === current?.id) && <AnalysingNotice />}
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
          </Card>
          <ResumeAnalysisView resume={current} practiceLink />
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
