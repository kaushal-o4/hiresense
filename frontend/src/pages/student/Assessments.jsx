import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ClipboardCheck, Code2, Play, RefreshCw, Timer } from "lucide-react";
import { get, post } from "../../api";
import { runJavaScript } from "../../components/codeRunner";
import {
  Button, Card, EmptyState, ErrorBox, Modal, Notice, PageHeader, Pill, Spinner, StatusPill, Table, Tabs, fmtDateTime,
  useApi, useToast,
} from "../../components/ui";

const CATEGORIES = [["", "All"], ["aptitude", "Aptitude"], ["technical", "Technical quizzes"], ["coding", "Coding tests"], ["english", "English"], ["other", "Other"]];

function CodingQuestion({ q, value, onChange }) {
  const [run, setRun] = useState(null);
  const [running, setRunning] = useState(false);
  const canRun = q.language === "javascript";
  const test = async () => {
    setRunning(true);
    setRun(await runJavaScript(value ?? q.starter_code, q.function_name, q.test_cases));
    setRunning(false);
  };
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <Pill tone="violet">{q.language}</Pill> function <code>{q.function_name}</code> · {q.marks} marks
      </div>
      <textarea className="input font-mono text-xs" rows={10} spellCheck={false} value={value ?? q.starter_code}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Tab") {
            e.preventDefault();
            const el = e.target;
            const v = el.value;
            const s = el.selectionStart;
            onChange(v.slice(0, s) + "  " + v.slice(el.selectionEnd));
            requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = s + 2; });
          }
        }} aria-label="Code editor" />
      {q.test_cases?.length > 0 && (
        <div className="rounded-lg bg-slate-50 p-2 text-xs">
          <p className="mb-1 font-semibold">Sample tests</p>
          {q.test_cases.map((t, i) => (
            <p key={i} className="font-mono">
              {q.function_name}({(t.input || []).map((x) => JSON.stringify(x)).join(", ")}) → {JSON.stringify(t.expected)}
              {run?.results?.[i] && (run.results[i].ok ? <span className="ml-2 text-emerald-700">✓ pass</span>
                : <span className="ml-2 text-red-700">✗ got {run.results[i].error || run.results[i].output}</span>)}
            </p>
          ))}
          {run?.error && <p className="mt-1 text-red-700">{run.error}</p>}
        </div>
      )}
      {canRun ? <Button size="sm" variant="secondary" loading={running} onClick={test}><Play size={14} /> Run sample tests in browser</Button>
        : <p className="text-xs text-slate-500">{q.language} code can't run in the browser; it is reviewed by AI after submission (not executed).</p>}
    </div>
  );
}

