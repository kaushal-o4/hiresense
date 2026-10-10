import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, Mic, MicOff, RefreshCw, Send, Square, Volume2 } from "lucide-react";
import { del, get, post } from "../../api";
import { Subtitles, speak, usePrefs, useSpeaker, useSpeechToText } from "../../components/useSpeech";
import {
  Button, Card, ConfirmButton, ErrorBox, Notice, PageHeader, Pill, ScoreBar, Spinner, StatusPill, useApi, useToast,
} from "../../components/ui";
import { findInterviewer, useInterviewers } from "../../voice/useInterviewers";
import InterviewerFeedback from "./InterviewerFeedback";

export function SampleAnswer({ text }) {
  const [open, setOpen] = useState(false);
  const { speech_lang, speech_rate } = usePrefs();
  return (
    <div className="mt-3">
      <button className="text-sm font-medium text-brand-600 hover:underline" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} sample answer</button>
      {open && (
        <div className="mt-2 rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm">
          <p>{text}</p>
          <button className="mt-1 inline-flex items-center gap-1 text-xs text-brand-700" onClick={() => speak(text, speech_lang, speech_rate)}><Volume2 size={12} /> Listen</button>
        </div>
      )}
    </div>
  );
}

const NEXT_LABEL = { easy: "easier", medium: "medium", hard: "harder" };

export function AnswerDetails({ answer }) {
  const d = answer?.details;
  if (!d) return null;
  const Section = ({ title, items, tone }) => items?.length ? (
    <div><p className={`text-xs font-semibold ${tone}`}>{title}</p><ul className="list-disc pl-4 text-sm">{items.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
  ) : null;
  return (
    <div className="mt-3 space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <ScoreBar label="Content (relevance, correctness, completeness)" value={d.content_score} />
        <ScoreBar label="Communication (clarity, language)" value={d.communication_score} />
      </div>
      <Section title="What went well" items={d.strengths} tone="text-emerald-700" />
      <Section title="Missing concepts" items={d.missing_concepts} tone="text-red-700" />
      <Section title="How to improve" items={d.improvements} tone="text-brand-700" />
      {d.rule_notes?.length > 0 && <p className="text-xs text-amber-700">{d.rule_notes.join(" ")}</p>}
      {d.next_difficulty && <p className="text-xs text-slate-500">Next question level: <b>{NEXT_LABEL[d.next_difficulty] || d.next_difficulty}</b></p>}
      {d.disclaimer && <p className="text-[11px] italic text-slate-400">{d.disclaimer}</p>}
    </div>
  );
}

const DIMENSIONS = [
  ["technical_knowledge", "Technical knowledge", "Correctness and completeness on technical and project questions"],
  ["relevance", "Relevance", "Did the answers address the questions asked?"],
  ["answer_structure", "Answer structure", "Clear structure with specific examples"],
  ["communication_clarity", "Communication clarity", "Professional, concise language"],
];
const INTERVIEWER_NAME = { aria: "Aria (friendly)", victor: "Victor (strict technical)", marcus: "Marcus (stress)", elena: "Elena (HR)" };

function ReportBreakdown({ r }) {
  const ind = r.indicators || {};
  const rows = [
    ["Answers given", ind.answers],
    ["Average answer length", ind.avg_words_per_answer != null && `${ind.avg_words_per_answer} words`],
    ["Average time per answer", ind.avg_seconds_to_answer != null && `${ind.avg_seconds_to_answer} s`],
    ["Speaking rate while talking", ind.speaking_pace_wpm != null && `${Math.round(ind.speaking_pace_wpm)} words/min`],
    ["Filler words (um, uh…)", ind.filler_words_per_100 != null && `${ind.filler_words_per_100} per 100 words`],
    ["Very short answers (< 8 words)", ind.very_short_answers],
    ["Stopped at the time limit", ind.stopped_at_time_limit || null],
  ].filter(([, v]) => v !== null && v !== undefined && v !== false);
  const next = r.recommended_next;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Card title="Skill breakdown">
        <div className="space-y-3">
          {DIMENSIONS.map(([k, label, hint]) => (
            <div key={k} title={hint}>
              {r.dimensions[k] == null
                ? <p className="text-sm text-slate-500">{label}: <span className="text-xs">no {k === "technical_knowledge" ? "technical questions" : "scored answers"}</span></p>
                : <ScoreBar label={label} value={r.dimensions[k]} />}
            </div>
          ))}
        </div>
        <p className="mt-3 text-xs text-slate-500">Technical knowledge is scored separately from English: grammar mistakes never lower it.</p>
      </Card>
      <Card title="Response indicators">
        <dl className="space-y-1 text-sm">
          {rows.map(([k, v]) => <div key={k} className="flex justify-between gap-3"><dt className="text-slate-600">{k}</dt><dd className="font-medium">{v}</dd></div>)}
        </dl>
        {ind.limitations && <p className="mt-3 text-[11px] italic text-slate-400">{ind.limitations}</p>}
      </Card>
      <Card title="What to do next">
        {next && (
          <p className="text-sm">Next interview: <b>{next.difficulty}</b> difficulty with <b>{INTERVIEWER_NAME[next.interviewer] || next.interviewer}</b>.
            <span className="block text-slate-500">{next.reason}</span></p>
        )}
        {r.suggested_topics?.length > 0 && (
          <>
            <p className="mt-3 text-xs font-semibold uppercase text-slate-500">Topics to revise</p>
            <div className="mt-1 flex flex-wrap gap-1">{r.suggested_topics.map((t) => <Pill key={t} tone="amber">{t}</Pill>)}</div>
          </>
        )}
      </Card>
    </div>
  );
}

