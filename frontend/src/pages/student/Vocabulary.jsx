/*
 * English word list and spaced-repetition review (/student/english/vocabulary).
 * Cards come from Aria's corrections (what you said -> the better way to say it) or from words the student adds.
 * Review: see the front, try to recall, flip, then "I knew it" / "Not yet". The server moves the card between
 * Leitner boxes (GET /vocabulary/review, POST /vocabulary/{id}/review); "Not yet" cards are repeated once at the
 * end of the session on screen only.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Check, Plus, RotateCcw, Trash2, X } from "lucide-react";
import { del, get, post } from "../../api";
import {
  answer, boxLabel, currentCard, dueText, flip, isFinished, reviewProgress, startReview,
} from "../../english/vocab";
import {
  Button, Card, EmptyState, ErrorBox, Field, Modal, PageHeader, Pill, ScoreBar, Spinner, Tabs, useApi, useToast,
} from "../../components/ui";

const FILTERS = [
  { value: "all", label: "All" }, { value: "due", label: "Due" }, { value: "learning", label: "Learning" },
  { value: "learned", label: "Learned" }, { value: "mastered", label: "Mastered" },
];

function Review({ cards, onDone }) {
  const toast = useToast();
  const [s, setS] = useState(() => startReview(cards));
  const [busy, setBusy] = useState(false);
  const cur = currentCard(s);
  const prog = reviewProgress(s);

  const respond = async (knew) => {
    if (!cur) return;
    setBusy(true);
    try {
      let masteredNow = false;
      if (!cur.repeat) {
        const r = await post(`/student/english/vocabulary/${cur.card.id}/review`, { knew });
        masteredNow = r.mastered_now;
        (r.new_badges || []).forEach((b) => toast(`New badge: ${b}`, "success"));
      }
      setS(answer(s, knew, { masteredNow }).state);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setBusy(false);
    }
  };

  if (isFinished(s)) {
    return (
      <Card title="Review finished">
        <p className="text-sm text-slate-700">
          You knew <span className="num font-semibold">{s.knew}</span> of {prog.total}.
          {s.mastered > 0 && <> {s.mastered} card{s.mastered === 1 ? "" : "s"} mastered.</>}
          {s.notYet > 0 && " The ones you didn't know come back tomorrow."}
        </p>
        <div className="mt-4"><Button onClick={onDone}>Back to my words</Button></div>
      </Card>
    );
  }

  const { card } = cur;
  return (
    <Card title="Review" actions={<span className="num text-xs text-slate-500">{Math.min(prog.answered + 1, prog.total)}/{prog.total}{cur.repeat ? " · once more" : ""}</span>}>
      <ScoreBar value={prog.total ? Math.round((100 * prog.answered) / prog.total) : 0} />
      <button type="button" onClick={() => setS(flip(s))} aria-label={s.flipped ? "Show the front" : "Show the answer"}
        className="mt-4 flex min-h-[180px] w-full flex-col items-center justify-center rounded-xl border border-slate-200 bg-slate-100/40 p-6 text-center transition hover:border-brand-400/60">
        <span className="mb-2 text-xs uppercase tracking-wide text-slate-500">
          {s.flipped ? (card.kind === "correction" ? "Better way to say it" : "Meaning") : (card.kind === "correction" ? "You said" : "Word")}
        </span>
        <span className={`text-lg font-medium ${s.flipped ? "text-emerald-700" : "text-slate-900"}`}>{s.flipped ? card.back : card.front}</span>
        {s.flipped && card.explanation && <span className="mt-2 text-sm text-slate-600">{card.explanation}</span>}
        {!s.flipped && <span className="mt-3 text-xs text-slate-500">{card.kind === "correction" ? "How would you say this correctly? Then tap to check." : "What does it mean? Tap to check."}</span>}
      </button>
      <div className="mt-4 flex flex-wrap justify-center gap-3">
        {!s.flipped ? <Button variant="secondary" onClick={() => setS(flip(s))}><RotateCcw size={15} /> Show answer</Button> : (
          <>
            <Button variant="secondary" loading={busy} onClick={() => respond(false)}><X size={15} /> Not yet</Button>
            <Button variant="success" loading={busy} onClick={() => respond(true)}><Check size={15} /> I knew it</Button>
          </>
        )}
      </div>
    </Card>
  );
}

export default function Vocabulary() {
  const toast = useToast();
  const [filter, setFilter] = useState("all");
  const [reviewCards, setReviewCards] = useState(null);
  const [adding, setAdding] = useState(null);
  const [busy, setBusy] = useState(false);
  const { data, error, loading, reload } = useApi(() => get("/student/english/vocabulary", { filter }), [filter]);

  const beginReview = async () => {
    setBusy(true);
    try {
      const q = await get("/student/english/vocabulary/review");
      if (!q.items.length) toast("Nothing is due right now. Come back later.", "info");
      else setReviewCards(q.items);
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true);
    try {
      await post("/student/english/vocabulary", adding);
      setAdding(null);
      reload();
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };
  const remove = async (id) => {
    try { await del(`/student/english/vocabulary/${id}`); reload(); } catch (e) { toast(e.message, "error"); }
  };

  const c = data?.counts;
  return (
    <div className="space-y-6">
      <PageHeader title="My words" subtitle="Phrases from Aria's corrections and words you add. Review them a little every day: each card comes back just before you are likely to forget it."
        actions={<Link to="/student/english" className="inline-flex items-center gap-1 text-sm text-brand-600 hover:underline"><ArrowLeft size={14} /> English practice</Link>} />
      {reviewCards ? <Review cards={reviewCards} onDone={() => { setReviewCards(null); reload(); }} /> : (
        <>
          <Card title="Review" actions={<Button size="sm" variant="secondary" onClick={() => setAdding({ word: "", meaning: "", example: "" })}><Plus size={14} /> Add a word</Button>}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="text-sm text-slate-700">
                {c ? <><span className="num font-semibold text-slate-900">{c.due}</span> due now · {c.total} in your list · {c.learned} learned · {c.mastered} mastered</> : "…"}
              </div>
              <Button onClick={beginReview} loading={busy} disabled={!c?.due}>Start review{c?.due ? ` (${Math.min(c.due, 20)})` : ""}</Button>
            </div>
            {c && c.total > 0 && (
              <div className="mt-4 grid grid-cols-5 gap-2 text-center text-xs" aria-label="Cards per box">
                {[1, 2, 3, 4, 5].map((b) => (
                  <div key={b} className="rounded-lg border border-slate-200 p-2">
                    <p className="num text-base font-semibold text-slate-900">{c.boxes[String(b)]}</p>
                    <p className="text-slate-500">Box {b}</p>
                    <p className="text-[11px] text-slate-500">every {data.intervals_days[String(b)]} day{data.intervals_days[String(b)] === 1 ? "" : "s"}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
          <div>
            <Tabs tabs={FILTERS} value={filter} onChange={setFilter} />
            {loading && <Spinner />}
            <ErrorBox message={error} onRetry={reload} />
            {data && data.items.length === 0 && (
              <EmptyState title="No words here yet" message="Have a conversation with Aria in English learning mode: her corrections are added here automatically." />
            )}
            {data && data.items.length > 0 && (
              <ul className="grid gap-3 md:grid-cols-2">
                {data.items.map((i) => (
                  <li key={i.id} className="card flex items-start justify-between gap-3 p-4">
                    <div className="min-w-0 text-sm">
                      {i.kind === "correction"
                        ? <p><span className="text-red-600 line-through">{i.front}</span> → <span className="font-medium text-emerald-700">{i.back}</span></p>
                        : <p><span className="font-medium text-slate-900">{i.front}</span> — <span className="text-slate-700">{i.back}</span></p>}
                      {i.explanation && <p className="mt-1 text-xs text-slate-500">{i.explanation}</p>}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <Pill tone={i.mastered ? "green" : i.learned ? "teal" : "gray"} dot>{boxLabel(i.box, i.mastered)}</Pill>
                        <span className="text-xs text-slate-500">{dueText(i.due_at)}</span>
                      </div>
                    </div>
                    <button type="button" className="shrink-0 rounded-md p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800" aria-label="Delete card" onClick={() => remove(i.id)}><Trash2 size={15} /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
      <Modal open={!!adding} onClose={() => setAdding(null)} title="Add a word"
        footer={<><Button variant="secondary" onClick={() => setAdding(null)}>Cancel</Button><Button loading={busy} disabled={!adding?.word?.trim() || !adding?.meaning?.trim()} onClick={save}>Add</Button></>}>
        {adding && (
          <div className="space-y-3">
            <Field label="Word or phrase"><input className="input" autoFocus maxLength={120} value={adding.word} onChange={(e) => setAdding({ ...adding, word: e.target.value })} /></Field>
            <Field label="Meaning"><input className="input" maxLength={300} value={adding.meaning} onChange={(e) => setAdding({ ...adding, meaning: e.target.value })} /></Field>
            <Field label="Example sentence (optional)"><input className="input" maxLength={300} value={adding.example} onChange={(e) => setAdding({ ...adding, example: e.target.value })} /></Field>
          </div>
        )}
      </Modal>
    </div>
  );
}