export function ReviewList({ review }) {
  return (
    <ol className="space-y-4">
      {review.map((q, i) => (
        <li key={i} className="rounded-lg border border-slate-200 p-4">
          <p className="font-medium">{i + 1}. {q.question}</p>
          {q.type === "mcq" ? (
            <>
              <ul className="mt-2 space-y-1 text-sm">
                {q.options.map((o, j) => (
                  <li key={j} className={`rounded px-2 py-1 ${j === q.answer_index ? "bg-emerald-50 text-emerald-800" : j === q.your_answer ? "bg-red-50 text-red-800" : ""}`}>
                    {o} {j === q.answer_index && "✓"} {j === q.your_answer && j !== q.answer_index && "(your answer)"}
                  </li>
                ))}
              </ul>
              {q.explanation && <p className="mt-2 text-xs text-slate-500">{q.explanation}</p>}
            </>
          ) : (
            <div className="mt-2 space-y-2 text-sm">
              <pre className="max-h-48 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{q.your_answer || "(no code submitted)"}</pre>
              {q.result.status === "pending" ? <Notice>Awaiting AI review: {q.result.feedback}</Notice> : (
                <>
                  <p><b>{q.result.marks}/{q.result.max_marks} marks</b> {q.result.method === "ai_review" && <Pill tone="brand" className="ml-1">AI-reviewed · code not executed</Pill>}</p>
                  <p className="text-slate-600">{q.result.feedback}</p>
                  {q.result.verdicts?.length > 0 && <ul className="text-xs">{q.result.verdicts.map((v) => <li key={v.case}>{v.likely_passes ? "✓" : "✗"} Test {v.case}: {v.reason}</li>)}</ul>}
                  {q.result.improved_solution && <details><summary className="cursor-pointer text-brand-600">Reference solution</summary><pre className="mt-1 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{q.result.improved_solution}</pre></details>}
                </>
              )}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

function ResultHeader({ r, total }) {
  if (r.evaluation_status === "pending") return <Notice>MCQs are graded; coding answers are awaiting AI review, so the final score isn't available yet.</Notice>;
  return (
    <div className="mb-6 flex flex-wrap items-center gap-4">
      <p className="text-4xl font-bold text-brand-700">{r.score}%</p>
      <Pill tone={r.passed ? "green" : "red"}>{r.passed ? "Passed" : "Not passed"}</Pill>
      <span className="text-sm text-slate-500">{r.marks_obtained}/{r.max_marks ?? total} marks · pass mark {r.pass_percent}%</span>
      {r.flagged && <Pill tone="amber">flagged: {r.flag_reason}</Pill>}
    </div>
  );
}

function TakeAssessment({ attempt, onDone }) {
  const a = attempt.assessment;
  const [answers, setAnswers] = useState(a.questions.map((q) => (q.type === "coding" ? q.starter_code : null)));
  const [left, setLeft] = useState(a.time_limit_minutes * 60);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const toast = useToast();
  const setAns = (i, v) => setAnswers((xs) => xs.map((x, k) => (k === i ? v : x)));

  const submit = async () => {
    setBusy(true);
    try {
      const res = await post(`/student/assessments/results/${attempt.result_id}/submit`, { answers });
      setResult(res);
      if (res.new_badges?.length) toast(`🏅 New badge: ${res.new_badges.join(", ")}`);
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  useEffect(() => {
    if (result) return;
    const t = setInterval(() => setLeft((x) => x - 1), 1000);
    return () => clearInterval(t);
  }, [result]);
  useEffect(() => {
    if (left === 0 && !result) { toast("Time is up - submitting your answers", "error"); submit(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left]);

  if (result) {
    return (
      <Card title={`Result: ${a.title}`} actions={<Button variant="secondary" onClick={onDone}>Back to assessments</Button>}>
        <ResultHeader r={result.result} total={a.total_marks} />
        <ReviewList review={result.review} />
      </Card>
    );
  }
  const mm = String(Math.max(0, Math.floor(left / 60))).padStart(2, "0");
  const ss = String(Math.max(0, left % 60)).padStart(2, "0");
  return (
    <Card title={a.title} actions={<span className={`flex items-center gap-1 text-sm font-semibold ${left < 60 ? "text-red-600" : "text-slate-700"}`}><Timer size={16} /> {mm}:{ss}</span>}>
      <ol className="space-y-6">
        {a.questions.map((q, i) => (
          <li key={i}>
            <p className="whitespace-pre-line font-medium">{i + 1}. {q.question} <span className="text-xs font-normal text-slate-400">({q.marks} mark{q.marks === 1 ? "" : "s"})</span></p>
            <div className="mt-2">
              {q.type === "coding" ? <CodingQuestion q={q} value={answers[i]} onChange={(v) => setAns(i, v)} /> : (
                <div className="space-y-1">
                  {q.options.map((o, j) => (
                    <label key={j} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${answers[i] === j ? "border-brand-500 bg-brand-50" : "border-slate-200 hover:bg-slate-50"}`}>
                      <input type="radio" name={`q${i}`} checked={answers[i] === j} onChange={() => setAns(i, j)} />
                      {o}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-6 flex items-center justify-between">
        <span className="text-sm text-slate-500">{a.questions.filter((q, i) => (q.type === "coding" ? answers[i] && answers[i] !== q.starter_code : answers[i] !== null)).length}/{a.questions.length} answered</span>
        <Button onClick={submit} loading={busy}>Submit</Button>
      </div>
    </Card>
  );
}

export default function StudentAssessments() {
  const toast = useToast();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") || "available");
  const [category, setCategory] = useState("");
  const [attempt, setAttempt] = useState(null);
  const [view, setView] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const available = useApi(() => get("/student/assessments", { category }), [category]);
  const results = useApi(() => get("/student/assessments/results"));

  const start = async (id) => {
    try { setAttempt(await post(`/student/assessments/${id}/start`)); } catch (e) { toast(e.message, "error"); }
  };
  const open = async (r) => { try { setView(await get(`/student/assessments/results/${r.id}`)); } catch (e) { toast(e.message, "error"); } };
  const evaluate = async (r) => {
    setBusyId(r.id);
    try { setView(await post(`/student/assessments/results/${r.id}/evaluate`)); results.reload(); toast("Evaluation complete"); }
    catch (e) { toast(e.message, "error"); } finally { setBusyId(null); }
  };

  if (attempt) return <TakeAssessment attempt={attempt} onDone={() => { setAttempt(null); available.reload(); results.reload(); }} />;

  return (
    <div>
      <PageHeader title="Assessments" subtitle="Aptitude tests, technical quizzes and coding tests set by the placement office and recruiters." />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "available", label: "Available" }, { value: "results", label: "My results" }]} />
      {tab === "available" ? (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            {CATEGORIES.map(([v, l]) => (
              <button key={v || "all"} onClick={() => setCategory(v)} className={`rounded-full px-3 py-1 text-sm ${category === v ? "bg-brand-600 text-white" : "bg-white ring-1 ring-slate-200"}`}>{l}</button>
            ))}
          </div>
          {available.loading && <Spinner />}
          <ErrorBox message={available.error} onRetry={available.reload} />
          {available.data?.length === 0 && <Card><EmptyState icon={ClipboardCheck} title="No assessments available" message="Check back later - new tests are added by the placement office." /></Card>}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {available.data?.map((a) => (
              <Card key={a.id} className={a.assignment?.status === "assigned" ? "ring-2 ring-amber-300" : ""}>
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-semibold">{a.has_coding && <Code2 size={16} className="mr-1 inline text-violet-600" />}{a.title}</h3>
                  <Pill tone="brand">{a.category}</Pill>
                </div>
                {a.assignment && <p className="mt-1 text-xs font-medium text-amber-700">{a.assignment.status === "assigned" ? `Assigned by recruiter${a.assignment.due_at ? ` · due ${fmtDateTime(a.assignment.due_at)}` : ""}` : "Assigned · completed ✓"}</p>}
                {a.job_title && <p className="mt-1 text-xs text-amber-700">For job: {a.job_title}</p>}
                <p className="mt-2 line-clamp-3 text-sm text-slate-600">{a.description || "No description."}</p>
                <p className="mt-3 text-xs text-slate-500">{a.question_count} questions · {a.total_marks} marks · {a.time_limit_minutes} min · {a.difficulty} · pass {a.pass_percent}%</p>
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-sm">{a.best_score != null ? <>Best: <b>{a.best_score}%</b></> : <span className="text-slate-400">Not attempted</span>}</span>
                  <Button size="sm" onClick={() => start(a.id)}>{a.best_score != null ? "Retake" : "Start"}</Button>
                </div>
              </Card>
            ))}
          </div>
          <div className="mt-4"><Notice tone="blue">Up to 3 attempts per assessment per day. Points are awarded the first time you pass each assessment. JavaScript coding answers can be self-tested in your browser; all code is graded by AI review on the server.</Notice></div>
        </>
      ) : (
        <Card bodyClass="">
          {results.loading && <Spinner />}
          <ErrorBox message={results.error} />
          {results.data && (
            <Table rows={results.data.items} empty="No results yet" onRowClick={open} columns={[
              { label: "Assessment", render: (r) => <span className="font-medium">{r.assessment_title}</span> },
              { label: "Category", render: (r) => <Pill>{r.category}</Pill> },
              { label: "Score", render: (r) => r.evaluation_status === "pending" ? <Pill tone="amber">pending review</Pill> : `${r.score}% (${r.marks_obtained}/${r.max_marks})` },
              { label: "Result", render: (r) => r.evaluation_status === "pending" ? (
                <Button size="sm" variant="secondary" loading={busyId === r.id} onClick={(e) => { e.stopPropagation(); evaluate(r); }}><RefreshCw size={12} /> Evaluate now</Button>
              ) : <span className="flex gap-1"><StatusPill status={r.passed ? "completed" : "failed"} />{r.flagged && <Pill tone="amber">flagged</Pill>}</span> },
              { label: "Submitted", render: (r) => fmtDateTime(r.submitted_at) },
            ]} />
          )}
        </Card>
      )}
      <Modal open={!!view} onClose={() => setView(null)} title={view?.result.assessment_title} wide>
        {view && <><ResultHeader r={view.result} /><ReviewList review={view.review} /></>}
      </Modal>
    </div>
  );
}
