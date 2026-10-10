import { useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardList } from "lucide-react";
import { get, post } from "../../api";
import { Button, Card, ConfirmButton, EmptyState, ErrorBox, PageHeader, Pill, Spinner, StatusPill, fmtDate, fmtDateTime, useApi, useToast } from "../../components/ui";

const FILTERS = ["", "applied", "shortlisted", "interview_scheduled", "selected", "rejected", "withdrawn"];

export default function Applications() {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const { data, error, loading, reload } = useApi(() => get("/student/applications", { status }), [status]);

  return (
    <div className="space-y-6">
      <PageHeader title="My applications" subtitle="Track application status, interview invitations and results." actions={<Link to="/student/jobs"><Button>Browse jobs</Button></Link>} />
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button key={f || "all"} onClick={() => setStatus(f)} className={`rounded-full px-3 py-1 text-sm ${status === f ? "bg-brand-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}>
            {f ? f.replace(/_/g, " ") : "All"}
          </button>
        ))}
      </div>
      {loading && <Spinner />}
      <ErrorBox message={error} onRetry={reload} />
      {data?.length === 0 && <Card><EmptyState icon={ClipboardList} title="No applications" message="Apply to jobs from the Jobs page." /></Card>}
      <div className="space-y-4">
        {data?.map((a) => (
          <Card key={a.id}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-semibold">{a.job?.title}</h3>
                <p className="text-sm text-slate-600">{a.job?.company_name} · {a.job?.location}</p>
                <p className="mt-1 text-xs text-slate-500">Applied {fmtDate(a.created_at)} {a.job?.status === "closed" && <Pill className="ml-1">job closed</Pill>}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusPill status={a.status} />
                {["applied", "shortlisted", "interview_scheduled"].includes(a.status) && (
                  <ConfirmButton size="sm" variant="ghost" message="Withdraw this application?" onConfirm={async () => {
                    try { await post(`/student/applications/${a.id}/withdraw`); toast("Application withdrawn"); reload(); } catch (e) { toast(e.message, "error"); }
                  }}>Withdraw</ConfirmButton>
                )}
              </div>
            </div>
            {a.status === "interview_scheduled" && a.interview_at && (
              <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">📅 Interview scheduled for <b>{fmtDateTime(a.interview_at)}</b></p>
            )}
            {a.status === "selected" && <p className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">🎉 Congratulations - you've been selected!</p>}
            <ol className="mt-4 flex flex-wrap gap-x-6 gap-y-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
              {a.history.map((h, i) => (
                <li key={i}><span className="font-medium text-slate-700">{h.to_status.replace(/_/g, " ")}</span> · {fmtDateTime(h.created_at)}{h.note && ` - ${h.note}`}</li>
              ))}
            </ol>
          </Card>
        ))}
      </div>
    </div>
  );
}
