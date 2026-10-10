import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDown, ArrowUp, Mic, RefreshCw, RotateCcw, Send, Square, Target, Timer, Volume2 } from "lucide-react";
import { api, del, get, post } from "../../api";
import { Subtitles, useSpeaker, useSpeechToText } from "../../components/useSpeech";
import {
  Button, Card, ErrorBox, Notice, PageHeader, Pagination, Pill, ScoreBar, Spinner, Table, Tabs, fmtDateTime,
  useApi, useToast,
} from "../../components/ui";
import { MicRecorder } from "../../voice/recorder";

const WORD_STYLE = { correct: "bg-emerald-100 text-emerald-800", mispronounced: "bg-amber-100 text-amber-900", missed: "bg-red-100 text-red-800 line-through" };
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/**
 * Records one answer. Prefers the app's own recorder + local Whisper on the server (audio stays on this server and
 * the delivery measures get real timing); falls back to the browser's speech recognition, then to typing.
 */
function useAnswerInput(exerciseId) {
  const browser = useSpeechToText();
  const [voice, setVoice] = useState(null);
  const [text, setText] = useState("");
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState(null);
  const rec = useRef(null);
  if (!rec.current) rec.current = new MicRecorder();
  useEffect(() => { get("/voice/status").then(setVoice).catch(() => setVoice({})); }, []);
  useEffect(() => () => rec.current?.cancel(), []);
  useEffect(() => { if (browser.transcript) setText(browser.transcript); }, [browser.transcript]);
  const engine = voice == null ? null : voice.stt?.enabled ? "local" : browser.supported ? "browser" : "none";

  const start = async () => {
    setError(null);
    if (engine === "browser") { browser.reset(); browser.start(); setRecording(true); return; }
    try {
      await rec.current.start({ silenceMs: 8000, maxSeconds: 170, onLevel: setLevel, onSilence: () => stop(), onMax: () => stop() });
      setRecording(true);
    } catch (e) { setError(e.message); }
  };
  const stop = async () => {
    if (engine === "browser") { browser.stop(); setRecording(false); return; }
    if (!rec.current.active) return; // already stopped (silence timer and the Stop button can both fire)
    const clip = await rec.current.stop();
    setRecording(false); setLevel(0);
    if (!clip || clip.seconds < 0.5) return setError("That recording was too short. Press Record and try again.");
    const fd = new FormData();
    fd.append("audio", new Blob([clip.wav], { type: "audio/wav" }), "answer.wav");
    setTranscribing(true);
    try {
      const r = await api(`/student/exercises/${exerciseId}/transcribe`, { method: "POST", body: fd });
      if (!r.text) setError(r.note || "No words were recognised. Try again a little closer to the microphone.");
      else setText(r.text);
    } catch (e) { setError(`${e.message} You can type your answer instead.`); } finally { setTranscribing(false); }
  };
  const reset = () => { rec.current.cancel(); browser.reset(); setRecording(false); setText(""); setError(null); };
  return { engine, text, setText, recording, transcribing, level, error, start, stop, reset, confidence: browser.avgConfidence };
}

