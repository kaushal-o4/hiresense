import { useState } from "react";
import { get, post } from "../../api";
import { SimpleBar } from "../../components/charts";
import { Button, Card, ErrorBox, Field, Modal, Notice, PageHeader, Pagination, Pill, Spinner, Table, Tabs, fmtDateTime, useApi, useToast } from "../../components/ui";
import { InterviewReport } from "../student/InterviewSession";
import { IntegrityReview } from "../shared/IntegrityReview";

function Flagged() {
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => get("/admin/flagged"));
  const [review, setReview] = useState(null);
  const [view, setView] = useState(null);
  const submit = async (action) => {
    try {
      const res = await post(`/admin/flagged/${review.kind}/${review.id}`, { action, note: review.note || null });
      toast(action === "clear" ? "Flag cleared" : `Confirmed - ${res.points_revoked} points revoked`);
      setReview(null); reload();
    } catch (e) { toast(e.message, "error"); }
  };
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-6">
      <Notice tone="blue">Activities are flagged automatically (e.g. long answers submitted within seconds, identical answers, perfect tests finished impossibly fast). Flagged items never earn rewards. Confirm to revoke related points, or clear if legitimate.</Notice>
      <Card title="Flagged interviews" bodyClass="">
        <Table rows={data.interviews} empty="Nothing flagged" columns={[
          { label: "Student", key: "student_name" }, { label: "Interview", render: (r) => `${r.job_role} (${r.category})` },
          { label: "Reason", render: (r) => <span className="text-xs">{r.flag_reason}</span> }, { label: "Date", render: (r) => fmtDateTime(r.created_at) },
          { label: "", render: (r) => <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={async () => { try { setView(await get(`/admin/interviews/${r.id}`)); } catch (e) { toast(e.message, "error"); } }}>View</Button>
            <Button size="sm" onClick={() => setReview({ kind: "interview", id: r.id, note: "" })}>Review</Button></div> }]} />
      </Card>
      <Card title="Flagged assessment attempts" bodyClass="">
        <Table rows={data.assessment_results} empty="Nothing flagged" columns={[
          { label: "Student", key: "student_name" }, { label: "Assessment", key: "assessment_title" }, { label: "Score", render: (r) => `${r.score}%` },
          { label: "Reason", render: (r) => <span className="text-xs">{r.flag_reason}</span> },
          { label: "", render: (r) => <Button size="sm" onClick={() => setReview({ kind: "assessment", id: r.id, note: "" })}>Review</Button> }]} />
      </Card>
      <Modal open={!!review} onClose={() => setReview(null)} title="Review flagged activity"
        footer={<><Button variant="secondary" onClick={() => submit("clear")}>Clear flag</Button><Button variant="danger" onClick={() => submit("confirm")}>Confirm & revoke points</Button></>}>
        {review && <Field label="Review note (saved to audit log)"><textarea className="input" rows={3} value={review.note} onChange={(e) => setReview({ ...review, note: e.target.value })} /></Field>}
      </Modal>
      <Modal open={!!view} onClose={() => setView(null)} title={view ? `${view.job_role} · ${view.category}` : ""} wide>{view && <InterviewReport session={view} />}</Modal>
    </div>
  );
}