export function InterviewReport({ session, onRetry, retrying }) {
  const r = session.report;
  const unevaluated = session.questions.some((q) => q.answer && !["completed", "scored"].includes(q.answer.evaluation_status));
  return (
    <div className="space-y-6">
      {session.flagged && <Notice>This interview was flagged for review: {session.flag_reason}. Flagged interviews don't earn rewards.</Notice>}
      {(unevaluated || session.report_status !== "completed") && onRetry && (
        <Notice>
          Some answers or the final report have not been evaluated by AI yet.
          <Button size="sm" variant="secondary" className="ml-3" loading={retrying} onClick={onRetry}><RefreshCw size={14} /> Retry evaluation</Button>
        </Notice>
      )}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Overall score">
          <p className="text-5xl font-bold text-brand-700">{session.overall_score ?? "—"}<span className="text-lg text-slate-400">/100</span></p>
          <div className="mt-2"><ScoreBar value={session.overall_score} /></div>
          {r?.summary && <p className="mt-4 text-sm text-slate-600">{r.summary}</p>}
        </Card>
        <Card title="Strengths">{r?.strengths?.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{r.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul> : <p className="text-sm text-slate-500">Available after AI evaluation.</p>}</Card>
        <Card title="Weaknesses">{r?.weaknesses?.length ? <ul className="list-disc space-y-1 pl-5 text-sm">{r.weaknesses.map((s, i) => <li key={i}>{s}</li>)}</ul> : <p className="text-sm text-slate-500">Available after AI evaluation.</p>}</Card>
      </div>
      {r?.dimensions && <ReportBreakdown r={r} />}
      {r?.summary && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Improvement suggestions"><ul className="list-disc space-y-1 pl-5 text-sm">{r.suggestions?.map((s, i) => <li key={i}>{s}</li>)}</ul></Card>
          <Card title="Recommended practice"><ul className="list-disc space-y-1 pl-5 text-sm">{r.recommended_practice?.map((s, i) => <li key={i}>{s}</li>)}</ul></Card>
        </div>
      )}
      <Card title="Question-by-question feedback">
        <div className="space-y-5">
          {session.questions.map((q) => (
            <div key={q.id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-slate-400">Q{q.position}</span>
                <Pill tone="brand">{q.question_type}</Pill>{q.difficulty && <Pill>{q.difficulty}</Pill>}{q.is_followup && <Pill tone="violet">follow-up</Pill>}
                {q.source === "question_bank" && <Pill tone="amber">question bank</Pill>}
                {q.answer?.score != null && <span className="ml-auto text-sm font-semibold">{q.answer.score}/100</span>}
              </div>
              {q.preface && <p className="mt-2 text-sm italic text-slate-500">{q.preface}</p>}
              <p className="mt-2 font-medium">{q.text}</p>
              {q.answer ? (
                <>
                  <p className="mt-2 whitespace-pre-line rounded bg-slate-50 p-3 text-sm text-slate-700">{q.answer.text}</p>
                  {q.answer.scores && (
                    <div className="mt-3 grid gap-3 sm:grid-cols-4">
                      {Object.entries(q.answer.scores).map(([k, v]) => <ScoreBar key={k} label={k} value={v} max={10} />)}
                    </div>
                  )}
                  {q.answer.feedback ? <p className="mt-3 whitespace-pre-line text-sm text-slate-600">{q.answer.feedback}</p>
                    : q.answer.evaluation_status === "scored"
                      ? <p className="mt-3 text-sm text-slate-500">{q.answer.details?.feedback_status === "unavailable" ? "Detailed tips could not be generated - use Retry evaluation." : "Detailed tips are being written… (refresh in a moment)"}</p>
                      : <p className="mt-3 text-sm text-amber-700">Not evaluated yet (AI unavailable).</p>}
                  <AnswerDetails answer={q.answer} />
                  {q.answer.sample_answer && <SampleAnswer text={q.answer.sample_answer} />}
                </>
              ) : <p className="mt-2 text-sm text-slate-400">Not answered</p>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default function InterviewSession() {
  const { id } = useParams();
  const toast = useToast();
  const navigate = useNavigate();
  const { data: session, setData, error, loading, reload } = useApi(() => get(`/student/interviews/${id}`), [id]);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [lastFeedback, setLastFeedback] = useState(null);
  const shownAt = useRef(Date.now());
  const speech = useSpeechToText();
  const speaker = useSpeaker();
  const { list: interviewers } = useInterviewers();
  const persona = findInterviewer(interviewers, session?.interviewer);
  const current = session?.questions?.[session.questions.length - 1];
  const awaitingAnswer = session?.status === "in_progress" && current && !current.answer;
  const isVoice = session?.mode === "voice";

  useEffect(() => {
    if (!current) return;
    shownAt.current = Date.now();
    if (isVoice && awaitingAnswer) speaker.speak(current.text);
    return () => speaker.stop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.id]);

  useEffect(() => { if (isVoice) setAnswer(speech.transcript); }, [speech.transcript, isVoice]);

  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const submit = async () => {
    if (speech.listening) speech.stop();
    const text = answer.trim();
    if (!text) return toast("Please give an answer first", "error");
    setBusy(true);
    try {
      const res = await post(`/student/interviews/${id}/answer`, {
        question_id: current.id, answer: text, input_mode: isVoice ? "voice" : "text",
        response_seconds: Math.round((Date.now() - shownAt.current) / 1000),
      });
      const answered = res.session.questions.find((q) => q.id === current.id);
      setLastFeedback(answered?.answer);
      if (res.evaluation_error) toast(`Answer saved. ${res.evaluation_error}`, "error");
      setData(res.session);
      setAnswer("");
      speech.reset();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    setFinishing(true);
    try {
      const res = await post(`/student/interviews/${id}/complete`);
      setData(res.session);
      if (res.report_error) toast(res.report_error, "error");
      if (res.new_badges?.length) toast(`🏅 New badge: ${res.new_badges.join(", ")}`);
      else toast("Interview complete");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setFinishing(false);
    }
  };

  const retry = async () => {
    setRetrying(true);
    try {
      const res = await post(`/student/interviews/${id}/retry-evaluation`);
      setData(res.session);
      toast("Evaluation complete");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setRetrying(false);
    }
  };

  const answeredCount = session.questions.filter((q) => q.answer).length;
  const allDone = session.status === "in_progress" && answeredCount >= session.planned_questions;

  return (
    <div className="space-y-6">
      <Subtitles subtitle={speaker.subtitle} show={speaker.showSubtitles} />
      <PageHeader title={`${session.job_role} interview`}
        subtitle={<span className="flex flex-wrap items-center gap-2"><Pill tone="violet">{INTERVIEWER_NAME[session.interviewer] || session.interviewer}</Pill><Pill tone="brand">{session.category}</Pill><Pill>{session.mode}</Pill><Pill>{session.difficulty}</Pill><StatusPill status={session.status} />
          {session.question_source !== "ai" && <Pill tone="amber">question bank</Pill>}</span>}
        actions={<>
          {session.mode === "voice" && session.status === "in_progress" && <Link to={`/student/interviews/${id}/live`}><Button><Mic size={16} /> Open live interviewer</Button></Link>}
          <Link to="/student/interviews"><Button variant="secondary">All interviews</Button></Link>
        </>} />

      {session.status === "in_progress" ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div>
              <div className="mb-1 flex justify-between text-xs text-slate-500"><span>Progress</span><span>{answeredCount}/{session.planned_questions} answered</span></div>
              <ScoreBar value={(answeredCount / session.planned_questions) * 100} />
            </div>
            {awaitingAnswer ? (
              <Card>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-400">Question {current.position} of {session.planned_questions}</span>
                  <Pill tone="brand">{current.question_type}</Pill>{current.difficulty && <Pill>{current.difficulty}</Pill>}{current.is_followup && <Pill tone="violet">follow-up</Pill>}
                  <button className="ml-auto rounded p-1 text-slate-500 hover:bg-slate-100" onClick={() => speaker.speak(current.text)} aria-label="Read question aloud"><Volume2 size={18} /></button>
                </div>
                {current.preface && <p className="mt-3 rounded-lg border border-brand-100 bg-brand-50 p-3 text-sm text-slate-700">💡 {current.preface}</p>}
                <p className="mt-3 text-lg font-medium">{current.text}</p>
                <div className="mt-5">
                  {isVoice && (
                    <div className="mb-3 flex flex-wrap items-center gap-3">
                      {!speech.supported ? <Notice>Voice input isn't supported in this browser - type your answer instead.</Notice> : speech.listening ? (
                        <Button variant="danger" onClick={speech.stop}><Square size={16} /> Stop recording</Button>
                      ) : (
                        <Button onClick={() => { speaker.stop(); speech.start(); }}><Mic size={16} /> {answer ? "Continue speaking" : "Start speaking"}</Button>
                      )}
                      {speech.listening && <span className="flex items-center gap-2 text-sm text-red-600"><span className="h-2 w-2 animate-pulse rounded-full bg-red-600" /> Listening…</span>}
                      {speech.error && <span className="text-sm text-red-600">{speech.error}</span>}
                    </div>
                  )}
                  <label className="label" htmlFor="answer">{isVoice ? "Transcript (you can edit it)" : "Your answer"}</label>
                  <textarea id="answer" className="input" rows={7} value={answer + (speech.interim ? ` ${speech.interim}` : "")}
                    onChange={(e) => { setAnswer(e.target.value); if (isVoice) speech.setTranscript(e.target.value); }}
                    placeholder={isVoice ? "Your spoken answer will appear here…" : "Type your answer. Be specific and give examples."} maxLength={8000} />
                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-xs text-slate-500">{answer.trim() ? answer.trim().split(/\s+/).length : 0} words</span>
                    <Button onClick={submit} loading={busy} disabled={!answer.trim()}><Send size={16} /> {busy ? "Evaluating…" : "Submit answer"}</Button>
                  </div>
                  {busy && <p className="mt-2 text-xs text-slate-500">The local AI is scoring your answer and preparing the next question. This can take up to a minute.</p>}
                </div>
              </Card>
            ) : allDone ? (
              <Card><div className="flex flex-col items-center gap-3 py-6 text-center">
                <CheckCircle2 size={40} className="text-emerald-500" />
                <p className="font-medium">All questions answered!</p>
                <Button onClick={finish} loading={finishing}>Finish & get my report</Button>
              </div></Card>
            ) : <Spinner label="Preparing next question…" />}
          </div>
          <div className="space-y-4">
            <Card title="Feedback on last answer">
              {lastFeedback?.score != null ? (
                <>
                  <p className="text-3xl font-bold text-brand-700">{lastFeedback.score}<span className="text-sm text-slate-400">/100</span></p>
                  <div className="mt-3 space-y-2">{lastFeedback.scores && Object.entries(lastFeedback.scores).map(([k, v]) => <ScoreBar key={k} label={k} value={v} max={10} />)}</div>
                  {lastFeedback.feedback
                    ? <p className="mt-3 whitespace-pre-line text-sm text-slate-600">{lastFeedback.feedback}</p>
                    : <p className="mt-3 text-sm text-slate-500">Detailed tips are being written and will appear in your report.</p>}
                  <AnswerDetails answer={lastFeedback} />
                  {lastFeedback.sample_answer && <SampleAnswer text={lastFeedback.sample_answer} />}
                </>
              ) : <p className="text-sm text-slate-500">Submit an answer to see instant feedback here.</p>}
            </Card>
            <div className="flex flex-col gap-2">
              {answeredCount > 0 && !allDone && <Button variant="secondary" onClick={finish} loading={finishing}>Finish early & get report</Button>}
              <ConfirmButton variant="ghost" message="Abandon this interview? It won't count towards your progress."
                onConfirm={async () => { try { await del(`/student/interviews/${id}`); navigate("/student/interviews"); } catch (e) { toast(e.message, "error"); } }}>
                <MicOff size={16} /> Abandon interview
              </ConfirmButton>
            </div>
          </div>
        </div>
      ) : session.status === "completed" ? (
        <>
          {persona && session.report?.closing_remarks && <InterviewerFeedback session={session} persona={persona} />}
          <InterviewReport session={session} onRetry={retry} retrying={retrying} />
        </>
      ) : <Notice>This interview was abandoned.</Notice>}
    </div>
  );
}
