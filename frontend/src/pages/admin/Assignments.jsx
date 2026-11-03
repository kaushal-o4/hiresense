/* Assign students to mentors and remove assignments (/admin/assignments). */

import { useState } from "react";
import { del, get, post } from "../../api";
import { Button, Card, ConfirmButton, ErrorBox, Field, PageHeader, Spinner, Table, fmtDate, useApi, useToast } from "../../components/ui";

export default function AdminAssignments() {
  const toast = useToast();
  const [mentorFilter, setMentorFilter] = useState("");
  const [form, setForm] = useState({ mentor_id: "", student_ids: [] });
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const mentors = useApi(() => get("/admin/users", { role: "mentor", status: "active", page_size: 100 }));
  const students = useApi(() => get("/admin/users", { role: "student", status: "active", page_size: 100 }));
  const { data, error, loading, reload } = useApi(() => get("/admin/assignments", { mentor_id: mentorFilter }), [mentorFilter]);

  const assign = async () => {
    setBusy(true);
    try {
      const res = await post("/admin/assignments", { mentor_id: Number(form.mentor_id), student_ids: form.student_ids });
      toast(`${res.assigned} student(s) assigned`);
      setForm({ ...form, student_ids: [] });
      reload();
      students.reload();
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  const visibleStudents = (students.data?.items || []).filter((s) => !search || `${s.full_name} ${s.email}`.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6">
      <PageHeader title="Mentor assignments" subtitle="Mentors can only see the students assigned to them (unless granted 'view all students')." />
      <Card title="Assign students to a mentor">
        <div className="grid gap-4 lg:grid-cols-3">
          <Field label="Mentor">
            <select className="input" value={form.mentor_id} onChange={(e) => setForm({ ...form, mentor_id: e.target.value })}>
              <option value="">Select mentor</option>
              {mentors.data?.items.map((m) => <option key={m.id} value={m.id}>{m.full_name} ({m.assigned_count} students)</option>)}
            </select>
          </Field>
          <div className="lg:col-span-2">
            <span className="label">Students ({form.student_ids.length} selected)</span>
            <input className="input mb-2" placeholder="Filter students" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Filter students" />
            <div className="max-h-56 overflow-y-auto rounded-lg border border-slate-200 p-2">
              {visibleStudents.length === 0 && <p className="p-2 text-sm text-slate-500">No active students.</p>}
              {visibleStudents.map((s) => (
                <label key={s.id} className="flex items-center gap-2 rounded px-2 py-1 text-sm hover:bg-slate-50">
                  <input type="checkbox" checked={form.student_ids.includes(s.id)}
                    onChange={(e) => setForm({ ...form, student_ids: e.target.checked ? [...form.student_ids, s.id] : form.student_ids.filter((x) => x !== s.id) })} />
                  {s.full_name} <span className="text-xs text-slate-500">{s.email}{s.mentors?.length ? ` · mentor: ${s.mentors.join(", ")}` : ""}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
        <Button className="mt-4" loading={busy} disabled={!form.mentor_id || form.student_ids.length === 0} onClick={assign}>Assign</Button>
      </Card>
      <Card title="Current assignments" bodyClass="" actions={
        <select className="input w-auto" value={mentorFilter} onChange={(e) => setMentorFilter(e.target.value)} aria-label="Filter by mentor">
          <option value="">All mentors</option>{mentors.data?.items.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
        </select>}>
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && <Table rows={data} empty="No assignments yet" columns={[
          { label: "Mentor", key: "mentor_name" }, { label: "Student", render: (a) => <span>{a.student_name} <span className="text-xs text-slate-500">{a.student_email}</span></span> },
          { label: "Since", render: (a) => fmtDate(a.created_at) },
          { label: "", render: (a) => <ConfirmButton size="sm" variant="ghost" message="Remove this assignment?" onConfirm={async () => { try { await del(`/admin/assignments/${a.id}`); toast("Assignment removed"); reload(); } catch (e) { toast(e.message, "error"); } }}>Remove</ConfirmButton> },
        ]} />}
      </Card>
    </div>
  );
}
