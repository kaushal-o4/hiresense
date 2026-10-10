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
              ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 bg-white text-slate-600 hover:border-brand-400"}`}>
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
            <article key={p.id} data-interviewer-card={p.id}
              className={`flex flex-col overflow-hidden rounded-xl border bg-white transition-shadow ${selected
                ? "border-brand-500 shadow-md ring-2 ring-brand-500/40" : "border-slate-200 hover:shadow"}`}>
              <div className="relative">
                <LazyAvatar persona={p} mode={previewing === p.id ? "greeting" : selected ? "listening" : "idle"}
                  getVisemes={previewing === p.id ? getVisemes : null} />
                <span className="absolute left-2 top-2 rounded-full px-2 py-0.5 text-[11px] font-semibold text-white" style={{ background: p.ui.accent }}>{p.ui.badge}</span>
                {selected && <CheckCircle2 className="absolute right-2 top-2 text-brand-600" size={22} aria-label="Selected" />}
              </div>
              <div className="flex flex-1 flex-col gap-2 p-4">
                <div>
                  <h3 className="text-lg font-semibold">{p.name}</h3>
                  <p className="text-xs font-medium uppercase tracking-wide" style={{ color: p.ui.accent }}>{p.title}</p>
                </div>
                <p className="text-sm text-slate-600">{p.description}</p>
                <p className="text-xs text-slate-500"><Volume2 size={12} className="mr-1 inline" />{p.voice_description}</p>
                <div className="flex flex-wrap gap-1 text-xs">
                  <Pill tone="amber">{LEVEL[p.recommended_difficulty]} level</Pill>
                  {p.categories.slice(0, 4).map((c) => <Pill key={c}>{c}</Pill>)}
                </div>
                {p.interrupts && <p className="text-xs text-red-700">Time limit: about {Math.round(p.answer_seconds)} s per answer.</p>}
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
    <div ref={ref} className="h-52 w-full bg-slate-200">
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
