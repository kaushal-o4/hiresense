/* Candidate search for recruiters: filter students by skill, branch, CGPA, graduation year and interview score, optionally ranked against one of the recruiter's jobs. */

import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Search } from "lucide-react";
import { get } from "../../api";
import { Button, Card, ErrorBox, PageHeader, Pagination, Pill, Spinner, Table, useApi } from "../../components/ui";

export default function Candidates() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const init = { q: "", skill: "", branch: "", min_cgpa: "", graduation_year: "", min_interview_score: "", job_id: params.get("job_id") || "" };
  const [f, setF] = useState(init);
  const [applied, setApplied] = useState(init);
  const [page, setPage] = useState(1);
  const jobs = useApi(() => get("/recruiter/jobs", { page_size: 100 }));
  const { data, error, loading, reload } = useApi(() => get("/recruiter/candidates", { ...applied, page }), [applied, page]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <PageHeader title="Candidate search" subtitle="Search students by skills, qualifications and scores. Full reports are visible for students who applied to your jobs." />
      <Card>
        <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied(f); }}>
          <input className="input" placeholder="Name or college" value={f.q} onChange={set("q")} aria-label="Name or college" />
          <input className="input" placeholder="Skill (e.g. React)" value={f.skill} onChange={set("skill")} aria-label="Skill" />
          <input className="input" placeholder="Branch" value={f.branch} onChange={set("branch")} aria-label="Branch" />
          <input className="input" type="number" placeholder="Graduation year" value={f.graduation_year} onChange={set("graduation_year")} aria-label="Graduation year" />
          <input className="input" type="number" step="0.1" min="0" max="10" placeholder="Min CGPA" value={f.min_cgpa} onChange={set("min_cgpa")} aria-label="Minimum CGPA" />
          <input className="input" type="number" min="0" max="100" placeholder="Min interview score" value={f.min_interview_score} onChange={set("min_interview_score")} aria-label="Minimum interview score" />
          <select className="input" value={f.job_id} onChange={set("job_id")} aria-label="Rank against job">
            <option value="">Rank against a job (optional)</option>
            {jobs.data?.items.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}
          </select>
          <Button type="submit"><Search size={16} /> Search</Button>
        </form>
      </Card>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No candidates match these filters" onRowClick={(r) => navigate(`/recruiter/candidates/${r.id}`)}
              columns={[
                { label: "Name", render: (r) => <span className="font-medium">{r.full_name}{r.has_applied_to_you && <Pill tone="green" className="ml-2">applicant</Pill>}</span> },
                { label: "College / branch", render: (r) => <span className="text-xs">{r.college || "—"}<br />{r.branch || "—"} · {r.graduation_year || "—"}</span> },
                { label: "CGPA", render: (r) => r.cgpa ?? "—" },
                { label: "Interview avg", render: (r) => r.interview_avg ?? "—" },
                { label: "Skills", render: (r) => <div className="flex max-w-xs flex-wrap gap-1">{r.skills.slice(0, 5).map((s) => <Pill key={s}>{s}</Pill>)}</div> },
                ...(applied.job_id ? [
                  { label: "Skill match", render: (r) => `${r.skill_match}%` },
                  { label: "Eligible", render: (r) => r.eligible ? <Pill tone="green">yes</Pill> : <span title={r.ineligible_reasons.join("; ")}><Pill tone="red">no</Pill></span> },
                ] : []),
              ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
