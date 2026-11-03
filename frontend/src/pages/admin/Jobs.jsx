/* All job postings across recruiters, with the option to close one. */

import { useState } from "react";
import { Search } from "lucide-react";
import { get, post } from "../../api";
import { Button, Card, ConfirmButton, ErrorBox, PageHeader, Pagination, Spinner, StatusPill, Table, fmtDate, useApi, useToast } from "../../components/ui";

export default function AdminJobs() {
  const toast = useToast();
  const [f, setF] = useState({ q: "", status: "" });
  const [applied, setApplied] = useState(f);
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi(() => get("/admin/jobs", { ...applied, page }), [applied, page]);
  return (
    <div className="space-y-6">
      <PageHeader title="Jobs & placement activity" subtitle="All job postings across recruiters." />
      <Card>
        <form className="flex flex-wrap gap-3" onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied(f); }}>
          <input className="input max-w-xs" placeholder="Title or company" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} aria-label="Search" />
          <select className="input max-w-[12rem]" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} aria-label="Status">
            <option value="">All statuses</option><option value="published">Published</option><option value="draft">Draft</option><option value="closed">Closed</option>
          </select>
          <Button type="submit"><Search size={16} /> Filter</Button>
        </form>
      </Card>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No jobs posted yet" columns={[
              { label: "Job", render: (j) => <div><p className="font-medium">{j.title}</p><p className="text-xs text-slate-500">{j.company_name} · {j.location}</p></div> },
              { label: "Recruiter", key: "recruiter_name" },
              { label: "Applications", key: "application_count" },
              { label: "Selected", key: "selected_count" },
              { label: "Status", render: (j) => <StatusPill status={j.status} /> },
              { label: "Posted", render: (j) => fmtDate(j.created_at) },
              { label: "", render: (j) => j.status !== "closed" && <ConfirmButton size="sm" variant="ghost" message="Close this job? The recruiter will be notified."
                onConfirm={async () => { try { await post(`/admin/jobs/${j.id}/close`); toast("Job closed"); reload(); } catch (e) { toast(e.message, "error"); } }}>Close</ConfirmButton> },
            ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
