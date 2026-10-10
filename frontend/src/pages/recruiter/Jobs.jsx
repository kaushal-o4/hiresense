import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { del, get, post, put } from "../../api";
import {
  Button, Card, ConfirmButton, ErrorBox, Field, Modal, PageHeader, Pagination, Spinner, StatusPill, Table, TagInput,
  fmtDate, fromLocalInput, toLocalInput, useApi, useToast,
} from "../../components/ui";

const EMPTY = { title: "", description: "", location: "", job_type: "full_time", experience_years: 0, salary: "", min_cgpa: "",
  eligible_branches: [], graduation_years: [], required_skills: [], preferred_skills: [], deadline: "" };

export function JobForm({ job, open, onClose, onSaved }) {
  const toast = useToast();
  const [f, setF] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setF(job ? { ...EMPTY, ...job, salary: job.salary || "", min_cgpa: job.min_cgpa ?? "", deadline: toLocalInput(job.deadline),
      graduation_years: (job.graduation_years || []).map(String) } : EMPTY);
  }, [open, job]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const save = async (status) => {
    setBusy(true);
    try {
      const body = { ...f, experience_years: Number(f.experience_years) || 0, min_cgpa: f.min_cgpa === "" ? null : Number(f.min_cgpa),
        salary: f.salary || null, deadline: fromLocalInput(f.deadline),
        graduation_years: f.graduation_years.map(Number).filter((y) => y >= 1990 && y <= 2100), status };
      ["id", "recruiter_id", "company_name", "created_at", "updated_at", "published_at", "application_count"].forEach((k) => delete body[k]);
      if (job) await put(`/recruiter/jobs/${job.id}`, body);
      else await post("/recruiter/jobs", body);
      toast(job ? "Job updated" : status === "published" ? "Job published" : "Draft saved");
      onSaved();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={job ? "Edit job" : "Post a new job"} wide
      footer={<>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
        {job ? <Button loading={busy} onClick={() => save(job.status === "published" ? "published" : "draft")}>Save changes</Button> : <>
          <Button variant="secondary" loading={busy} onClick={() => save("draft")}>Save as draft</Button>
          <Button loading={busy} onClick={() => save("published")}>Publish</Button>
        </>}
      </>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2"><Field label="Job title *"><input className="input" value={f.title} onChange={set("title")} /></Field></div>
        <div className="sm:col-span-2"><Field label="Description *" hint="At least 20 characters"><textarea className="input" rows={6} value={f.description} onChange={set("description")} /></Field></div>
        <Field label="Location *"><input className="input" value={f.location} onChange={set("location")} /></Field>
        <Field label="Job type">
          <select className="input" value={f.job_type} onChange={set("job_type")}>
            <option value="full_time">Full-time</option><option value="internship">Internship</option><option value="part_time">Part-time</option><option value="contract">Contract</option>
          </select>
        </Field>
        <Field label="Experience required (years)"><input className="input" type="number" min="0" max="30" step="0.5" value={f.experience_years} onChange={set("experience_years")} /></Field>
        <Field label="Salary / stipend"><input className="input" placeholder="e.g. 6-8 LPA" value={f.salary} onChange={set("salary")} /></Field>
        <Field label="Minimum CGPA"><input className="input" type="number" min="0" max="10" step="0.1" value={f.min_cgpa} onChange={set("min_cgpa")} /></Field>
        <Field label="Application deadline"><input className="input" type="datetime-local" value={f.deadline} onChange={set("deadline")} /></Field>
        <div className="sm:col-span-2"><Field label="Required skills"><TagInput value={f.required_skills} onChange={(v) => setF({ ...f, required_skills: v })} /></Field></div>
        <div className="sm:col-span-2"><Field label="Preferred skills"><TagInput value={f.preferred_skills} onChange={(v) => setF({ ...f, preferred_skills: v })} /></Field></div>
        <Field label="Eligible branches" hint="Leave empty for all branches"><TagInput value={f.eligible_branches} onChange={(v) => setF({ ...f, eligible_branches: v })} /></Field>
        <Field label="Graduation years" hint="e.g. 2026, 2027"><TagInput value={f.graduation_years} onChange={(v) => setF({ ...f, graduation_years: v })} /></Field>
      </div>
    </Modal>
  );
}

export default function RecruiterJobs() {
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(null);
  const [formOpen, setFormOpen] = useState(params.get("new") === "1");
  const { data, error, loading, reload } = useApi(() => get("/recruiter/jobs", { status, page }), [status, page]);

  const act = async (fn, msg) => { try { await fn(); toast(msg); reload(); } catch (e) { toast(e.message, "error"); } };

  return (
    <div className="space-y-6">
      <PageHeader title="Job postings" actions={<Button onClick={() => { setEditing(null); setFormOpen(true); }}><Plus size={16} /> Post a job</Button>} />
      <div className="flex gap-2">
        {["", "published", "draft", "closed"].map((s) => (
          <button key={s || "all"} onClick={() => { setStatus(s); setPage(1); }} className={`rounded-full px-3 py-1 text-sm ${status === s ? "bg-brand-600 text-white" : "bg-white ring-1 ring-slate-200"}`}>{s || "All"}</button>
        ))}
      </div>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No jobs yet - post your first job!"
              columns={[
                { label: "Title", render: (j) => <Link className="font-medium text-brand-700 hover:underline" to={`/recruiter/jobs/${j.id}`}>{j.title}</Link> },
                { label: "Location", key: "location" },
                { label: "Applications", key: "application_count" },
                { label: "Status", render: (j) => <StatusPill status={j.status} /> },
                { label: "Deadline", render: (j) => fmtDate(j.deadline) },
                { label: "", render: (j) => (
                  <div className="flex flex-wrap gap-1">
                    {j.status !== "closed" && <Button size="sm" variant="ghost" onClick={() => { setEditing(j); setFormOpen(true); }}>Edit</Button>}
                    {j.status !== "published" && <Button size="sm" variant="ghost" onClick={() => act(() => post(`/recruiter/jobs/${j.id}/status/publish`), "Job published")}>Publish</Button>}
                    {j.status === "published" && <ConfirmButton size="sm" variant="ghost" message="Close this job? Students can no longer apply." onConfirm={() => act(() => post(`/recruiter/jobs/${j.id}/status/close`), "Job closed")}>Close</ConfirmButton>}
                    {j.application_count === 0 && <ConfirmButton size="sm" variant="ghost" message="Delete this job permanently?" onConfirm={() => act(() => del(`/recruiter/jobs/${j.id}`), "Job deleted")}>Delete</ConfirmButton>}
                  </div>) },
              ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
      <JobForm open={formOpen} job={editing} onClose={() => { setFormOpen(false); setParams({}); }} onSaved={() => { setFormOpen(false); setParams({}); reload(); }} />
    </div>
  );
}