function Drill({ setup, onDone }) {
  const toast = useToast();
  const speaker = useSpeaker();
  const [ex, setEx] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const input = useAnswerInput(ex?.id);

  const begin = async (body) => {
    setBusy(true);
    try {
      if (ex && !result) await del(`/student/exercises/${ex.id}`).catch(() => {});
      const x = await post("/student/exercises", body);
      setEx(x); setResult(null); setElapsed(0); input.reset();
      if (x.kind === "speaking") speaker.speak(x.prompt);
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  // the parent remounts this component (key) for every new setup, so this runs once per drill
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { const { _n, ...body } = setup; begin(body); }, []);
  useEffect(() => {
    if (!ex || result) return undefined;
    const t = setInterval(() => setElapsed((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [ex, result]);

  const submit = async () => {
    if (input.recording) await input.stop();
    const transcript = input.text.trim();
    if (!transcript) return toast("Record (or type) your answer first", "error");
    setBusy(true);
    try {
      const res = await post(`/student/exercises/${ex.id}/submit`, { transcript, speech_confidence: input.engine === "browser" ? input.confidence() : null });
      setResult(res.exercise);
      onDone?.();
      if (res.evaluation_error) toast(res.evaluation_error, "error");
      if (res.new_badges?.length) toast(`🏅 New badge: ${res.new_badges.join(", ")}`);
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  if (!ex) return busy ? <Spinner label="Preparing your exercise…" /> : null;
  const d = result?.details;
  const target = ex.details?.target_seconds;
  const isRead = ex.kind === "pronunciation";
  return (
    <div className="space-y-4">
      <Subtitles subtitle={speaker.subtitle} show={speaker.showSubtitles} />
      <Card title={isRead ? "Read this aloud" : ex.details?.plan_title || "Answer aloud"}
        actions={!result && <span className="flex items-center gap-1 text-sm text-slate-500"><Timer size={14} /> {fmt(elapsed)}{target ? ` / target ${fmt(target)}` : ""}</span>}>
        <div className="flex items-start gap-3">
          <p className="flex-1 text-xl font-medium leading-relaxed">{ex.prompt}</p>
          <Button variant="secondary" size="sm" onClick={() => speaker.speak(ex.prompt)}><Volume2 size={14} /> Listen</Button>
        </div>
        {target && !result && (
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-200" aria-hidden>
            <div className={`h-full transition-all ${elapsed > target * 1.25 ? "bg-amber-500" : "bg-brand-500"}`} style={{ width: `${Math.min(100, (elapsed / target) * 100)}%` }} />
          </div>
        )}
        {!result && (
          <div className="mt-5 space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              {input.engine !== "none" && (input.recording
                ? <Button variant="danger" onClick={input.stop}><Square size={16} /> Stop</Button>
                : <Button onClick={input.start} disabled={busy || input.transcribing || input.engine == null}><Mic size={16} /> {input.text ? "Record again" : "Record"}</Button>)}
              {input.recording && input.engine === "local" && (
                <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-200" aria-label="Microphone level"><div className="h-full bg-emerald-500" style={{ width: `${Math.min(100, input.level * 900)}%` }} /></div>
              )}
              {input.recording && <span className="text-sm text-red-600">Recording… press Stop when you finish.</span>}
              {input.transcribing && <span className="text-sm text-slate-500">Writing down what you said…</span>}
              {input.text && !input.recording && <Button variant="ghost" size="sm" onClick={input.reset}><RotateCcw size={14} /> Clear</Button>}
            </div>
            {input.error && <p className="text-sm text-red-600">{input.error}</p>}
            <textarea className="input" rows={4} value={input.text} onChange={(e) => input.setText(e.target.value)}
              placeholder={input.engine === "none" ? "Voice input isn't available here - type your answer." : "Your words appear here. You can fix recognition mistakes before submitting."} />
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={submit} loading={busy} disabled={input.recording || input.transcribing}><Send size={16} /> Submit</Button>
              <span className="text-xs text-slate-500">
                {input.engine === "local" ? "Transcribed on this server; audio is not saved. Timing (pace, pauses) is measured only when you submit what was recorded."
                  : input.engine === "browser" ? "Using your browser's speech recognition (Chrome/Edge send audio to Google/Microsoft). Pace and pauses can't be measured this way."
                    : ""}
              </span>
            </div>
          </div>
        )}
        {result && (
          <div className="mt-5 space-y-5">
            {isRead && d && <ReadAloudResult d={d} result={result} speaker={speaker} />}
            {!isRead && d?.delivery && <Delivery f={d.delivery} />}
            {!isRead && (result.evaluation_status !== "completed"
              ? <Notice>Saved, but the AI's language feedback is unavailable right now. The delivery measures above don't need the AI.</Notice>
              : <LanguageFeedback d={d} score={result.score} speaker={speaker} />)}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => begin({ kind: ex.kind, retry_of: ex.id })} loading={busy}><RefreshCw size={16} /> Try the same one again</Button>
              <Button variant="secondary" onClick={() => begin({ kind: ex.kind, level: ex.level, drill: ex.details?.drill === "timed_answer" ? "timed_answer" : "standard" })}>Next exercise</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function Change({ label, v, better }) {
  if (!v || v.before == null || v.after == null || v.before === v.after) return null;
  const up = v.after > v.before;
  const good = better === "higher" ? up : !up;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${good ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"}`}>
      {up ? <ArrowUp size={12} /> : <ArrowDown size={12} />}{label}: {v.before} → {v.after}
    </span>
  );
}

function Delivery({ f }) {
  const cmp = f.compared_to_previous;
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">How you spoke <span className="font-normal text-slate-500">(measured, not AI)</span></p>
        {f.delivery_score != null && <p className="text-3xl font-bold text-brand-700">{f.delivery_score}<span className="text-sm text-slate-400">/100</span></p>}
      </div>
      <div className="mt-3 grid gap-3 text-sm sm:grid-cols-4">
        <Stat label="Pace" value={f.pace_wpm != null ? `${f.pace_wpm} wpm` : "—"} hint="100-165 is easy to follow" />
        <Stat label="Filler words" value={`${f.fillers}`} hint={f.filler_words?.length ? f.filler_words.join(", ") : "none heard"} />
        <Stat label="Long pauses" value={f.long_pauses != null ? `${f.long_pauses}` : "—"} hint={f.longest_pause_s != null ? `longest ${f.longest_pause_s}s` : "needs a recording"} />
        <Stat label="Length" value={f.duration_s != null ? fmt(f.duration_s) : `${f.words} words`} hint={f.target_seconds ? `target ${fmt(f.target_seconds)}` : ""} />
      </div>
      {cmp && Object.keys(cmp).length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="text-xs text-slate-500">Since your last try:</span>
          <Change label="score" v={cmp.delivery_score} better="higher" />
          <Change label="fillers/min" v={cmp.fillers_per_min} better="lower" />
          <Change label="long pauses" v={cmp.long_pauses} better="lower" />
          <Change label="pace" v={cmp.pace_wpm} better="higher" />
        </div>
      )}
      <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-700">{f.tips.map((t) => <li key={t}>{t}</li>)}</ul>
      <p className="mt-2 text-xs text-slate-400">{f.limitations}</p>
    </div>
  );
}

const Stat = ({ label, value, hint }) => (
  <div className="rounded-lg bg-slate-50 p-2"><p className="text-xs text-slate-500">{label}</p><p className="text-lg font-semibold">{value}</p>{hint && <p className="text-[11px] text-slate-400">{hint}</p>}</div>
);

function LanguageFeedback({ d, score, speaker }) {
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between"><p className="text-sm font-semibold">What you said <span className="font-normal text-slate-500">(AI feedback)</span></p>
        <p className="text-2xl font-bold text-slate-700">{score}<span className="text-sm text-slate-400">/100</span></p></div>
      <div className="grid gap-3 sm:grid-cols-5">
        {["grammar", "vocabulary", "fluency", "sentence_formation", "relevance"].map((k) => <ScoreBar key={k} label={k.replace("_", " ")} value={d[k]} max={10} />)}
      </div>
      <p className="text-sm">{d.feedback}</p>
      {d.corrections?.length > 0 && (
        <div className="space-y-1 rounded-lg bg-slate-50 p-3 text-sm">
          {d.corrections.map((c, i) => <p key={i}><span className="text-red-600 line-through">{c.original}</span> → <b className="text-emerald-700">{c.corrected}</b> <span className="text-xs text-slate-500">({c.explanation})</span></p>)}
        </div>
      )}
      {d.sample_answer && (
        <div className="rounded-lg border border-brand-200 bg-brand-50 p-3">
          <div className="flex items-center justify-between"><p className="text-xs font-semibold uppercase text-brand-700">Sample answer</p>
            <Button size="sm" variant="ghost" onClick={() => speaker.speak(d.sample_answer)}><Volume2 size={14} /> Listen</Button></div>
          <p className="mt-1 text-sm">{d.sample_answer}</p>
        </div>
      )}
    </div>
  );
}

function ReadAloudResult({ d, result, speaker }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-4">
        <p className="text-4xl font-bold text-brand-700">{result.score}<span className="text-sm text-slate-400">/100</span></p>
        <div className="flex flex-wrap gap-1.5">
          {d.words.map((w, i) => <span key={i} title={w.heard ? `heard "${w.heard}"` : w.status} className={`rounded px-1.5 py-0.5 text-base ${WORD_STYLE[w.status]}`}>{w.word}</span>)}
        </div>
      </div>
      {d.practice_words?.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span>Listen and repeat:</span>
          {d.practice_words.map((w) => <button key={w} onClick={() => speaker.speak(w)} className="rounded-full bg-brand-50 px-3 py-1 text-brand-700 hover:bg-brand-100"><Volume2 size={12} className="mr-1 inline" />{w}</button>)}
        </div>
      )}
      <p className="text-xs text-slate-500">This checks whether each word was recognised as you read it. It is a rough guide to clarity, not a full pronunciation assessment, and accent is never judged. You said: “{result.response_text}”</p>
    </>
  );
}

function Plan({ onStart, version }) {
  const { data, error, loading, reload } = useApi(() => get("/student/exercises/plan"), [version]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const b = data.based_on;
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Built from your own practice: {b.conversation_corrections} correction(s) from <Link className="text-brand-600 hover:underline" to="/student/english">conversations with Aria</Link>,
        {" "}{b.interview_reports} interview report(s) and {b.speaking_drills} recorded drill(s). It updates as you practise.
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        {data.items.map((i) => (
          <article key={i.id} className="flex flex-col rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-start gap-2"><Target size={18} className="mt-0.5 shrink-0 text-brand-600" /><h3 className="font-semibold">{i.title}</h3></div>
            <p className="mt-1 text-sm text-slate-600">{i.why}</p>
            {i.evidence?.length > 0 && <div className="mt-2 flex flex-wrap gap-1">{i.evidence.map((e) => <Pill key={e}>{e}</Pill>)}</div>}
            <div className="mt-auto pt-3">
              <Button size="sm" onClick={() => onStart({ kind: i.kind, plan_item: i.id })}>
                {i.kind === "pronunciation" ? "Read aloud" : i.target_seconds ? `Speak for ${Math.round(i.target_seconds)}s` : "Start"}
              </Button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function Picker({ kind, onStart }) {
  const [level, setLevel] = useState("easy");
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm"><span className="label">Level</span>
          <select className="input w-36" value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
          </select>
        </label>
        <Button onClick={() => onStart(kind === "speaking" ? { kind, level, drill: "timed_answer" } : { kind, level })}>Start</Button>
        <p className="text-sm text-slate-500">
          {kind === "speaking"
            ? "Speak for about a minute. You get measured delivery feedback (pace, filler words, pauses, length) plus AI feedback on your language and a sample answer. Then try the same prompt again and compare."
            : "Listen to the sentence, then read it aloud. Each word is checked against what was recognised."}
        </p>
      </div>
    </Card>
  );
}

function ExerciseHistory() {
  const [page, setPage] = useState(1);
  const { data, error, loading, reload } = useApi(() => get("/student/exercises", { page }), [page]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <Card bodyClass="">
      <Table rows={data.items} empty="No exercises yet" columns={[
        { label: "Type", render: (r) => <Pill tone={r.kind === "pronunciation" ? "violet" : "blue"}>{r.kind === "pronunciation" ? "read aloud" : "speaking"}</Pill> },
        { label: "Prompt", render: (r) => <span className="text-sm">{r.prompt}</span> },
        { label: "Delivery", render: (r) => r.details?.delivery?.delivery_score ?? "—" },
        { label: "Language", render: (r) => r.score ?? "—" },
        { label: "Date", render: (r) => fmtDateTime(r.completed_at) }]} />
      <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
    </Card>
  );
}

export default function EnglishLearning() {
  const [tab, setTab] = useState("plan");
  const [setup, setSetup] = useState(null);
  const [version, setVersion] = useState(0);
  const start = (body) => setSetup({ ...body, _n: Date.now() });
  const changeTab = (t) => { setTab(t); setSetup(null); };
  return (
    <div className="space-y-4">
      <PageHeader title="Speaking practice"
        subtitle="Short, focused drills chosen from your own conversations, interviews and resume. You get measured feedback on how you speak (pace, filler words, pauses) and AI feedback on what you say." />
      <Tabs value={tab} onChange={changeTab} tabs={[
        { value: "plan", label: "My practice plan" }, { value: "speaking", label: "Timed speaking" },
        { value: "pronunciation", label: "Read aloud" }, { value: "history", label: "History" }]} />
      {tab === "plan" && !setup && <Plan onStart={start} version={version} />}
      {(tab === "speaking" || tab === "pronunciation") && !setup && <Picker kind={tab} onStart={start} />}
      {tab !== "history" && setup && (
        <>
          <Button variant="ghost" size="sm" onClick={() => setSetup(null)}>← Back</Button>
          <Drill key={setup._n} setup={setup} onDone={() => setVersion((v) => v + 1)} />
        </>
      )}
      {tab === "history" && <ExerciseHistory />}
    </div>
  );
}
