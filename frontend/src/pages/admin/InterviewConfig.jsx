import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { del, get, post, put } from "../../api";
import { Button, Card, ConfirmButton, ErrorBox, Field, Modal, PageHeader, Pagination, Pill, Spinner, Table, Tabs, useApi, useToast } from "../../components/ui";

function Categories() {
  const toast = useToast();
  const [modal, setModal] = useState(null);
  const { data, error, loading, reload } = useApi(() => get("/admin/categories"));
  const save = async () => {
    try {
      const body = { code: modal.code, name: modal.name, description: modal.description || null, default_question_count: Number(modal.default_question_count), active: modal.active };
      if (modal.id) await put(`/admin/categories/${modal.id}`, body); else await post("/admin/categories", body);
      toast("Category saved"); setModal(null); reload();
    } catch (e) { toast(e.message, "error"); }
  };
  return (
    <Card title="Interview categories" bodyClass="" actions={<Button size="sm" onClick={() => setModal({ code: "", name: "", description: "", default_question_count: 5, active: true })}><Plus size={14} /> Add</Button>}>
      {loading && <Spinner />}<ErrorBox message={error} />
      {data && <Table rows={data} columns={[
        { label: "Code", render: (c) => <code>{c.code}</code> }, { label: "Name", key: "name" }, { label: "Description", key: "description" },
        { label: "Bank questions", key: "question_count" }, { label: "Status", render: (c) => <Pill tone={c.active ? "green" : "gray"}>{c.active ? "active" : "inactive"}</Pill> },
        { label: "", render: (c) => <Button size="sm" variant="ghost" onClick={() => setModal({ ...c, description: c.description || "" })}>Edit</Button> }]} />}
      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.id ? "Edit category" : "New category"} footer={<Button onClick={save}>Save</Button>}>
        {modal && <div className="space-y-3">
          <Field label="Code" hint="lowercase letters and underscores"><input className="input" disabled={!!modal.id} value={modal.code} onChange={(e) => setModal({ ...modal, code: e.target.value })} /></Field>
          <Field label="Name"><input className="input" value={modal.name} onChange={(e) => setModal({ ...modal, name: e.target.value })} /></Field>
          <Field label="Description"><textarea className="input" rows={2} value={modal.description} onChange={(e) => setModal({ ...modal, description: e.target.value })} /></Field>
          <Field label="Default number of questions"><input className="input" type="number" min="3" max="15" value={modal.default_question_count} onChange={(e) => setModal({ ...modal, default_question_count: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={modal.active} onChange={(e) => setModal({ ...modal, active: e.target.checked })} /> Active</label>
        </div>}
      </Modal>
    </Card>
  );
}

function QuestionBank() {
  const toast = useToast();
  const [cat, setCat] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(null);
  const cats = useApi(() => get("/admin/categories"));
  const { data, error, loading, reload } = useApi(() => get("/admin/questions", { category_id: cat, q, page }), [cat, page, q]);
  const save = async () => {
    try {
      const body = { category_id: Number(modal.category_id), question: modal.question, difficulty: modal.difficulty, role_tag: modal.role_tag || null, active: modal.active };
      if (modal.id) await put(`/admin/questions/${modal.id}`, body); else await post("/admin/questions", body);
      toast("Question saved"); setModal(null); reload();
    } catch (e) { toast(e.message, "error"); }
  };
  return (
    <Card title="Question bank" bodyClass="" actions={<>
      <input className="input w-48 py-1" placeholder="Search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search questions" />
      <select className="input w-auto py-1" value={cat} onChange={(e) => { setCat(e.target.value); setPage(1); }} aria-label="Category"><option value="">All categories</option>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
      <Button size="sm" onClick={() => setModal({ category_id: cats.data?.[0]?.id || "", question: "", difficulty: "medium", role_tag: "", active: true })}><Plus size={14} /> Add</Button></>}>
      <p className="px-5 pt-3 text-xs text-slate-500">Used as a fallback when AI is unavailable, so students can still practise.</p>
      {loading && <Spinner />}<ErrorBox message={error} />
      {data && <>
        <Table rows={data.items} columns={[
          { label: "Question", render: (r) => <span className="text-sm">{r.question}</span> }, { label: "Category", key: "category" },
          { label: "Difficulty", render: (r) => <Pill>{r.difficulty}</Pill> }, { label: "Role tag", render: (r) => r.role_tag || "—" },
          { label: "Status", render: (r) => <Pill tone={r.active ? "green" : "gray"}>{r.active ? "active" : "inactive"}</Pill> },
          { label: "", render: (r) => <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={() => setModal({ ...r, role_tag: r.role_tag || "" })}>Edit</Button>
            <ConfirmButton size="sm" variant="ghost" message="Delete this question?" onConfirm={async () => { try { await del(`/admin/questions/${r.id}`); reload(); } catch (e) { toast(e.message, "error"); } }}><Trash2 size={14} /></ConfirmButton></div> }]} />
        <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
      </>}
      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.id ? "Edit question" : "New question"} footer={<Button onClick={save}>Save</Button>}>
        {modal && <div className="space-y-3">
          <Field label="Category"><select className="input" value={modal.category_id} onChange={(e) => setModal({ ...modal, category_id: e.target.value })}>{cats.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label="Question"><textarea className="input" rows={3} value={modal.question} onChange={(e) => setModal({ ...modal, question: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Difficulty"><select className="input" value={modal.difficulty} onChange={(e) => setModal({ ...modal, difficulty: e.target.value })}><option>easy</option><option>medium</option><option>hard</option></select></Field>
            <Field label="Role tag (optional)"><input className="input" placeholder="e.g. web, data" value={modal.role_tag} onChange={(e) => setModal({ ...modal, role_tag: e.target.value })} /></Field>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={modal.active} onChange={(e) => setModal({ ...modal, active: e.target.checked })} /> Active</label>
        </div>}
      </Modal>
    </Card>
  );
}

function Rubrics() {
  const toast = useToast();
  const [modal, setModal] = useState(null);
  const { data, error, loading, reload } = useApi(() => get("/admin/rubrics"));
  const total = modal ? modal.criteria.reduce((s, c) => s + (Number(c.weight) || 0), 0) : 0;
  const save = async () => {
    try {
      const body = { name: modal.name, applies_to: modal.applies_to, active: modal.active, criteria: modal.criteria.map((c) => ({ ...c, weight: Number(c.weight) })) };
      if (modal.id) await put(`/admin/rubrics/${modal.id}`, body); else await post("/admin/rubrics", body);
      toast("Rubric saved"); setModal(null); reload();
    } catch (e) { toast(e.message, "error"); }
  };
  return (
    <Card title="Evaluation rubrics" actions={<Button size="sm" onClick={() => setModal({ name: "", applies_to: "interview", active: true, criteria: [{ name: "", weight: 0.25, description: "" }] })}><Plus size={14} /> Add</Button>}>
      <p className="mb-3 text-xs text-slate-500">The newest active rubric of each type is sent to the AI. Interview rubrics should use the criteria Relevance, Correctness, Clarity and Communication so their weights affect the score.</p>
      {loading && <Spinner />}<ErrorBox message={error} />
      <div className="grid gap-4 md:grid-cols-2">
        {data?.map((r) => (
          <div key={r.id} className="rounded-lg border border-slate-200 p-4">
            <div className="flex items-center justify-between"><p className="font-medium">{r.name}</p><div className="flex gap-1"><Pill tone="brand">{r.applies_to}</Pill><Pill tone={r.active ? "green" : "gray"}>{r.active ? "active" : "inactive"}</Pill></div></div>
            <ul className="mt-2 space-y-1 text-sm">{r.criteria.map((c) => <li key={c.name}><b>{c.name}</b> ({Math.round(c.weight * 100)}%) - <span className="text-slate-600">{c.description}</span></li>)}</ul>
            <Button size="sm" variant="ghost" className="mt-2" onClick={() => setModal(JSON.parse(JSON.stringify(r)))}>Edit</Button>
          </div>
        ))}
      </div>
      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.id ? "Edit rubric" : "New rubric"} wide footer={<Button onClick={save}>Save</Button>}>
        {modal && <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Name"><input className="input" value={modal.name} onChange={(e) => setModal({ ...modal, name: e.target.value })} /></Field>
            <Field label="Applies to"><select className="input" value={modal.applies_to} onChange={(e) => setModal({ ...modal, applies_to: e.target.value })}><option value="interview">Interview answers</option><option value="job_match">Job matching</option><option value="english">English</option></select></Field>
          </div>
          {modal.criteria.map((c, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-[1fr_6rem_2fr_auto]">
              <input className="input" placeholder="Criterion" value={c.name} onChange={(e) => setModal({ ...modal, criteria: modal.criteria.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)) })} aria-label="Criterion name" />
              <input className="input" type="number" step="0.05" min="0" max="1" value={c.weight} onChange={(e) => setModal({ ...modal, criteria: modal.criteria.map((x, j) => (j === i ? { ...x, weight: e.target.value } : x)) })} aria-label="Weight" />
              <input className="input" placeholder="Description" value={c.description} onChange={(e) => setModal({ ...modal, criteria: modal.criteria.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)) })} aria-label="Description" />
              <button className="text-slate-400 hover:text-red-600" onClick={() => setModal({ ...modal, criteria: modal.criteria.filter((_, j) => j !== i) })} aria-label="Remove criterion"><Trash2 size={16} /></button>
            </div>
          ))}
          <div className="flex items-center justify-between">
            <Button size="sm" variant="secondary" onClick={() => setModal({ ...modal, criteria: [...modal.criteria, { name: "", weight: 0, description: "" }] })}><Plus size={14} /> Criterion</Button>
            <span className={`text-sm ${Math.abs(total - 1) > 0.01 ? "text-red-600" : "text-emerald-700"}`}>Total weight: {total.toFixed(2)} (must be 1.00)</span>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={modal.active} onChange={(e) => setModal({ ...modal, active: e.target.checked })} /> Active</label>
        </div>}
      </Modal>
    </Card>
  );
}

export default function InterviewConfig() {
  const [tab, setTab] = useState("bank");
  return (
    <div>
      <PageHeader title="Interview & assessment setup" subtitle="Configure categories, question banks and evaluation rubrics used by the AI." />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "bank", label: "Question bank" }, { value: "categories", label: "Categories" }, { value: "rubrics", label: "Rubrics" }]} />
      {tab === "bank" && <QuestionBank />}
      {tab === "categories" && <Categories />}
      {tab === "rubrics" && <Rubrics />}
    </div>
  );
}
