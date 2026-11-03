/* The mentor's assigned students (or all students with the view_all_students permission), with search. */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { get } from "../../api";
import { Card, ErrorBox, PageHeader, Pill, Spinner, StatusPill, Table, fmtDate, useApi } from "../../components/ui";

export default function MentorStudents() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [trend, setTrend] = useState("");
  const { data, error, loading, reload } = useApi(() => get("/mentor/students", { trend }), [trend]);
  const rows = (data || []).filter((s) => !q || `${s.full_name} ${s.email}`.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="space-y-6">
      <PageHeader title="My students" subtitle="Click a student to see their full progress, add feedback and set goals." />
      <div className="flex flex-wrap gap-3">
        <input className="input max-w-xs" placeholder="Search by name or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search students" />
        <select className="input max-w-xs" value={trend} onChange={(e) => setTrend(e.target.value)} aria-label="Filter by trend">
          <option value="">All trends</option><option value="improving">Improving</option><option value="stable">Stable</option>
          <option value="struggling">Struggling</option><option value="no_data">No activity</option>
        </select>
      </div>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <Table rows={rows} empty="No students assigned to you yet" onRowClick={(s) => navigate(`/mentor/students/${s.id}`)} columns={[
            { label: "Student", render: (s) => <div><p className="font-medium">{s.full_name}{!s.assigned && <Pill className="ml-2">not assigned</Pill>}</p><p className="text-xs text-slate-500">{s.branch || "—"}</p></div> },
            { label: "Trend", render: (s) => <StatusPill status={s.trend} /> },
            { label: "Interviews", render: (s) => `${s.interviews_completed} · avg ${s.interview_avg ?? "—"}` },
            { label: "English", render: (s) => `${s.english_minutes} min · ${s.english_avg ?? "—"}` },
            { label: "Assessments", render: (s) => s.assessment_avg != null ? `${s.assessment_avg}%` : "—" },
            { label: "Resume", render: (s) => s.resume_score ?? "—" },
            { label: "Last active", render: (s) => fmtDate(s.last_active_at) },
            { label: "Weak areas", render: (s) => <div className="flex max-w-xs flex-wrap gap-1">{s.weak_areas.map((w) => <Pill key={w} tone="red">{w}</Pill>)}</div> },
          ]} />
        )}
      </Card>
    </div>
  );
}