function AIUsage() {
  const [days, setDays] = useState(7);
  const { data, error, loading, reload } = useApi(() => get("/admin/ai-usage", { days }), [days]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const s = data.status;
  return (
    <div className="space-y-6">
      <Card title="AI service status" actions={<select className="input w-auto py-1" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Period"><option value={1}>Last 24 hours</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option></select>}>
        <div className="flex flex-wrap gap-6 text-sm">
          <span>Local model: <b>{s.model}</b> ({s.provider})</span>
          <span>Ollama: <b className={s.runtime_running ? "text-emerald-700" : "text-red-700"}>{s.runtime_running ? "running" : "not running"}</b></span>
          <span>Model ready: <b className={s.configured ? "text-emerald-700" : "text-red-700"}>{s.configured ? "yes" : "no"}</b></span>
          <span>Enabled in settings: <b>{s.enabled ? "yes" : "no"}</b></span>
          {s.embeddings && <span>Embeddings: <b>{s.embeddings.model}</b> ({s.embeddings.loaded ? "loaded" : s.embeddings.enabled ? "not loaded yet" : "disabled"})</span>}
        </div>
        {s.setup_hint && <p className="mt-2 text-sm text-red-700">{s.setup_hint}</p>}
        {s.embeddings?.error && <p className="mt-1 text-sm text-red-700">{s.embeddings.error}</p>}
      </Card>
      <Card title="Usage by feature" bodyClass="">
        <Table rows={data.by_feature} rowKey={(r) => `${r.feature}-${r.status}`} empty="No AI calls in this period" columns={[
          { label: "Feature", key: "feature" }, { label: "Result", render: (r) => <Pill tone={r.status === "success" ? "green" : "red"}>{r.status}</Pill> },
          { label: "Calls", key: "count" }, { label: "Avg latency", render: (r) => r.avg_latency_ms ? `${(r.avg_latency_ms / 1000).toFixed(1)} s` : "—" },
          { label: "Tokens in / out", render: (r) => `${r.input_tokens.toLocaleString()} / ${r.output_tokens.toLocaleString()}` }]} />
      </Card>
      <Card title="Answer score distribution (quality check)">
        <p className="mb-2 text-xs text-slate-500">A healthy evaluator produces a spread of scores. If nearly every answer lands in one bucket, review the rubric and recent transcripts.</p>
        <SimpleBar data={data.answer_score_distribution} dataKey="count" nameKey="range" />
      </Card>
      <Card title="Recent AI errors" bodyClass="">
        <Table rows={data.recent_errors} empty="No errors" columns={[
          { label: "When", render: (r) => fmtDateTime(r.created_at) }, { label: "Feature", key: "feature" },
          { label: "Status", render: (r) => <Pill tone="red">{r.status}</Pill> }, { label: "Error", render: (r) => <span className="text-xs">{r.error}</span> }]} />
      </Card>
    </div>
  );
}

function Errors() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi(() => get("/admin/errors", { page }), [page]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <Card title="Application errors" bodyClass="">
      <Table rows={data.items} empty="No application errors recorded 🎉" columns={[
        { label: "When", render: (r) => fmtDateTime(r.created_at) }, { label: "Request", render: (r) => <code className="text-xs">{r.method} {r.path}</code> },
        { label: "User", render: (r) => r.user_id ?? "—" },
        { label: "Error", render: (r) => <details><summary className="cursor-pointer text-xs">{r.error.split("\n").filter(Boolean).slice(-1)[0]}</summary><pre className="mt-2 max-w-xl overflow-x-auto whitespace-pre-wrap text-[10px]">{r.error}</pre></details> }]} />
      <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
    </Card>
  );
}

const ms = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(2)} s` : `${v} ms`);

function Performance() {
  const [hours, setHours] = useState(24);
  const { data, error, loading, reload } = useApi(() => get("/admin/performance", { hours }), [hours]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const groups = [
    ["Candidate waiting time (measured in the browser)", (m) => m.source === "client"],
    ["Interview turn (server)", (m) => m.source !== "client" && /^(turn|answer|prefetch)\./.test(m.metric)],
    ["Language model", (m) => m.metric.startsWith("llm.")],
    ["Speech (text-to-speech / transcription)", (m) => /^(tts|stt)\./.test(m.metric)],
  ];
  return (
    <div className="space-y-6">
      <Card title="Interview pipeline performance" actions={
        <div className="flex gap-2">
          <select className="input w-auto py-1" value={hours} onChange={(e) => setHours(Number(e.target.value))} aria-label="Period">
            <option value={1}>Last hour</option><option value={24}>Last 24 hours</option><option value={168}>Last 7 days</option>
          </select>
          <Button size="sm" variant="secondary" onClick={reload}>Refresh</Button>
        </div>}>
        <p className="text-sm text-slate-600">{data.note} Use the p95 column to find the step that makes candidates wait. For the language model, "generate_ms" vs "prompt_ms" vs "load_ms" shows whether writing, reading the prompt or loading the model is slow.</p>
      </Card>
      {groups.map(([title, test]) => {
        const rows = data.metrics.filter(test);
        if (!rows.length) return null;
        return (
          <Card key={title} title={title} bodyClass="">
            <Table rows={rows} rowKey={(r) => r.metric} columns={[
              { label: "Step", render: (r) => <div><code className="text-xs">{r.metric}</code><p className="text-xs text-slate-500">{r.description}</p></div> },
              { label: "Count", key: "count" },
              { label: "Failed", render: (r) => (r.failed ? <Pill tone="red">{r.failed}</Pill> : 0) },
              { label: "Average", render: (r) => ms(r.avg_ms) }, { label: "p50", render: (r) => ms(r.p50_ms) },
              { label: "p95", render: (r) => <b>{ms(r.p95_ms)}</b> }, { label: "Max", render: (r) => ms(r.max_ms) },
              { label: "Details (avg)", render: (r) => <span className="text-xs">{Object.entries(r.avg_details).map(([k, v]) => `${k} ${v}`).join(" · ")}</span> }]} />
          </Card>
        );
      })}
      {!data.metrics.length && <Notice>No measurements in this period yet. Run a live interview, then refresh.</Notice>}
    </div>
  );
}

export default function Monitoring() {
  const [tab, setTab] = useState("flagged");
  return (
    <div>
      <PageHeader title="AI & system monitoring" subtitle="Review suspicious activity, interview integrity signals, AI quality, performance and errors." />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "flagged", label: "Flagged activity" }, { value: "integrity", label: "Interview integrity" },
        { value: "ai", label: "AI usage & quality" }, { value: "perf", label: "Performance" }, { value: "errors", label: "Application errors" }]} />
      {tab === "flagged" && <Flagged />}
      {tab === "integrity" && <IntegrityReview />}
      {tab === "ai" && <AIUsage />}
      {tab === "perf" && <Performance />}
      {tab === "errors" && <Errors />}
    </div>
  );
}
