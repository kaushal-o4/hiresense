/*
 * User management: list and filter, create staff accounts, approve recruiters, change role/status,
 * delete (/admin/users endpoints).
 */

import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { del, get, patch, post } from "../../api";
import { useAuth } from "../../auth";
import {
  Button, Card, ConfirmButton, ErrorBox, Field, Modal, PageHeader, Pagination, Pill, Spinner, StatusPill, Table,
  fmtDate, fmtDateTime, useApi, useToast,
} from "../../components/ui";

const NEW = { full_name: "", email: "", password: "", role: "mentor", company_name: "", department: "" };

export default function AdminUsers() {
  const { user: me } = useAuth();
  const toast = useToast();
  const [params] = useSearchParams();
  const [f, setF] = useState({ role: params.get("role") || "", status: params.get("status") || "", q: "" });
  const [applied, setApplied] = useState(f);
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [nu, setNu] = useState(NEW);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const { data, error, loading, reload } = useApi(() => get("/admin/users", { ...applied, page }), [applied, page]);

  const update = async (u, body, msg) => {
    try { await patch(`/admin/users/${u.id}`, body); toast(msg); reload(); if (detail?.id === u.id) openDetail(u); } catch (e) { toast(e.message, "error"); }
  };
  const openDetail = async (u) => { try { setDetail(await get(`/admin/users/${u.id}`)); } catch (e) { toast(e.message, "error"); } };
  const create = async () => {
    setBusy(true);
    try {
      await post("/admin/users", { ...nu, company_name: nu.company_name || null, department: nu.department || null });
      toast("User created");
      setCreateOpen(false);
      setNu(NEW);
      reload();
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="User management" actions={<Button onClick={() => setCreateOpen(true)}><Plus size={16} /> Create user</Button>} />
      <Card>
        <form className="grid gap-3 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); setPage(1); setApplied(f); }}>
          <input className="input" placeholder="Name or email" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} aria-label="Search" />
          <select className="input" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} aria-label="Role">
            <option value="">All roles</option><option value="student">Students</option><option value="recruiter">Recruiters</option><option value="mentor">Mentors</option><option value="admin">Admins</option>
          </select>
          <select className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} aria-label="Status">
            <option value="">Any status</option><option value="pending">Pending approval</option><option value="active">Active</option><option value="suspended">Suspended</option><option value="deactivated">Deactivated</option>
          </select>
          <Button type="submit"><Search size={16} /> Filter</Button>
        </form>
      </Card>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} columns={[
              { label: "User", render: (u) => <button className="text-left" onClick={() => openDetail(u)}><p className="font-medium text-brand-700 hover:underline">{u.full_name}</p><p className="text-xs text-slate-500">{u.email}</p></button> },
              { label: "Role", render: (u) => <Pill tone="brand">{u.role}</Pill> },
              { label: "Details", render: (u) => <span className="text-xs">{u.company_name || u.branch || (u.assigned_count != null ? `${u.assigned_count} students` : "")}{u.mentors?.length ? ` · mentor: ${u.mentors.join(", ")}` : ""}{u.permissions.length ? ` · ${u.permissions.join(", ")}` : ""}</span> },
              { label: "Status", render: (u) => <StatusPill status={u.status} /> },
              { label: "Last active", render: (u) => fmtDate(u.last_active_at) },
              { label: "Actions", render: (u) => u.id === me.id ? <span className="text-xs text-slate-400">you</span> : (
                <div className="flex flex-wrap gap-1">
                  {u.status === "pending" && <Button size="sm" variant="success" onClick={() => update(u, { status: "active" }, "Account approved")}>Approve</Button>}
                  {u.status === "active" && <ConfirmButton size="sm" variant="ghost" message={`Suspend ${u.full_name}? They will be signed out immediately.`} onConfirm={() => update(u, { status: "suspended" }, "Account suspended")}>Suspend</ConfirmButton>}
                  {["suspended", "deactivated"].includes(u.status) && <Button size="sm" variant="ghost" onClick={() => update(u, { status: "active" }, "Account reactivated")}>Reactivate</Button>}
                  {u.status !== "deactivated" && <ConfirmButton size="sm" variant="ghost" message={`Deactivate ${u.full_name}? Their records are kept.`} onConfirm={async () => { try { await del(`/admin/users/${u.id}`); toast("Account deactivated"); reload(); } catch (e) { toast(e.message, "error"); } }}>Deactivate</ConfirmButton>}
                </div>) },
            ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="Create user"
        footer={<><Button variant="secondary" onClick={() => setCreateOpen(false)}>Cancel</Button><Button loading={busy} onClick={create}>Create</Button></>}>
        <div className="space-y-3">
          <Field label="Role"><select className="input" value={nu.role} onChange={(e) => setNu({ ...nu, role: e.target.value })}><option value="mentor">Mentor</option><option value="recruiter">Recruiter</option><option value="student">Student</option><option value="admin">Admin</option></select></Field>
          <Field label="Full name"><input className="input" value={nu.full_name} onChange={(e) => setNu({ ...nu, full_name: e.target.value })} /></Field>
          <Field label="Email"><input className="input" type="email" value={nu.email} onChange={(e) => setNu({ ...nu, email: e.target.value })} /></Field>
          <Field label="Temporary password" hint="8+ characters with letters and numbers. Ask the user to change it after first login."><input className="input" type="text" value={nu.password} onChange={(e) => setNu({ ...nu, password: e.target.value })} /></Field>
          {nu.role === "recruiter" && <Field label="Company name"><input className="input" value={nu.company_name} onChange={(e) => setNu({ ...nu, company_name: e.target.value })} /></Field>}
          {nu.role === "mentor" && <Field label="Department"><input className="input" value={nu.department} onChange={(e) => setNu({ ...nu, department: e.target.value })} /></Field>}
        </div>
      </Modal>

      <Modal open={!!detail} onClose={() => setDetail(null)} title={detail?.full_name} wide>
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="grid gap-3 sm:grid-cols-2">
              <p><span className="text-slate-500">Email:</span> {detail.email}</p>
              <p><span className="text-slate-500">Joined:</span> {fmtDate(detail.created_at)}</p>
              <p><span className="text-slate-500">Last login:</span> {fmtDateTime(detail.last_login_at)}</p>
              <p><span className="text-slate-500">Status:</span> <StatusPill status={detail.status} /></p>
            </div>
            {detail.id !== me.id && (
              <div className="grid gap-3 rounded-lg bg-slate-50 p-3 sm:grid-cols-2">
                <Field label="Role">
                  <select className="input" value={detail.role} onChange={(e) => update(detail, { role: e.target.value }, "Role updated")}>
                    <option value="student">student</option><option value="recruiter">recruiter</option><option value="mentor">mentor</option><option value="admin">admin</option>
                  </select>
                </Field>
                {detail.role === "mentor" && (
                  <div className="flex flex-col gap-1 self-end pb-2">
                    {[["view_all_students", "Can view all students (not just assigned)"],
                      ["review_integrity", "Can review interview integrity (monitoring) events of students they can view"]].map(([perm, label]) => (
                      <label key={perm} className="flex items-center gap-2">
                        <input type="checkbox" checked={detail.permissions.includes(perm)}
                          onChange={(e) => update(detail, { permissions: e.target.checked ? [...new Set([...detail.permissions, perm])] : detail.permissions.filter((x) => x !== perm) }, "Permissions updated")} />
                        {label}
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}
            {detail.summary && (
              <div className="rounded-lg border border-slate-200 p-3">
                <p className="font-medium">Student summary</p>
                <p>Interviews: {detail.summary.interviews.completed} (avg {detail.summary.interviews.average_score ?? "—"}) · English: {detail.summary.english.minutes} min · Assessments: {detail.summary.assessments.taken} · Points: {detail.summary.rewards.points} · Trend: <StatusPill status={detail.summary.trend} /></p>
              </div>
            )}
            <div>
              <p className="mb-1 font-medium">Recent activity</p>
              {detail.recent_activity.length === 0 ? <p className="text-slate-500">No recorded activity.</p> : (
                <ul className="max-h-60 space-y-1 overflow-y-auto text-xs">{detail.recent_activity.map((a, i) => <li key={i}><span className="font-mono">{a.action}</span> · {fmtDateTime(a.created_at)}</li>)}</ul>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
