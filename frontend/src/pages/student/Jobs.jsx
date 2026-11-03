/*
 * Job openings for students: search and filter, view details and eligibility, and apply
 * (GET /student/jobs, POST /student/jobs/{id}/apply). Shown as a tab of Opportunities.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { BadgeCheck, Briefcase, MapPin, Search } from "lucide-react";
import { get, post } from "../../api";
import {
  Button, Card, EmptyState, ErrorBox, Field, Modal, PageHeader, Pagination, Pill, Spinner, StatusPill, fmtDate,
  useApi, useToast,
} from "../../components/ui";

const TYPES = { full_time: "Full-time", internship: "Internship", part_time: "Part-time", contract: "Contract" };

export default function Jobs() {
  const toast = useToast();
  const [filters, setFilters] = useState({ q: "", location: "", job_type: "", skill: "", eligible_only: false });
  const [applied, setApplied] = useState(filters);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [cover, setCover] = useState("");
  const [busy, setBusy] = useState(false);
  const { data, error, loading, reload } = useApi(() => get("/student/jobs", { ...applied, page }), [applied, page]);

  const open = async (job) => {
    try { setSelected(await get(`/student/jobs/${job.id}`)); setCover(""); } catch (e) { toast(e.message, "error"); }
  };

  const apply = async () => {
    setBusy(true);
    try {
      await post(`/student/jobs/${selected.id}/apply`, { cover_letter: cover || null });
      toast("Application submitted!");
      setSelected(null);
      reload();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Placement opportunities" subtitle="Jobs and internships published by recruiters." actions={<Link to="/student/applications"><Button variant="secondary">My applications</Button></Link>} />
      <Card>
        <form className="grid gap-3 md:grid-cols-6" onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied(filters); }}>
          <div className="md:col-span-2"><input className="input" placeholder="Search title, company, keywords" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} aria-label="Search" /></div>
          <input className="input" placeholder="Location" value={filters.location} onChange={(e) => setFilters({ ...filters, location: e.target.value })} aria-label="Location" />
          <input className="input" placeholder="Skill" value={filters.skill} onChange={(e) => setFilters({ ...filters, skill: e.target.value })} aria-label="Skill" />
          <select className="input" value={filters.job_type} onChange={(e) => setFilters({ ...filters, job_type: e.target.value })} aria-label="Job type">
            <option value="">All types</option>{Object.entries(TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <Button type="submit"><Search size={16} /> Search</Button>
          <label className="flex items-center gap-2 text-sm md:col-span-6">
            <input type="checkbox" checked={filters.eligible_only} onChange={(e) => { const f = { ...filters, eligible_only: e.target.checked }; setFilters(f); setApplied(f); setPage(1); }} />
            Show only jobs I'm eligible for
          </label>
        </form>
      </Card>
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data && data.items.length === 0 && <Card><EmptyState icon={Briefcase} title="No jobs found" message="Try different filters, or check back later." /></Card>}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data?.items.map((j) => (
          <Card key={j.id} className="flex flex-col">
            <div className="flex items-start justify-between gap-2">
              <div><h3 className="font-semibold">{j.title}</h3><p className="text-sm text-slate-600">{j.company_name}
                {j.company_verified && <BadgeCheck size={14} className="ml-1 inline text-emerald-600" aria-label="Verified company" />}
                {j.industry && <span className="text-xs text-slate-400"> · {j.industry}</span>}</p></div>
              {j.application_status ? <StatusPill status={j.application_status} /> : j.eligible ? <Pill tone="green">eligible</Pill> : <Pill tone="gray">not eligible</Pill>}
            </div>
            <p className="mt-2 flex items-center gap-1 text-xs text-slate-500"><MapPin size={12} /> {j.location} · {TYPES[j.job_type]}{j.salary && ` · ${j.salary}`}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {j.required_skills.slice(0, 6).map((s) => <Pill key={s} tone={j.skill_match.includes(s) ? "green" : "gray"}>{s}</Pill>)}
            </div>
            <p className="mt-2 text-xs text-slate-500">You match {j.skill_match.length}/{j.required_skills.length + j.preferred_skills.length} skills{j.deadline && ` · apply by ${fmtDate(j.deadline)}`}</p>
            <div className="mt-auto pt-4"><Button size="sm" variant="secondary" onClick={() => open(j)}>View details</Button></div>
          </Card>
        ))}
      </div>
      {data && <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />}

      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected ? `${selected.title} · ${selected.company_name}` : ""} wide
        footer={selected && !selected.application ? <Button onClick={apply} loading={busy} disabled={!selected.eligible}>Apply now</Button> : null}>
        {selected && (
          <div className="space-y-4 text-sm">
            {selected.company_verified ? <Pill tone="green"><BadgeCheck size={12} className="mr-1" /> Verified company</Pill>
              : <Pill tone="gray">Company not yet verified by the placement office</Pill>}
            <p className="flex flex-wrap gap-3 text-slate-600"><span>📍 {selected.location}</span><span>💼 {TYPES[selected.job_type]}</span>
              <span>🧭 {selected.experience_years} yrs experience</span>{selected.salary && <span>💰 {selected.salary}</span>}{selected.deadline && <span>⏳ Apply by {fmtDate(selected.deadline)}</span>}</p>
            <p className="whitespace-pre-line">{selected.description}</p>
            <div><p className="font-medium">Required skills</p><div className="mt-1 flex flex-wrap gap-1">{selected.required_skills.map((s) => <Pill key={s} tone="brand">{s}</Pill>)}</div></div>
            {selected.preferred_skills.length > 0 && <div><p className="font-medium">Preferred skills</p><div className="mt-1 flex flex-wrap gap-1">{selected.preferred_skills.map((s) => <Pill key={s}>{s}</Pill>)}</div></div>}
            <div><p className="font-medium">Eligibility</p>
              <ul className="list-disc pl-5 text-slate-600">
                <li>Minimum CGPA: {selected.min_cgpa ?? "none"}</li>
                <li>Branches: {selected.eligible_branches.length ? selected.eligible_branches.join(", ") : "all"}</li>
                <li>Graduation years: {selected.graduation_years.length ? selected.graduation_years.join(", ") : "all"}</li>
              </ul>
            </div>
            {!selected.eligible && <div className="rounded-lg bg-red-50 p-3 text-red-800">You're not eligible: {selected.ineligible_reasons.join("; ")}. Update your <Link className="underline" to="/profile">profile</Link> if this is wrong.</div>}
            {selected.assessments.length > 0 && <p className="text-amber-700">This job has an assessment: {selected.assessments.map((a) => a.title).join(", ")} - it becomes available under Assessments after you apply.</p>}
            {selected.application ? <p className="rounded-lg bg-sky-50 p-3 text-sky-800">You applied on {fmtDate(selected.application.created_at)} - status: <b>{selected.application.status.replace(/_/g, " ")}</b></p> : selected.eligible && (
              <Field label="Cover note (optional)"><textarea className="input" rows={4} maxLength={4000} value={cover} onChange={(e) => setCover(e.target.value)} placeholder="Why are you a good fit?" /></Field>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
