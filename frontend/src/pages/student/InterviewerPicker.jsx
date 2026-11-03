import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Square, Volume2 } from "lucide-react";
import { post } from "../../api";
import { usePrefs } from "../../components/useSpeech";
import { Button, Pill, Spinner, useToast } from "../../components/ui";
import { SpeechPlayer } from "../../voice/speechPlayer";
import { FILTERS, browserVoiceOpts, speakBody } from "../../voice/useInterviewers";

const Avatar3D = lazy(() => import("../../voice/Avatar3D"));
const LEVEL = { easy: "Beginner", medium: "Intermediate", hard: "Advanced" };

/**
 * Interviewer selection: one card per personality with a live animated 3D preview (rendered only while the card is
 * on screen), a voice preview that the avatar lip-syncs, and filters by interview type.
 */
export default function InterviewerPicker({ interviewers, value, onSelect, voiceStatus }) {
  const toast = useToast();
  const { speech_rate } = usePrefs();
  const [filter, setFilter] = useState("all");
  const [previewing, setPreviewing] = useState(null); // interviewer id while their sample plays
  const [loadingPreview, setLoadingPreview] = useState(null);
  const player = useRef(null);
  if (!player.current) player.current = new SpeechPlayer();
  const getVisemes = useCallback(() => player.current.getVisemes(), []);
  useEffect(() => () => player.current?.close(), []);

  const shown = interviewers.filter((i) => filter === "all" || i.filters.includes(filter));

  const preview = async (p) => {
    if (previewing === p.id) { player.current.stop(); setPreviewing(null); return; }
    player.current.unlock(); // user gesture
    player.current.stop();
    setLoadingPreview(p.id);
    try {
      let playing;
      if (voiceStatus?.tts?.enabled) {
        try {
          const res = await post("/voice/speak", speakBody(p, p.sample_line, speech_rate));
          setLoadingPreview(null);
          setPreviewing(p.id);
          playing = player.current.play(res);
        } catch (e) {
          toast(`Local voice unavailable (${e.message}) - using the browser voice.`, "error");
        }
      }
      if (!playing) {
        setLoadingPreview(null);
        setPreviewing(p.id);
        playing = player.current.playBrowser(p.sample_line, browserVoiceOpts(p, speech_rate));
      }
      await playing;
    } catch (e) {
      toast(`The preview could not be played (${e.message}).`, "error");
    } finally {
      setLoadingPreview(null);
      setPreviewing((cur) => (cur === p.id ? null : cur));
    }
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter interviewers">
        {FILTERS.map((f) => (
          <button key={f.id} type="button" onClick={() => setFilter(f.id)} aria-pressed={filter === f.id}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${filter === f.id
              ? "border-brand-400/60 bg-brand-500 text-snow shadow-glow" : "border-slate-300 bg-white text-slate-600 hover:border-slate-400 hover:text-slate-900"}`}>
            {f.label}
          </button>
        ))}
      </div>
      {filter === "english" && (
        <p className="mb-3 text-xs text-slate-500">
          For relaxed speaking practice without interview questions, try <Link to="/student/english" className="text-brand-600 hover:underline">English practice with Aria</Link>.
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {shown.map((p) => {
          const selected = value === p.id;
          return (
            <article key={p.id} data-interviewer-card={p.id} style={{ "--acc": p.ui.accent }}
              className={`card group flex flex-col overflow-hidden transition duration-300 ${selected
                ? "!border-transparent shadow-[0_0_0_1.5px_var(--acc),0_0_60px_-14px_var(--acc)]"
                : "hover:-translate-y-1 hover:shadow-[0_0_0_1px_var(--acc),0_24px_50px_-20px_var(--acc)]"}`}>
              <div className="relative">
                <LazyAvatar persona={p} mode={previewing === p.id ? "greeting" : selected ? "listening" : "idle"}
                  getVisemes={previewing === p.id ? getVisemes : null} />
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-white to-transparent" aria-hidden />
                <span className="absolute left-2.5 top-2.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold text-snow" style={{ background: p.ui.accent, boxShadow: `0 0 16px -2px ${p.ui.accent}` }}>{p.ui.badge}</span>
                {selected && <span className="absolute right-2.5 top-2.5 flex h-7 w-7 items-center justify-center rounded-full text-snow" style={{ background: p.ui.accent, boxShadow: `0 0 18px ${p.ui.accent}` }}><CheckCircle2 size={17} aria-label="Selected" /></span>}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-4">
                <div>
                  <h3 className="text-lg font-semibold">{p.name}</h3>
                  <p className="mt-0.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-slate-600"><span className="h-1.5 w-1.5 rounded-full" style={{ background: p.ui.accent, boxShadow: `0 0 6px ${p.ui.accent}` }} />{p.title}</p>
                </div>
                <p className="text-sm leading-relaxed text-slate-600">{p.description}</p>
                <p className="text-xs text-slate-500"><Volume2 size={12} className="mr-1 inline" />{p.voice_description}</p>
                {p.traits && Object.keys(p.traits).length > 0 && (
                  <dl className="grid grid-cols-2 gap-x-2 gap-y-1 rounded-lg border border-slate-200 bg-slate-100/40 p-2.5 text-[11px] text-slate-500">
                    {Object.entries(p.traits).map(([k, v]) => (
                      <div key={k} className="contents"><dt className="capitalize">{k}</dt><dd className="font-medium text-slate-700">{v}</dd></div>
                    ))}
                  </dl>
                )}
                <div className="flex flex-wrap gap-1 text-xs">
                  <Pill tone="amber">{LEVEL[p.recommended_difficulty]} level</Pill>
                  {p.categories.slice(0, 4).map((c) => <Pill key={c}>{c}</Pill>)}
                </div>
                {p.interrupts && <p className="text-xs text-rose-700">Time limit: about {Math.round(p.answer_seconds)} s per answer.</p>}
                <div className="mt-auto flex gap-2 pt-2">
                  <Button type="button" size="sm" variant="secondary" onClick={() => preview(p)} loading={loadingPreview === p.id}
                    aria-label={`${previewing === p.id ? "Stop" : "Preview"} ${p.name}'s voice`}>
                    {previewing === p.id ? <><Square size={14} /> Stop</> : <><Volume2 size={14} /> Preview</>}
                  </Button>
                  <Button type="button" size="sm" className="flex-1" variant={selected ? "success" : "primary"} onClick={() => onSelect(p)}
                    aria-pressed={selected}>
                    {selected ? "Selected" : `Select ${p.name}`}
                  </Button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
      {!shown.length && <p className="text-sm text-slate-500">No interviewer matches this filter.</p>}
      {(() => {
        const sel = interviewers.find((i) => i.id === value);
        if (!sel?.interrupts) return null;
        return (
          <div role="note" className="mt-4 rounded-xl border border-rose-400/30 bg-rose-500/[0.08] p-4 text-sm text-rose-800 shadow-[0_0_40px_-20px_rgb(244_63_94/0.6)]">
            <p className="font-semibold">You have chosen a stress interview with {sel.name}.</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              <li>He asks short, direct questions, challenges vague claims and adds realistic constraints.</li>
              <li>Each answer has a time limit of about {Math.round(sel.answer_seconds)} seconds. A countdown is shown, and at the limit he politely stops you and moves on.</li>
              <li>The pressure comes only from the questions: no insults, nothing personal. Your score uses the same fair rubric as every other interviewer.</li>
              <li>If it feels like too much, you can pause or end the interview at any time, or choose another interviewer.</li>
            </ul>
          </div>
        );
      })()}
    </div>
  );
}

/** Live 3D preview, mounted only while the card is visible (each preview is a WebGL canvas). */
function LazyAvatar({ persona, mode, getVisemes }) {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) { setVisible(true); return undefined; }
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { rootMargin: "100px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} className="h-52 w-full bg-night-900">
      {visible && !failed && (
        <Suspense fallback={<div className="flex h-full items-center justify-center"><Spinner label="" /></div>}>
          <Avatar3D lite testHook={false} interviewer={persona.id} modelUrl={persona.ui.model} mode={mode}
            getVisemes={getVisemes} label={`${persona.name} preview`} className="h-52 w-full" onFailed={() => setFailed(true)} />
        </Suspense>
      )}
      {failed && <div className="flex h-full items-center justify-center text-xs text-slate-500">3D preview unavailable in this browser</div>}
    </div>
  );
}
