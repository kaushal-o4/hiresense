// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/pages/student/InterviewerPicker.jsx
//
// FILE PURPOSE:
// Interviewer selection cards with a live 3D preview and a voice sample.
//
// WHAT THIS FILE DOES:
// 1. Shows one card per interviewer personality with level and style.
// 2. Filters by interview type.
// 3. Plays a voice preview (POST /voice/speak) that the avatar lip-syncs.
// 4. Renders the 3D preview only while the card is visible (LazyAvatar).
//
// HOW THIS FILE WORKS:
// A React page component. It loads data with useApi()/get() from apiClient.js, keeps local state with
// useState and sends changes with post/put/patch/del, then shows results with the shared UI
// components. API calls used: POST /voice/speak.
//
// IMPORTANT FUNCTIONS:
//    - InterviewerPicker()
//        Selection component.
//    - LazyAvatar()
//        3D preview rendered only when on screen.
//    Other helper functions: Avatar3D
//
// INPUT:
// Props: interviewers, value, onSelect, voiceStatus.
//
// OUTPUT:
// The selected interviewer id.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, components/SharedUiComponents.jsx, components/useSpeechAndPreferences.jsx,
//    voice/Avatar3D.jsx, voice/speechPlayer.js, voice/useInterviewers.js
//    Used by: pages/student/MockInterviewHome.jsx
//
// IMPORTANT DEPENDENCIES:
//    lucide-react, react, react-router-dom
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Square, Volume2 } from "lucide-react";
import { post } from "../../apiClient";
import { usePrefs } from "../../components/useSpeechAndPreferences";
import { Button, Pill, Spinner, useToast } from "../../components/SharedUiComponents";
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
      <div className="mb-4 flex w-fit max-w-full flex-wrap gap-0.5 rounded-lg border border-slate-200 bg-slate-100 p-0.5" role="group" aria-label="Filter interviewers">
        {FILTERS.map((f) => (
          <button key={f.id} type="button" onClick={() => setFilter(f.id)} aria-pressed={filter === f.id}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${filter === f.id
              ? "bg-white text-slate-950 shadow-soft ring-1 ring-slate-200" : "text-slate-500 hover:text-slate-900"}`}>
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
              className={`card group flex flex-col overflow-hidden transition duration-200 ${selected
                ? "!border-brand-500 ring-1 ring-brand-500"
                : "hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-pop"}`}>
              <div className="relative">
                <LazyAvatar persona={p} mode={previewing === p.id ? "greeting" : selected ? "listening" : "idle"}
                  getVisemes={previewing === p.id ? getVisemes : null} />
                <span className="absolute left-2.5 top-2.5 inline-flex items-center gap-1.5 rounded-full bg-night-950/75 px-2.5 py-0.5 text-[11px] font-semibold text-snow ring-1 ring-snow/10">
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: p.ui.accent }} aria-hidden />{p.ui.badge}
                </span>
                {selected && <span className="absolute right-2.5 top-2.5 flex h-7 w-7 items-center justify-center rounded-full bg-brand-500 text-snow"><CheckCircle2 size={16} aria-label="Selected" /></span>}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-4">
                <div>
                  <h3 className="text-lg font-bold">{p.name}</h3>
                  <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-500">{p.title}</p>
                </div>
                <p className="text-sm leading-relaxed text-slate-600">{p.description}</p>
                <p className="flex items-start gap-1.5 text-xs text-slate-500"><Volume2 size={12} className="mt-0.5 shrink-0" aria-hidden />{p.voice_description}</p>
                {p.traits && Object.keys(p.traits).length > 0 && (
                  <dl className="grid grid-cols-2 gap-x-2 gap-y-1 rounded-lg bg-slate-50 p-2.5 text-[11px] text-slate-500 ring-1 ring-inset ring-slate-200">
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
          <div role="note" className="mt-4 rounded-xl border border-rose-200 border-l-2 border-l-rose-500 bg-rose-50 p-4 text-sm text-rose-800">
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
