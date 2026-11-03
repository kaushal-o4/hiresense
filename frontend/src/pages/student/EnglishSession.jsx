/*
 * One English conversation. Voice sessions in progress render EnglishAvatarSession; otherwise this
 * page shows the text chat (POST .../message), ending (POST .../end) and the final scores and feedback.
 */

import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, Send, Sparkles, Volume2 } from "lucide-react";
import { get, post } from "../../api";
import { streamPost } from "../../voice/turnStream";
import { SkillRadar } from "../../components/charts";
import { Subtitles, useSpeaker } from "../../components/useSpeech";
import { Button, Card, ErrorBox, Notice, PageHeader, Pill, ScoreBar, Spinner, StatusPill, useApi, useToast } from "../../components/ui";
import ConversationMemory, { LEARNING_MODE_LABEL } from "../../components/ConversationMemory";
import EnglishAvatarSession from "./EnglishAvatarSession";

const STYLE_LABEL = { free_talk: "free talk", interview: "interview practice" };

export default function EnglishSession() {
  const { id } = useParams();
  const { data: s, setData, error, loading, reload } = useApi(() => get(`/student/english/${id}`), [id]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  // Spoken sessions in progress are face to face with Aria; when they end, `setData` swaps in the report below.
  if (s.mode === "voice" && s.status === "in_progress") return <EnglishAvatarSession key={s.id} initial={s} onEnded={setData} />;
  return <EnglishChat s={s} setData={setData} />;
}

function EnglishChat({ s, setData }) {
  const toast = useToast();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState(null); // {student, draft} while a reply is streaming
  const [ending, setEnding] = useState(false);
  const speaker = useSpeaker();
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [s.messages?.length, pending?.draft?.length]);

  const send = async (e) => {
    e?.preventDefault();
    const content = text.trim();
    if (!content) return;
    setBusy(true);
    setPending({ student: content, draft: "" });
    try {
      // The reply appears while it is being written; the saved version (after the repeat/correction checks) replaces it.
      let saved = null;
      let failure = null;
      await streamPost(`/api/student/english/${s.id}/message/stream`, { content, input_mode: "text" }, {
        delta: ({ text: draft }) => setPending({ student: content, draft }),
        done: ({ session }) => { saved = session; },
        error: (e) => { failure = e.detail; },
      }, { interruptedMessage: "The connection was interrupted." });
      if (failure) throw new Error(typeof failure === "string" ? failure : "Something went wrong. Please try again.");
      setData(saved);
      setText("");
    } catch (err) {
      toast(err.message, "error");
      if (err.status === 0) { try { setData(await get(`/student/english/${s.id}`)); } catch { /* keep what is shown */ } }
    } finally {
      setPending(null);
      setBusy(false);
    }
  };

  const end = async () => {
    setEnding(true);
    try {
      const res = await post(`/student/english/${s.id}/end`);
      setData(res.session);
      if (res.evaluation_error) toast(res.evaluation_error, "error");
      const mins = Math.round(res.session.active_seconds / 60);
      if (res.session.active_seconds < res.min_active_seconds_for_points)
        toast(`Session saved (${mins} min active). Practise at least ${Math.round(res.min_active_seconds_for_points / 60)} active minutes to earn points.`);
      else toast(`Great work! ${mins} verified minutes of practice.`);
      if (res.new_badges?.length) toast(`New badge: ${res.new_badges.join(", ")}`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setEnding(false);
    }
  };

  const radar = s.scores ? Object.entries(s.scores).filter(([k]) => k !== "pronunciation_clarity")
    .map(([k, v]) => ({ label: k.replace(/_/g, " "), value: v })) : [];

  return (
    <div className="space-y-6">
      <Subtitles subtitle={speaker.subtitle} show={speaker.showSubtitles} />
      <PageHeader title={s.topic} subtitle={<span className="flex items-center gap-2"><Pill>{s.mode}</Pill><Pill>{STYLE_LABEL[s.style] || s.style}</Pill><Pill>{LEARNING_MODE_LABEL[s.learning_mode] || LEARNING_MODE_LABEL.free_conversation}</Pill><StatusPill status={s.status} /></span>}
        actions={<>
          <Link to="/student/english"><Button variant="secondary">All sessions</Button></Link>
          {s.status === "in_progress" && <Button variant="success" onClick={end} loading={ending}>End & get feedback</Button>}
        </>} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" bodyClass="flex h-[60vh] flex-col">
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {s.messages.map((m) => (
              <div key={m.id} className={`flex ${m.sender === "student" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${m.sender === "student" ? "bg-brand-500 text-snow shadow-glow" : "bg-slate-100 text-slate-800"}`}>
                  {m.meta?.encouragement && <p className="mb-1 flex items-center gap-1 text-xs font-medium text-emerald-700"><Sparkles size={12} /> {m.meta.encouragement}</p>}
                  <p className="whitespace-pre-line">{m.content}</p>
                  {m.sender === "ai" && <button className="mt-1 text-slate-400 hover:text-slate-700" onClick={() => speaker.speak(m.content)} aria-label="Read aloud"><Volume2 size={14} /></button>}
                  {m.corrections?.length > 0 && (
                    <div className="mt-2 space-y-1 rounded-lg bg-white/95 p-2 text-xs text-slate-700">
                      {m.corrections.map((c, i) => (
                        <p key={i}><span className="text-red-600 line-through">{c.original}</span> → <span className="font-medium text-emerald-700">{c.corrected}</span><br /><span className="text-slate-500">{c.explanation}</span></p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {pending && (
              <>
                <div className="flex justify-end"><div className="max-w-[85%] rounded-2xl bg-gradient-to-br from-brand-500 to-violet-500 text-snow px-4 py-2 text-sm"><p className="whitespace-pre-line">{pending.student}</p></div></div>
                {pending.draft
                  ? <div className="flex justify-start"><div className="max-w-[85%] rounded-2xl bg-slate-100 px-4 py-2 text-sm text-slate-800"><p className="whitespace-pre-line">{pending.draft}<span className="animate-pulse">▍</span></p></div></div>
                  : <div className="text-sm text-slate-400">Aria is typing…</div>}
              </>
            )}
            <div ref={bottomRef} />
          </div>
          {s.status === "in_progress" && (
            <form onSubmit={send} className="border-t border-slate-100 p-3">
              <div className="flex gap-2">
                <input className="input" value={text} onChange={(e) => setText(e.target.value)}
                  placeholder="Type your reply in full sentences…" maxLength={3000} aria-label="Your reply" />
                <Button type="submit" loading={busy} disabled={!text.trim()} aria-label="Send"><Send size={16} /></Button>
              </div>
            </form>
          )}
        </Card>
        <div className="space-y-4">
          <Card title="Session">
            <p className="text-sm text-slate-600">Verified active time</p>
            <p className="text-2xl font-semibold">{Math.round((s.status === "in_progress" ? s.live_active_seconds : s.active_seconds) / 60)} min</p>
            {s.status === "in_progress" && <p className="mt-1 text-xs text-slate-500">Updates after each reply; final when you end the session.</p>}
          </Card>
          {s.status === "in_progress" && <ConversationMemory memory={s.memory} learningMode={s.learning_mode} />}
          {s.status === "completed" && (
            s.evaluation_status === "completed" ? (
              <>
                <Card title="Your scores">
                  <p className="num text-4xl font-semibold tracking-tight text-slate-900">{s.overall_score}<span className="text-sm font-normal text-slate-400">/100</span></p>
                  <SkillRadar data={radar} height={220} />
                  <div className="space-y-2">{Object.entries(s.scores).map(([k, v]) => <ScoreBar key={k} label={k.replace(/_/g, " ")} value={v} max={10} />)}</div>
                  {s.scores.pronunciation_clarity != null && <p className="mt-2 text-xs text-slate-500">Pronunciation clarity is estimated from speech-recognition confidence.</p>}
                </Card>
                <Card title="Feedback">
                  <p className="text-sm leading-relaxed text-slate-700">{s.feedback.summary}</p>
                  <p className="eyebrow mb-2 mt-4">Strengths</p>
                  <ul className="space-y-1.5">{s.feedback.strengths.map((x, i) => <li key={i} className="flex gap-2 text-sm text-slate-700"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600" />{x}</li>)}</ul>
                  <p className="eyebrow mb-2 mt-4">Suggestions</p>
                  <ul className="space-y-1.5">{s.feedback.suggestions.map((x, i) => <li key={i} className="flex gap-2 text-sm text-slate-700"><ArrowRight size={15} className="mt-0.5 shrink-0 text-slate-400" />{x}</li>)}</ul>
                </Card>
              </>
            ) : <Notice>This session was not evaluated (no replies, or AI was unavailable).</Notice>
          )}
        </div>
      </div>
    </div>
  );
}
