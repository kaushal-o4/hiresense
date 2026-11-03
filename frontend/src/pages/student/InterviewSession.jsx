/*
 * Text-mode interview and the results view for any finished interview. Loads the session,
 * submits typed answers (POST .../answer), finishes (POST .../complete) and retries scoring (POST .../retry-evaluation).
 * InterviewReport is reused by VoiceInterview and the mentor's student view.
 */

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, ChevronDown, ChevronRight, CircleDashed, Lightbulb, Mic, MicOff, RefreshCw, Send, Square, Volume2 } from "lucide-react";
import { del, get, post } from "../../api";
import { Subtitles, speak, usePrefs, useSpeaker, useSpeechToText } from "../../components/useSpeech";
import {
  Button, Card, ConfirmButton, ErrorBox, Notice, PageHeader, Pill, ScoreBar, Spinner, StatusPill, useApi, useToast,
} from "../../components/ui";
import { findInterviewer, useInterviewers } from "../../voice/useInterviewers";
import InterviewerFeedback from "./InterviewerFeedback";
import InterviewSetup from "./InterviewSetup";
import { MonitorBar } from "../../monitoring/MonitorBar";
import { useTypedMonitoring } from "../../monitoring/useTypedMonitoring";

export function SampleAnswer({ text }) {
  const [open, setOpen] = useState(false);
  const { speech_lang, speech_rate } = usePrefs();
  return (
    <div className="mt-4">
      <button className="inline-flex items-center gap-1 text-sm font-medium text-slate-700 hover:text-slate-900" onClick={() => setOpen(!open)} aria-expanded={open}>
        <ChevronRight size={15} className={`transition-transform ${open ? "rotate-90" : ""}`} /> {open ? "Hide" : "Show"} sample answer
      </button>
      {open && (
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-700">
          <p>{text}</p>
          <button className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-900" onClick={() => speak(text, speech_lang, speech_rate)}><Volume2 size={13} /> Listen</button>
        </div>
      )}
    </div>
  );
}

const NEXT_LABEL = { easy: "easier", medium: "medium", hard: "harder" };
const scoreTone = (v) => (v == null ? "gray" : v >= 75 ? "green" : v >= 50 ? "amber" : "red");
const scoreText = (v) => (v == null ? "text-slate-400" : v >= 75 ? "text-emerald-700" : v >= 50 ? "text-amber-700" : "text-rose-700");

function BulletList({ items, icon: Icon, iconClass }) {
  return (
    <ul className="space-y-2">
      {items.map((x, i) => (
        <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-slate-700">
          <Icon size={15} className={`mt-[3px] shrink-0 ${iconClass}`} aria-hidden />{x}
        </li>
      ))}
    </ul>
  );
}

