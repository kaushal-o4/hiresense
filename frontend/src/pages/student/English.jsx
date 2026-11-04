/*
 * English conversation practice home: start a new conversation (topic, style, learning mode, text or
 * voice) with POST /student/english, and see companion stats and past sessions.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, HeartHandshake, MessageCircle, MessagesSquare } from "lucide-react";
import { get, post } from "../../api";
import MistakeProfile from "../../components/MistakeProfile";
import AIConsentGate from "../../components/AIConsent";
import { useAuth } from "../../auth";
import {
  Button, Card, ErrorBox, Field, Notice, PageHeader, Pagination, Spinner, StatCard, StatusPill, Table, fmtDateTime,
  useApi, useToast,
} from "../../components/ui";

const TOPICS = {
  free_talk: ["Video games", "Movies and shows", "Cricket and football", "Music", "Technology and AI", "Travel",
    "Food", "College life and friends", "Your hobbies and weekends", "Your career dreams"],
  interview: ["Tell me about yourself", "Strengths and weaknesses", "Your final-year project walkthrough",
    "Teamwork and conflict resolution", "Why should we hire you?", "HR round for a software developer role"],
};

// Used only if the server's mode list cannot be loaded; the server (services/english_companion.py) is the source.
const FALLBACK_MODES = [
  { id: "free_conversation", label: "Free conversation", description: "Just talk. Only the occasional important mistake is noted on screen." },
  { id: "english_learning", label: "English learning", description: "Gentle corrections as you go, then the conversation continues." },
  { id: "confidence", label: "Confidence building", description: "Short, easy questions, slower speech and example answers." },
];
const chip = (icon) => <span className="flex h-7 w-7 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-600">{icon}</span>;
const MODE_ICON = {
  free_conversation: chip(<MessageCircle size={15} />),
  english_learning: chip(<BookOpen size={15} />),
  confidence: chip(<HeartHandshake size={15} />),
};

export default function English() {
  const { ai } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [form, setForm] = useState({ topic: TOPICS.free_talk[0], mode: "voice", style: "free_talk", learning_mode: "free_conversation" });
  const setStyle = (style) => setForm((f) => ({ ...f, style, topic: TOPICS[f.style].includes(f.topic) ? TOPICS[style][0] : f.topic }));
  const [busy, setBusy] = useState(false);
  const { data: companion } = useApi(() => get("/student/english/companion"), []);
  const modes = companion?.modes || FALLBACK_MODES;
  const { data, error, loading, reload } = useApi(() => get("/student/english", { page }), [page]);
  const totalMinutes = data ? Math.round(data.items.reduce((s, x) => s + x.active_seconds, 0) / 60) : 0;

  const start = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const s = await post("/student/english", form);
      navigate(`/student/english/${s.id}`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="English communication practice" subtitle="Chat with Aria about anything you enjoy - games, films, cricket, technology, college life. She follows your interests, remembers what you said, and helps your English at the pace you choose." />
      <AIConsentGate action="practise English with Aria" />
      {ai && !ai.available && <Notice>English practice needs the local AI, which is not available right now{ai.setup_hint ? ` (${ai.setup_hint})` : ""}. Please try again later or tell your administrator.</Notice>}
      <Card title="Start a conversation">
        <form onSubmit={start} className="space-y-5">
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-slate-700">1. How would you like Aria to help?</legend>
            <div className="grid gap-3 md:grid-cols-3" role="radiogroup">
              {modes.map((m) => {
                const on = form.learning_mode === m.id;
                return (
                  <button key={m.id} type="button" role="radio" aria-checked={on} onClick={() => setForm({ ...form, learning_mode: m.id })}
                    className={`rounded-lg border p-3.5 text-left transition-colors ${on ? "border-brand-400/60 bg-brand-500/10 ring-1 ring-brand-400/40 shadow-glow" : "border-slate-200 bg-white hover:border-slate-300"}`}>
                    <span className="flex items-center gap-2 text-sm font-semibold">{MODE_ICON[m.id]} {m.label}</span>
                    <span className="mt-1 block text-xs text-slate-600">{m.description}</span>
                  </button>
                );
              })}
            </div>
          </fieldset>
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-slate-700">2. What would you like to talk about?</legend>
            <div className="mb-2 inline-flex rounded-lg border border-slate-200 p-0.5 text-sm" role="radiogroup" aria-label="Practice type">
              {[["free_talk", "Chat about anything"], ["interview", "Practise interview answers"]].map(([v, label]) => (
                <button key={v} type="button" role="radio" aria-checked={form.style === v} onClick={() => setStyle(v)}
                  className={`rounded-md px-3 py-1 ${form.style === v ? "bg-brand-500 text-snow shadow-glow" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              {TOPICS[form.style].map((t) => (
                <button key={t} type="button" onClick={() => setForm({ ...form, topic: t })} aria-pressed={form.topic === t}
                  className={`rounded-full border px-3 py-1 text-sm ${form.topic === t ? "border-brand-400/60 bg-brand-500 text-snow shadow-glow" : "border-slate-300 bg-white text-slate-700 hover:border-brand-400"}`}>{t}</button>
              ))}
            </div>
            <div className="mt-2 max-w-md">
              <Field label="…or type your own topic">
                <input className="input" required minLength={2} maxLength={200} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} />
              </Field>
            </div>
            {form.style === "free_talk" && <p className="mt-1 text-xs text-slate-500">This is just a starting point - you can switch topics whenever you like by saying “Can we talk about … instead?”</p>}
          </fieldset>
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-slate-700">3. Speak or type?</legend>
            <div className="flex flex-wrap items-center gap-3">
              <div className="inline-flex rounded-lg border border-slate-200 p-0.5 text-sm" role="radiogroup" aria-label="Input mode">
                {[["voice", "Speak with Aria (avatar)"], ["text", "Text chat"]].map(([v, label]) => (
                  <button key={v} type="button" role="radio" aria-checked={form.mode === v} onClick={() => setForm({ ...form, mode: v })}
                    className={`rounded-md px-3 py-1 ${form.mode === v ? "bg-brand-500 text-snow shadow-glow" : "text-slate-600 hover:bg-slate-100"}`}>{label}</button>
                ))}
              </div>
              <Button type="submit" loading={busy}><MessagesSquare size={16} /> Start practice</Button>
              {busy && <span className="text-xs text-slate-500">Aria is getting ready…</span>}
            </div>
          </fieldset>
        </form>
        <p className="mt-3 text-xs text-slate-500">Practice time is verified: only time spent actively replying (with real sentences) counts, and pauses longer than 2 minutes are not counted.</p>
      </Card>
      <div className="grid gap-4 sm:grid-cols-2">
        <StatCard label="Sessions (this page)" value={data?.total ?? "—"} icon={MessagesSquare} />
        <StatCard label="Verified practice (this page)" value={`${totalMinutes} min`} icon={MessagesSquare} tone="sky" />
      </div>
      <MistakeProfile />
      <Card title="Practice history" bodyClass="">
        {loading && <Spinner />}
        <div className="px-4"><ErrorBox message={error} onRetry={reload} /></div>
        {data && (
          <>
            <Table rows={data.items} empty="No practice sessions yet" onRowClick={(r) => navigate(`/student/english/${r.id}`)}
              columns={[
                { label: "Topic", render: (r) => <span className="font-medium">{r.topic}</span> },
                { label: "Mode", key: "mode" },
                { label: "Active time", render: (r) => `${Math.round(r.active_seconds / 60)} min` },
                { label: "Score", render: (r) => <span className="font-semibold">{r.overall_score ?? "—"}</span> },
                { label: "Status", render: (r) => <StatusPill status={r.status} /> },
                { label: "Date", render: (r) => fmtDateTime(r.created_at) },
              ]} />
            <Pagination page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
