/*
 * Mock-interview start page and history. Step 1 picks an interviewer (InterviewerPicker), step 2 sets
 * role, category, text/voice mode, question count and response mode; POST /student/interviews creates the session and
 * opens InterviewSession (text) or VoiceInterview (voice, /live).
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mic, Play } from "lucide-react";
import { get, post } from "../../api";
import { useAuth } from "../../auth";
import {
  Button, Card, ErrorBox, Field, Notice, PageHeader, Pagination, Pill, Spinner, StatusPill, Table, fmtDateTime,
  useApi, useToast,
} from "../../components/ui";
import { findInterviewer, useInterviewers } from "../../voice/useInterviewers";
import InterviewerPicker from "./InterviewerPicker";

const CATEGORIES = [
  { value: "mixed", label: "Mixed (technical + HR + behavioral)" },
  { value: "technical", label: "Technical" },
  { value: "hr", label: "HR" },
  { value: "behavioral", label: "Behavioral" },
  { value: "communication", label: "Communication" },
];

const RESPONSE_MODES = [
  { value: "fast", label: "Fast interview", help: "Short questions, minimal introduction, quick transitions. Detailed feedback comes at the end." },
  { value: "coaching", label: "Coaching", help: "Short spoken feedback and hints after each answer, English phrasing tips, and 50% more time to answer. Good for beginners." },
];

export default function Interviews() {
  const { user, ai } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [form, setForm] = useState({ job_role: user.profile?.target_role || "", category: "mixed", mode: "voice", question_count: 5, difficulty: "", subject: "", interviewer: "aria", response_mode: "fast" });
  const [busy, setBusy] = useState(false);
  const { data, error, loading, reload } = useApi(() => get("/student/interviews", { page }), [page]);
  const { list: interviewers, error: ivError } = useInterviewers();
  const [voiceStatus, setVoiceStatus] = useState(null);
  useEffect(() => { get("/voice/status").then(setVoiceStatus).catch(() => setVoiceStatus({})); }, []);
  const chosen = findInterviewer(interviewers, form.interviewer);
  const select = (p) => setForm((f) => ({ ...f, interviewer: p.id, category: p.categories[0], difficulty: p.recommended_difficulty }));

  const start = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      // Live voice: the first question is written in the background while the student goes through the
      // monitoring disclosure and device check, so starting the room is instant.
      const res = await post("/student/interviews", { ...form, question_count: Number(form.question_count), difficulty: form.difficulty || null,
        subject: form.subject.trim() || null, defer_first_question: form.mode === "voice" });
      if (res.notice) toast(res.notice, "error");
      navigate(`/student/interviews/${res.session.id}${form.mode === "voice" ? "/live" : ""}`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="AI mock interviews" subtitle="Practise with questions generated from your resume and target role. Questions get harder when you answer well and simpler when you struggle." />
      {ai && !ai.available && (
        <Notice>The local AI is not available right now{ai.setup_hint ? ` (${ai.setup_hint})` : ""}. Interviews will use the admin question bank, and answers will be evaluated once AI is available.</Notice>
      )}
      <Card title="1. Choose your interviewer">
        {ivError && <ErrorBox message={`Interviewers could not be loaded: ${ivError}`} />}
        {!interviewers && !ivError && <Spinner label="Loading interviewers…" />}
        {interviewers && <InterviewerPicker interviewers={interviewers} value={form.interviewer} onSelect={select} voiceStatus={voiceStatus} />}
      </Card>
      <Card title={`2. Interview settings${chosen ? ` - with ${chosen.name}` : ""}`}>
        <form onSubmit={start} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <Field label="Job role"><input className="input" required minLength={2} placeholder="e.g. Backend Developer" value={form.job_role} onChange={(e) => setForm({ ...form, job_role: e.target.value })} /></Field>
          </div>
          <Field label="Focus">
            <select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
              {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </Field>
          <Field label="Mode">
            <select className="input" value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
              <option value="text">Text (type answers)</option>
              <option value="voice">Live voice (AI interviewer)</option>
            </select>
          </Field>
          <Field label="Questions">
            <select className="input" value={form.question_count} onChange={(e) => setForm({ ...form, question_count: e.target.value })}>
              {[3, 5, 7, 10].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </Field>
          <Field label="Difficulty">
            <select className="input" value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })}>
              <option value="">Default</option><option value="easy">Easy (beginner)</option><option value="medium">Medium</option><option value="hard">Hard</option>
            </select>
          </Field>
          <div className="sm:col-span-2">
            <Field label="Technical subject (optional)"><input className="input" maxLength={100} placeholder="e.g. DBMS, Python, React" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} /></Field>
          </div>
          <fieldset className="sm:col-span-2 lg:col-span-4">
            <legend className="label">Response mode</legend>
            <div className="grid gap-3 sm:grid-cols-2">
              {RESPONSE_MODES.map((m) => (
                <label key={m.value} className={`flex cursor-pointer gap-3 rounded-lg border p-3 ${form.response_mode === m.value ? "border-brand-600 bg-brand-50" : "border-slate-200"}`}>
                  <input type="radio" name="response_mode" className="mt-1" value={m.value} checked={form.response_mode === m.value}
                    onChange={() => setForm({ ...form, response_mode: m.value })} />
                  <span><span className="font-medium">{m.label}</span><span className="block text-xs text-slate-500">{m.help}</span></span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="sm:col-span-2 lg:col-span-4">
            <Button type="submit" loading={busy}>{form.mode === "voice" ? <Mic size={16} /> : <Play size={16} />} Start interview{chosen ? ` with ${chosen.name}` : ""}</Button>
            {busy && <span className="ml-3 text-xs text-slate-500">{form.mode === "voice" ? "Opening the interview room…" : "Generating your first question with the local AI…"}</span>}
            {form.mode === "voice" && !busy && <span className="ml-3 text-xs text-slate-500">{chosen?.name || "The interviewer"} asks the questions aloud and you answer by speaking. Needs a microphone; speech is processed on this server.</span>}
            {form.mode === "text" && !busy && <span className="ml-3 text-xs text-slate-500">Text mode keeps {chosen?.name || "the interviewer"}'s questioning style and feedback, without the avatar.</span>}
          </div>
        </form>
      </Card>

      <Card title="Interview history" bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No interviews yet - start your first one above!"
              onRowClick={(r) => navigate(`/student/interviews/${r.id}${r.mode === "voice" && r.status === "in_progress" ? "/live" : ""}`)}
              columns={[
                { label: "Role", render: (r) => <span className="font-medium">{r.job_role}</span> },
                { label: "Interviewer", render: (r) => findInterviewer(interviewers, r.interviewer)?.name || r.interviewer },
                { label: "Focus", render: (r) => <span className="flex gap-1"><Pill tone="brand">{r.category}</Pill><Pill>{r.difficulty}</Pill></span> },
                { label: "Mode", key: "mode" },
                { label: "Answered", render: (r) => `${r.answered}/${r.planned_questions}` },
                { label: "Score", render: (r) => <span className="font-semibold">{r.overall_score ?? "—"}</span> },
                { label: "Status", render: (r) => <span className="flex gap-1"><StatusPill status={r.status} />{r.flagged && <Pill tone="red">flagged</Pill>}</span> },
                { label: "Date", render: (r) => fmtDateTime(r.created_at) },
              ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