export function AnswerDetails({ answer }) {
  const d = answer?.details;
  if (!d) return null;
  const groups = [
    ["What went well", d.strengths, CheckCircle2, "text-emerald-600"],
    ["Missing concepts", d.missing_concepts, CircleDashed, "text-rose-500"],
    ["How to improve", d.improvements, ArrowRight, "text-slate-500"],
  ].filter(([, items]) => items?.length);
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <ScoreBar label="Content (relevance, correctness, completeness)" value={d.content_score} />
        <ScoreBar label="Communication (clarity, language)" value={d.communication_score} />
      </div>
      {groups.length > 0 && (
        <div className={`grid gap-4 ${["", "", "md:grid-cols-2", "md:grid-cols-3"][groups.length]}`}>
          {groups.map(([title, items, Icon, cls]) => (
            <div key={title}><p className="eyebrow mb-2">{title}</p><BulletList items={items} icon={Icon} iconClass={cls} /></div>
          ))}
        </div>
      )}
      {d.rule_notes?.length > 0 && <p className="text-xs text-amber-700">{d.rule_notes.join(" ")}</p>}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        {d.next_difficulty && <span>Next question level: <b className="font-medium text-slate-700">{NEXT_LABEL[d.next_difficulty] || d.next_difficulty}</b></span>}
        {d.disclaimer && <span className="italic text-slate-400">{d.disclaimer}</span>}
      </div>
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

function Indicators({ r }) {
  const ind = r.indicators || {};
  const rows = [
    ["Answers given", ind.answers],
    ["Avg answer length", ind.avg_words_per_answer != null && `${ind.avg_words_per_answer} words`],
    ["Avg time per answer", ind.avg_seconds_to_answer != null && `${ind.avg_seconds_to_answer} s`],
    ["Speaking rate", ind.speaking_pace_wpm != null && `${Math.round(ind.speaking_pace_wpm)} wpm`],
    ["Filler words", ind.filler_words_per_100 != null && `${ind.filler_words_per_100} / 100 words`],
    ["Very short answers", ind.very_short_answers],
    ["Stopped at time limit", ind.stopped_at_time_limit || null],
  ].filter(([, v]) => v !== null && v !== undefined && v !== false);
  if (!rows.length) return null;
  return (
    <Card title="Response indicators">
      <dl className="divide-y divide-slate-100 text-sm">
        {rows.map(([k, v]) => <div key={k} className="flex justify-between gap-3 py-2 first:pt-0 last:pb-0"><dt className="text-slate-500">{k}</dt><dd className="num font-medium text-slate-900">{v}</dd></div>)}
      </dl>
      {ind.limitations && <p className="mt-3 text-[11px] leading-relaxed text-slate-400">{ind.limitations}</p>}
    </Card>
  );
}

function QuestionRow({ q, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);
  const s = q.answer?.score;
  return (
    <li className="border-b border-slate-200 last:border-b-0">
      <button className="flex w-full items-start gap-4 px-5 py-4 text-left transition-colors hover:bg-slate-50" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="num mt-0.5 w-6 shrink-0 text-xs font-medium text-slate-400">Q{q.position}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium leading-snug text-slate-900">{q.text}</span>
          <span className="mt-1.5 flex flex-wrap gap-1.5">
            <Pill>{q.question_type}</Pill>{q.difficulty && <Pill>{q.difficulty}</Pill>}{q.is_followup && <Pill tone="blue">follow-up</Pill>}
            {q.source === "question_bank" && <Pill tone="amber">question bank</Pill>}
          </span>
        </span>
        <span className={`num shrink-0 text-lg font-semibold ${scoreText(s)}`}>{s ?? "—"}</span>
        <ChevronDown size={16} className={`mt-1 shrink-0 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="px-5 pb-5 sm:pl-[3.75rem]">
          {q.preface && <p className="mb-2 text-sm italic text-slate-500">{q.preface}</p>}
          {q.answer ? (
            <>
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3.5">
                <p className="eyebrow mb-1">Your answer</p>
                <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">{q.answer.text}</p>
              </div>
              {q.answer.scores && (
                <div className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  {Object.entries(q.answer.scores).map(([k, v]) => <ScoreBar key={k} label={k.charAt(0).toUpperCase() + k.slice(1)} value={v} max={10} />)}
                </div>
              )}
              {q.answer.feedback ? <p className="mt-4 whitespace-pre-line text-sm leading-relaxed text-slate-700">{q.answer.feedback}</p>
                : q.answer.evaluation_status === "scored"
                  ? <p className="mt-4 text-sm text-slate-500">{q.answer.details?.feedback_status === "unavailable" ? "Detailed tips could not be generated - use Retry evaluation." : "Detailed tips are being written… (refresh in a moment)"}</p>
                  : <p className="mt-4 text-sm text-amber-700">Not evaluated yet (AI unavailable).</p>}
              <AnswerDetails answer={q.answer} />
              {q.answer.sample_answer && <SampleAnswer text={q.answer.sample_answer} />}
            </>
          ) : <p className="text-sm text-slate-400">Not answered</p>}
        </div>
      )}
    </li>
  );
}

export function InterviewReport({ session, onRetry, retrying }) {
  const r = session.report;
  const unevaluated = session.questions.some((q) => q.answer && !["completed", "scored"].includes(q.answer.evaluation_status));
  const score = session.overall_score;
  const level = score == null ? null : score >= 75 ? "Strong performance" : score >= 50 ? "Solid, with gaps" : "Needs more practice";
  const next = r?.recommended_next;
  const steps = [...(r?.suggestions || []), ...(r?.recommended_practice || [])];
  // open the weakest answer by default so the most useful feedback is visible first
  const weakest = session.questions.filter((q) => q.answer?.score != null).sort((a, b) => a.answer.score - b.answer.score)[0];
  return (
    <div className="space-y-6">
      {session.flagged && <Notice>This interview was flagged for review: {session.flag_reason}. Flagged interviews don't earn rewards.</Notice>}
      {(unevaluated || session.report_status !== "completed") && onRetry && (
        <Notice>
          <span className="flex flex-wrap items-center justify-between gap-3">
            Some answers or the final report have not been evaluated by AI yet.
            <Button size="sm" variant="secondary" loading={retrying} onClick={onRetry}><RefreshCw size={14} /> Retry evaluation</Button>
          </span>
        </Notice>
      )}

      <div className="card card-glow grid overflow-hidden lg:grid-cols-[1fr_360px]">
        <div className="p-6">
          <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
            <p className="num text-6xl font-semibold leading-none tracking-tight text-slate-900">{score ?? "—"}<span className="text-xl font-normal text-slate-400">/100</span></p>
            {level && <Pill dot tone={scoreTone(score)} className="mb-1.5">{level}</Pill>}
          </div>
          {r?.summary ? <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-slate-700">{r.summary}</p>
            : <p className="mt-5 text-sm text-slate-500">The written summary appears after AI evaluation.</p>}
        </div>
        <div className="border-t border-slate-200 bg-slate-50/60 p-6 lg:border-l lg:border-t-0">
          <h2 className="mb-4 text-[15px] font-semibold">Skill breakdown</h2>
          {r?.dimensions ? (
            <div className="space-y-3.5">
              {DIMENSIONS.map(([k, label, hint]) => (
                <div key={k} title={hint}>
                  {r.dimensions[k] == null
                    ? <div className="flex justify-between text-xs"><span className="text-slate-600">{label}</span><span className="text-slate-400">no {k === "technical_knowledge" ? "technical questions" : "scored answers"}</span></div>
                    : <ScoreBar label={label} value={r.dimensions[k]} />}
                </div>
              ))}
              <p className="pt-1 text-xs leading-relaxed text-slate-500">Technical knowledge is scored separately from English: grammar mistakes never lower it.</p>
            </div>
          ) : <p className="text-sm text-slate-500">Available after AI evaluation.</p>}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Strengths">{r?.strengths?.length ? <BulletList items={r.strengths} icon={CheckCircle2} iconClass="text-emerald-600" /> : <p className="text-sm text-slate-500">Available after AI evaluation.</p>}</Card>
        <Card title="Weaknesses">{r?.weaknesses?.length ? <BulletList items={r.weaknesses} icon={CircleDashed} iconClass="text-rose-500" /> : <p className="text-sm text-slate-500">Available after AI evaluation.</p>}</Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <Card title="Next steps" actions={<Link to="/student/interviews"><Button size="sm"><Mic size={14} /> Start next interview</Button></Link>}>
          {next && (
            <div className="mb-5 rounded-lg border border-slate-200 p-4">
              <p className="text-sm text-slate-900">Next: <b className="font-semibold">{next.difficulty}</b> difficulty with <b className="font-semibold">{INTERVIEWER_NAME[next.interviewer] || next.interviewer}</b></p>
              {next.reason && <p className="mt-0.5 text-sm text-slate-500">{next.reason}</p>}
            </div>
          )}
          {steps.length > 0 ? (
            <ol className="space-y-3">
              {steps.map((x, i) => (
                <li key={i} className="flex gap-3 text-sm leading-relaxed text-slate-700">
                  <span className="num flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-300 text-[11px] font-medium text-slate-500">{i + 1}</span>{x}
                </li>
              ))}
            </ol>
          ) : !next && <p className="text-sm text-slate-500">Available after AI evaluation.</p>}
          {r?.suggested_topics?.length > 0 && (
            <div className="mt-5 border-t border-slate-100 pt-4">
              <p className="eyebrow mb-2">Topics to revise</p>
              <div className="flex flex-wrap gap-1.5">{r.suggested_topics.map((t) => <Pill key={t} tone="amber">{t}</Pill>)}</div>
            </div>
          )}
        </Card>
        {r && <Indicators r={r} />}
      </div>

      <section className="card overflow-hidden">
        <div className="flex min-h-[52px] items-center justify-between border-b border-slate-200 px-5 py-2.5">
          <h2 className="text-[15px] font-semibold">Question-by-question feedback</h2>
          <span className="text-xs text-slate-500">{session.questions.length} questions</span>
        </div>
        <ul>{session.questions.map((q) => <QuestionRow key={q.id} q={q} defaultOpen={q.id === weakest?.id} />)}</ul>
      </section>
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
  // Monitoring is opt-in per feature and starts only after the setup screen's notice is accepted (see InterviewSetup).
  const mon = useTypedMonitoring(id);

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
      await mon.stop(); // interview over: camera off, last events sent
      const res = await post(`/student/interviews/${id}/complete`);
      setData(res.session);
      if (res.report_error) toast(res.report_error, "error");
      if (res.new_badges?.length) toast(`New badge: ${res.new_badges.join(", ")}`);
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
        subtitle={<span className="flex flex-wrap items-center gap-2"><Pill>{INTERVIEWER_NAME[session.interviewer] || session.interviewer}</Pill><Pill>{session.category}</Pill><Pill>{session.mode}</Pill><Pill>{session.difficulty}</Pill><StatusPill status={session.status} />
          {session.question_source !== "ai" && <Pill tone="amber">question bank</Pill>}</span>}
        actions={<>
          {session.mode === "voice" && session.status === "in_progress" && <Link to={`/student/interviews/${id}/live`}><Button><Mic size={16} /> Open live interviewer</Button></Link>}
          <Link to="/student/interviews"><Button variant="secondary">All interviews</Button></Link>
        </>} />

      {session.status === "in_progress" && !mon.features ? (
        <InterviewSetup typed session={session} persona={persona || { name: "your interviewer" }} camera={mon.camera} onStart={mon.begin} />
      ) : session.status === "in_progress" ? (
        <div className="space-y-4">
        <MonitorBar features={mon.features.withdrawn ? null : mon.features} status={mon.status} cameraOn={mon.camOn} cameraLost={mon.camLost}
          warning={mon.warning} onDismiss={mon.dismiss}
          onStop={!mon.features.withdrawn ? () => mon.stop({ withdraw: true }) : null} />
        {mon.camOn && (
          // Small self-view; the picture is analysed only in this browser and never recorded.
          <video ref={mon.video} autoPlay muted playsInline aria-label="Your camera (analysed only in this browser, not recorded)"
            className="fixed bottom-4 right-4 z-30 w-32 -scale-x-100 rounded-lg border-2 border-snow/70 shadow-lg sm:w-40" />
        )}
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
                  <Pill>{current.question_type}</Pill>{current.difficulty && <Pill>{current.difficulty}</Pill>}{current.is_followup && <Pill tone="blue">follow-up</Pill>}
                  <button className="ml-auto rounded p-1 text-slate-500 hover:bg-slate-100" onClick={() => speaker.speak(current.text)} aria-label="Read question aloud"><Volume2 size={18} /></button>
                </div>
                {current.preface && <p className="mt-3 flex gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700"><Lightbulb size={15} className="mt-0.5 shrink-0 text-amber-600" />{current.preface}</p>}
                <p className="mt-3 text-lg font-medium leading-snug text-slate-900">{current.text}</p>
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
                  <p className={`num text-4xl font-semibold tracking-tight ${scoreText(lastFeedback.score)}`}>{lastFeedback.score}<span className="text-sm font-normal text-slate-400">/100</span></p>
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
                onConfirm={async () => { try { await mon.stop(); await del(`/student/interviews/${id}`); navigate("/student/interviews"); } catch (e) { toast(e.message, "error"); } }}>
                <MicOff size={16} /> Abandon interview
              </ConfirmButton>
            </div>
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
