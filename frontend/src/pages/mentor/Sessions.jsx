import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { del, get, patch, post } from "../../api";
import {
  Button, Card, ConfirmButton, ErrorBox, Field, Modal, PageHeader, Spinner, StatusPill, Table, fmtDateTime,
  fromLocalInput, toLocalInput, useApi, useToast,
} from "../../components/ui";

export default function MentorSessions() {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(null);
  const [busy, setBusy] = useState(false);
  const { data, error, loading, reload } = useApi(() => get("/mentor/sessions", { status }), [status]);
  const students = useApi(() => get("/mentor/students"));

  const save = async () => {
    setBusy(true);
    try {
      if (modal.id) {
        await patch(`/mentor/sessions/${modal.id}`, { scheduled_at: fromLocalInput(modal.scheduled_at), agenda: modal.agenda, meeting_link: modal.meeting_link || null, status: modal.status, outcome_notes: modal.outcome_notes || null });
      } else {
        if (!modal.student_id) throw new Error("Select a student");
        await post("/mentor/sessions", { student_id: Number(modal.student_id), scheduled_at: fromLocalInput(modal.scheduled_at), agenda: modal.agenda, meeting_link: modal.meeting_link || null });
      }
      toast("Session saved");
      setModal(null);
      reload();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Follow-up sessions" actions={<Button onClick={() => setModal({ student_id: "", scheduled_at: "", agenda: "", meeting_link: "" })}><Plus size={16} /> Schedule session</Button>} />
      <div className="flex gap-2">
        {["", "scheduled", "completed", "cancelled"].map((s) => (
          <button key={s || "all"} onClick={() => setStatus(s)} className={`rounded-full px-3 py-1 text-sm ${status === s ? "bg-brand-600 text-white" : "bg-white ring-1 ring-slate-200"}`}>{s || "All"}</button>
        ))}
      </div>
      <Card bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && <Table rows={data} empty="No sessions" columns={[
          { label: "Student", render: (r) => <Link className="font-medium text-brand-700 hover:underline" to={`/mentor/students/${r.student_id}`}>{r.student_name}</Link> },
          { label: "When", render: (r) => fmtDateTime(r.scheduled_at) },
          { label: "Agenda", key: "agenda" },
          { label: "Status", render: (r) => <StatusPill status={r.status} /> },
          { label: "Outcome", render: (r) => r.outcome_notes || "—" },
          { label: "", render: (r) => <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => setModal({ ...r, scheduled_at: toLocalInput(r.scheduled_at), meeting_link: r.meeting_link || "", outcome_notes: r.outcome_notes || "" })}>Update</Button>
            <ConfirmButton size="sm" variant="ghost" message="Delete this session?" onConfirm={async () => { try { await del(`/mentor/sessions/${r.id}`); reload(); } catch (e) { toast(e.message, "error"); } }}>Delete</ConfirmButton>
          </div> },
        ]} />}
      </Card>
      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.id ? "Update session" : "Schedule session"}
        footer={<><Button variant="secondary" onClick={() => setModal(null)}>Cancel</Button><Button loading={busy} onClick={save}>Save</Button></>}>
        {modal && (
          <div className="space-y-3">
            {!modal.id && (
              <Field label="Student">
                <select className="input" value={modal.student_id} onChange={(e) => setModal({ ...modal, student_id: e.target.value })}>
                  <option value="">Select a student</option>
                  {students.data?.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
                </select>
              </Field>
            )}
            <Field label="Date & time"><input className="input" type="datetime-local" value={modal.scheduled_at} onChange={(e) => setModal({ ...modal, scheduled_at: e.target.value })} /></Field>
            <Field label="Agenda"><textarea className="input" rows={3} value={modal.agenda} onChange={(e) => setModal({ ...modal, agenda: e.target.value })} /></Field>
            <Field label="Meeting link"><input className="input" value={modal.meeting_link} onChange={(e) => setModal({ ...modal, meeting_link: e.target.value })} /></Field>
            {modal.id && (
              <>
                <Field label="Status"><select className="input" value={modal.status} onChange={(e) => setModal({ ...modal, status: e.target.value })}><option>scheduled</option><option>completed</option><option>cancelled</option></select></Field>
                <Field label="Outcome notes"><textarea className="input" rows={3} value={modal.outcome_notes} onChange={(e) => setModal({ ...modal, outcome_notes: e.target.value })} /></Field>
              </>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
