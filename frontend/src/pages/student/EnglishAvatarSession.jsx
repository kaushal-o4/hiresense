import { Suspense, lazy, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Flame, Gauge, Keyboard, Lightbulb, Mic, Pause, PhoneOff, Play, Send, Sparkles, Square, Timer, Volume2 } from "lucide-react";
import { api, del, get, post } from "../../api";
import { useSpeechToText, usePrefs } from "../../components/useSpeech";
import { Button, Card, ConfirmButton, Notice, Pill, useToast } from "../../components/ui";
import ConversationMemory, { LEARNING_MODE_LABEL } from "../../components/ConversationMemory";
import Avatar from "../../voice/Avatar";
// three.js is large: load the 3D avatar only when this page is opened.
const Avatar3D = lazy(() => import("../../voice/Avatar3D"));
import {
  E, ENGLISH_STATUS_LABEL, GENERIC_STARTERS, confidenceLabel, englishAvatarMode, englishTransition, initialEnglishState,
} from "../../voice/englishMachine";
import { MicRecorder } from "../../voice/recorder";
import { SpeechPlayer } from "../../voice/speechPlayer";

const HESITATION_MS = 5000; // quiet this long on the student's turn -> offer starter phrases
const STYLE_LABEL = { free_talk: "English free talk", interview: "Job interview practice" };

/**
 * Face-to-face spoken-English practice with Aria. Hands-free loop:
 * Aria speaks (lip-synced, subtitled) -> mic opens -> student speaks -> pause or "Done" -> transcribe -> Aria thinks
 * -> Aria replies. Corrections and encouragement are shown on screen, never spoken.
 *
 * Speech input: local Whisper on the server when enabled (audio stays on the server); otherwise the browser's
 * speech recognition (Chrome/Edge send audio to their cloud service - the start screen says so); otherwise typing.
 * Speech output: local Kokoro voice with phoneme lip sync; otherwise the browser voice with approximate lip sync.
 */
export default function EnglishAvatarSession({ initial, onEnded }) {
  const id = initial.id;
  const toast = useToast();
  const navigate = useNavigate();
  const { speech_rate, subtitles } = usePrefs();
  const [s, setS] = useState(initial);
  const [st, dispatch] = useReducer(englishTransition, initialEnglishState);
  const stRef = useRef(st);
  stRef.current = st;
  const [voice, setVoice] = useState(null); // /voice/status ({} if unknown)
  const [stats, setStats] = useState(null);
  const [inputMode, setInputMode] = useState("voice");
  const [autoMic, setAutoMic] = useState(true);
  const [draft, setDraft] = useState("");
  const [micLevel, setMicLevel] = useState(0);
  const [stuck, setStuck] = useState(false);
  const [hint, setHint] = useState(null);
  const [lipsync, setLipsync] = useState(null);
  const [subPos, setSubPos] = useState(null);
  const [use3d, setUse3d] = useState(true);
  const browserStt = useSpeechToText();
  const bs = useRef(browserStt);
  bs.current = browserStt;
  const player = useRef(null);
  const recorder = useRef(null);
  const audioRef = useRef(null);
  const recId = useRef(0);
  const lastVoiceAt = useRef(0);
  const inputRef = useRef(null);
  if (!player.current) player.current = new SpeechPlayer();
  if (!recorder.current) recorder.current = new MicRecorder();
  const getMouth = useCallback(() => player.current.getMouth(), []);
  const getVisemes = useCallback(() => player.current.getVisemes(), []);

  const lastAi = s.messages.filter((m) => m.sender === "ai").slice(-1)[0];
  const lastStudent = s.messages.filter((m) => m.sender === "student").slice(-1)[0];
  const studentTurns = s.messages.filter((m) => m.sender === "student").length;
  const style = s.style || "free_talk";
  // learning mode: confidence mode speaks more slowly and waits longer before ending the student's turn
  const modeCfg = s.learning_mode_settings || { tts_speed: 1, listen_silence_ms: 4000 };
  const ariaRate = Math.min(1.4, Math.max(0.7, (speech_rate || 1) * (modeCfg.tts_speed || 1)));
  const sttEngine = voice == null ? null : voice.stt?.enabled ? "local" : browserStt.supported ? "browser" : "none";

  // ------------------------------------------------------------------ load + cleanup
  useEffect(() => {
    get("/voice/status").then(setVoice).catch(() => setVoice({}));
    get("/student/english/stats").then(setStats).catch(() => {});
  }, []);
  useEffect(() => () => {
    player.current?.close();
    recorder.current?.cancel();
    bs.current?.stop();
  }, []);

  // ------------------------------------------------------------------ Aria speaks
  useEffect(() => {
    if (st.status !== E.PREPARING_SPEECH) return;
    if (!lastAi) return dispatch({ type: "SPEECH_FAILED", error: "There is nothing to say yet." });
    let alive = true;
    const text = lastAi.content.slice(0, 1500);
    (async () => {
      if (voice?.tts?.enabled) {
        try {
          const res = await post("/voice/speak", { text, speed: ariaRate });
          if (!alive) return;
          audioRef.current = { kind: "phoneme", res };
          return dispatch({ type: "AUDIO_READY" });
        } catch (e) {
          if (!alive) return;
          toast(`Aria's voice is unavailable (${e.message}). Using the browser voice instead.`, "error");
        }
      }
      audioRef.current = { kind: "approx", text };
      dispatch({ type: "AUDIO_READY" });
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status, lastAi?.id]);

  useEffect(() => {
    if (st.status !== E.SPEAKING || !audioRef.current) return;
    const a = audioRef.current;
    setLipsync(a.kind);
    const playing = a.kind === "phoneme" ? player.current.play(a.res) : player.current.playBrowser(a.text, { rate: ariaRate });
    playing
      .then(({ stopped }) => { if (!stopped) dispatch({ type: "SPEECH_DONE" }); })
      .catch((e) => dispatch({ type: "SPEECH_FAILED", error: `Aria's reply could not be played aloud (${e.message}). Please read it on screen.` }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status]);

  // live subtitles follow the playback position
  useEffect(() => {
    if (st.status !== E.SPEAKING) { setSubPos(null); return; }
    const t = setInterval(() => setSubPos(player.current.progress()), 90);
    return () => clearInterval(t);
  }, [st.status]);

  // ------------------------------------------------------------------ student's turn
  const sendReply = async (content, mode, confidence = null) => {
    dispatch({ type: "SEND" });
    setHint(null);
    try {
      const res = await post(`/student/english/${id}/message`, {
        content: content.slice(0, 3000), input_mode: mode, speech_confidence: confidence,
      });
      setS(res);
      setDraft("");
      setAutoMic(true);
      dispatch({ type: "REPLY" });
    } catch (e) {
      setDraft(content);
      setInputMode("text");
      dispatch({ type: "SEND_FAILED", error: `${e.message} Your words are kept below - press Send to try again.` });
    }
  };

  const cancelListening = () => {
    recId.current++;
    recorder.current.cancel();
    bs.current.stop();
    setMicLevel(0);
  };

  const startListening = useCallback(async () => {
    if (player.current.speaking) player.current.stop(); // never record while Aria is talking
    const myId = ++recId.current;
    lastVoiceAt.current = Date.now();
    if (sttEngine === "browser") {
      bs.current.reset();
      bs.current.start();
      dispatch({ type: "RECORD_START" });
      return;
    }
    try {
      await recorder.current.start({
        silenceMs: modeCfg.listen_silence_ms || 4000,
        maxSeconds: 120,
        onLevel: (l) => { setMicLevel(l); if (l > 0.02) lastVoiceAt.current = Date.now(); },
        onSilence: () => stopRef.current?.(myId),
        onMax: () => stopRef.current?.(myId),
        onNoSpeech: () => toast("I can't hear you yet. Check your microphone, or type your reply.", "error"),
      });
      if (myId !== recId.current) { recorder.current.cancel(); return; }
      dispatch({ type: "RECORD_START" });
    } catch (e) {
      setInputMode("text");
      dispatch({ type: "RECORD_FAILED", error: e.message });
    }
  }, [sttEngine, toast, modeCfg.listen_silence_ms]);

  const stopRef = useRef(null);
  stopRef.current = async (myId = recId.current) => {
    if (myId !== recId.current || !stRef.current.recording) return; // stale or already stopped
    const token = ++recId.current;
    setMicLevel(0);
    if (sttEngine === "browser") {
      bs.current.stop();
      dispatch({ type: "RECORD_STOP" });
      // final results can arrive just after stop()
      setTimeout(() => {
        if (token !== recId.current) return; // paused, ended or failed meanwhile
        const text = [bs.current.transcript, bs.current.interim].join(" ").trim();
        if (!text) { setAutoMic(false); dispatch({ type: "NO_SPEECH", notice: "I didn't catch that. Press Speak when you're ready - no rush." }); }
        else sendReply(text, "voice", bs.current.avgConfidence());
      }, 700);
      return;
    }
    const clip = await recorder.current.stop();
    dispatch({ type: "RECORD_STOP" });
    if (!clip || clip.seconds < 0.4) {
      setAutoMic(false);
      return dispatch({ type: "NO_SPEECH", notice: "That was very short. Press Speak and try again - take your time." });
    }
    const fd = new FormData();
    fd.append("audio", new Blob([clip.wav], { type: "audio/wav" }), "reply.wav");
    try {
      const r = await api(`/student/english/${id}/transcribe`, { method: "POST", body: fd });
      if (!r.text) {
        setAutoMic(false);
        return dispatch({ type: "NO_SPEECH", notice: r.note || "I didn't catch any words. Press Speak to try again." });
      }
      sendReply(r.text, "voice");
    } catch (e) {
      setInputMode("text");
      dispatch({ type: "TRANSCRIBE_FAILED", error: `${e.message}` });
    }
  };

  // microphone turns on automatically when it's the student's turn
  useEffect(() => {
    if (st.status !== E.LISTENING || st.recording || inputMode !== "voice" || !autoMic || st.error) return;
    if (!sttEngine || sttEngine === "none") return;
    const t = setTimeout(() => startListening(), 350); // small gap so the tail of Aria's voice is not captured
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status, st.recording, inputMode, autoMic, st.error, sttEngine]);

  // browser recognition: finish after ~2.5 s without new words, or when the browser ends recognition itself
  const heard = `${browserStt.transcript} ${browserStt.interim}`.trim();
  useEffect(() => {
    if (sttEngine !== "browser" || !st.recording) return;
    if (heard) lastVoiceAt.current = Date.now();
    if (!browserStt.listening) { stopRef.current(); return; }
    if (!heard) return;
    const t = setTimeout(() => stopRef.current(), 2500);
    return () => clearTimeout(t);
  }, [heard, browserStt.listening, st.recording, sttEngine]);

  // browser recognition failed (permission, network, unsupported service): fall back to typing for this session
  useEffect(() => {
    if (sttEngine !== "browser" || !browserStt.error) return;
    cancelListening();
    setInputMode("text");
    setAutoMic(false);
    dispatch({ type: "NO_SPEECH" }); // ignored unless a stop was already in flight
    dispatch({ type: "RECORD_FAILED", error: `${browserStt.error} Please type your reply instead.` });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [browserStt.error, sttEngine]);

  // hesitation helpers: highlighted after a quiet spell on the student's turn
  useEffect(() => {
    if (st.status !== E.LISTENING) { setStuck(false); return; }
    const since = Date.now();
    lastVoiceAt.current = since;
    const t = setInterval(() => setStuck(Date.now() - Math.max(lastVoiceAt.current, since) > HESITATION_MS), 500);
    return () => clearInterval(t);
  }, [st.status]);

  // ------------------------------------------------------------------ ending
  useEffect(() => {
    if (st.status !== E.ENDING) return;
    player.current.stop();
    cancelListening();
    post(`/student/english/${id}/end`)
      .then((res) => {
        if (res.evaluation_error) toast(res.evaluation_error, "error");
        const mins = Math.round(res.session.active_seconds / 60);
        if (res.session.active_seconds < res.min_active_seconds_for_points)
          toast(`Session saved (${mins} min active). Practise at least ${Math.round(res.min_active_seconds_for_points / 60)} active minutes to earn points.`);
        else toast(`Great work! ${mins} verified minutes of practice.`);
        if (res.new_badges?.length) toast(`🏅 New badge: ${res.new_badges.join(", ")}`);
        dispatch({ type: "ENDED" });
        onEnded(res.session); // parent switches to the score report; this page unmounts and releases audio + mic
      })
      .catch((e) => dispatch({ type: "END_FAILED", error: `${e.message} Your conversation is saved - try ending again.` }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status]);

  // ------------------------------------------------------------------ controls
  const start = () => { player.current.unlock(); if (sttEngine === "none") setInputMode("text"); dispatch({ type: "START" }); };
  const pause = () => { player.current.stop(); cancelListening(); dispatch({ type: "PAUSE" }); };
  const resume = () => { player.current.unlock(); dispatch({ type: "RESUME" }); };
  const replay = () => { cancelListening(); dispatch({ type: "REPLAY" }); };
  const speakNow = () => { setAutoMic(true); setInputMode("voice"); if (!st.recording) startListening(); };
  const typeInstead = () => { cancelListening(); setInputMode("text"); setTimeout(() => inputRef.current?.focus(), 0); };
  const submitText = (e) => {
    e?.preventDefault();
    const text = draft.trim();
    if (text) { cancelListening(); sendReply(text, "text"); }
  };
  const pickStarter = (phrase) => {
    lastVoiceAt.current = Date.now();
    setStuck(false);
    if (inputMode === "text") {
      setDraft((d) => (d.trim() ? d : `${phrase.replace(/…$/, "")} `));
      inputRef.current?.focus();
    } else setHint(phrase);
  };
  const end = async () => {
    if (!studentTurns) {
      player.current.stop();
      cancelListening();
      try { await del(`/student/english/${id}`); } catch { /* ignore */ }
      navigate("/student/english");
      return;
    }
    dispatch({ type: "END" });
  };

  // ------------------------------------------------------------------ render
  const mode = englishAvatarMode(st.status, lastAi?.meta?.avatar_mode);
  const live = ![E.READY, E.ENDING, E.ENDED].includes(st.status);
  const starters = [...(lastAi?.meta?.suggested_followups || []), ...GENERIC_STARTERS[style]].slice(0, 5);
  const encouragement = lastAi?.meta?.encouragement;
  const corrections = lastStudent?.corrections || [];
  const confidence = s.confidence;
  const liveMinutes = Math.floor((s.live_active_seconds || 0) / 60);
  const liveSecs = (s.live_active_seconds || 0) % 60;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      {/* top bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-900 px-4 py-3 text-slate-100">
        <div className="mr-auto min-w-0">
          <p className="truncate text-sm font-semibold">{s.topic}</p>
          <p className="text-xs text-slate-400">{STYLE_LABEL[style]} · {LEARNING_MODE_LABEL[s.learning_mode] || LEARNING_MODE_LABEL.free_conversation} · {studentTurns} {studentTurns === 1 ? "reply" : "replies"}</p>
        </div>
        <span role="status" aria-live="polite" className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
          st.recording ? "bg-red-600" : st.status === E.SPEAKING ? "bg-brand-600" : st.status === E.PAUSED ? "bg-amber-600" : "bg-slate-700"}`}>
          {st.recording && <span className="h-2 w-2 animate-pulse rounded-full bg-white" />}
          {st.recording ? "Listening to you" : ENGLISH_STATUS_LABEL[st.status]}
        </span>
        {live && st.status !== E.PAUSED && <Button size="sm" variant="secondary" onClick={pause}><Pause size={14} /> Pause</Button>}
        {st.status === E.PAUSED && <Button size="sm" onClick={resume}><Play size={14} /> Resume</Button>}
        {st.status !== E.ENDING && (
          <ConfirmButton size="sm" variant="danger"
            message={studentTurns ? "End this practice and see your scores?" : "End now? You haven't replied yet, so this session will be discarded."}
            onConfirm={end}><PhoneOff size={14} /> End & get feedback</ConfirmButton>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          {/* stage */}
          <div className="relative overflow-hidden rounded-2xl bg-slate-800 shadow-lg">
            {use3d ? (
              <Suspense fallback={<div className="flex h-[min(52vh,480px)] w-full items-center justify-center text-sm text-slate-300">Loading Aria…</div>}>
                <Avatar3D getVisemes={getVisemes} mode={mode} className="h-[min(52vh,480px)] w-full"
                  onFailed={(why) => { setUse3d(false); toast(`${why} Showing the simple avatar instead.`, "error"); }} />
              </Suspense>
            ) : (
              <Avatar getMouth={getMouth} mode={mode} className="block h-[min(52vh,480px)] w-full" />
            )}
            <span className="absolute left-3 top-3 z-10 rounded-full bg-black/50 px-3 py-1 text-xs text-white">Aria · English coach</span>
            {lipsync && st.status === E.SPEAKING && (
              <span className="absolute right-3 top-3 z-10 rounded-full bg-black/50 px-3 py-1 text-[11px] text-slate-200">
                {lipsync === "phoneme" ? "local voice · phoneme lip sync" : "browser voice · approximate lip sync"}
              </span>
            )}
            {encouragement && [E.SPEAKING, E.LISTENING].includes(st.status) && (
              <p className="absolute left-3 top-12 z-10 flex max-w-[80%] items-center gap-1.5 rounded-lg bg-emerald-600/90 px-3 py-1.5 text-xs text-white sm:text-sm">
                <Sparkles size={14} className="shrink-0" /> {encouragement}
              </p>
            )}
            {lastAi && live && (
              <div className="absolute inset-x-3 bottom-3 z-10 sm:inset-x-8">
                {hint && st.status === E.LISTENING && (
                  <p className="mb-2 rounded-lg bg-amber-400/95 px-3 py-1.5 text-center text-sm font-medium text-slate-900">Try saying: “{hint}”</p>
                )}
                <SubtitleLine text={lastAi.content} pos={st.status === E.SPEAKING && subtitles ? subPos : null} dim={st.status !== E.SPEAKING} />
              </div>
            )}
          </div>

          {st.error && <Notice>{st.error}</Notice>}
          {st.notice && !st.error && <Notice tone="sky">{st.notice}</Notice>}

          {/* start */}
          {st.status === E.READY && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="text-lg font-semibold">Ready to chat with Aria?</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
                <li>Aria speaks first - turn your sound on. Mistakes are completely fine; she'll never interrupt you.</li>
                <li>When she finishes, your <b>microphone turns on</b>. Pause for a few seconds or press <b>Done</b> when you finish.</li>
                {s.learning_mode === "english_learning"
                  ? <li>Aria will gently say a more natural version of important mistakes, then carry on chatting.</li>
                  : <li>Occasional tips appear on screen only, so you can review them without pressure.</li>}
                {s.learning_mode === "confidence" && <li>Aria speaks more slowly and waits longer for you. Use the example answers below if you get stuck.</li>}
                <li>Talk about anything you enjoy. To change the subject, just say “Can we talk about … instead?”</li>
                {sttEngine === "local" && <li>Your voice is transcribed <b>on this server</b>; audio is not saved.</li>}
                {sttEngine === "browser" && <li>Speech recognition uses your browser's service (Chrome/Edge send the audio to Google/Microsoft).</li>}
                {sttEngine === "none" && <li className="text-amber-700">Voice input isn't available here, so you'll type your replies. Aria will still speak.</li>}
              </ul>
              {voice && !voice.tts?.enabled && <p className="mt-2 text-sm text-amber-700">The local voice is off on this server, so the browser's voice will be used (approximate lip sync).</p>}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button onClick={start} disabled={!voice}><Play size={16} /> Start talking with Aria</Button>
                <Link to={`/student/english`} className="text-sm text-slate-500 hover:underline">Back to all sessions</Link>
              </div>
            </div>
          )}

          {/* answer dock */}
          {[E.LISTENING, E.TRANSCRIBING, E.THINKING, E.SPEAKING, E.PREPARING_SPEECH].includes(st.status) && (
            <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
              {st.status === E.LISTENING && inputMode === "voice" && sttEngine !== "none" && (
                <div className="flex flex-wrap items-center gap-3">
                  {st.recording ? (
                    <Button variant="danger" onClick={() => stopRef.current()}><Square size={16} /> Done</Button>
                  ) : (
                    <Button onClick={speakNow}><Mic size={16} /> Speak</Button>
                  )}
                  {sttEngine === "local" ? (
                    <div className="h-2 w-32 overflow-hidden rounded-full bg-slate-200" aria-label="Microphone level">
                      <div className="h-full bg-emerald-500 transition-[width] duration-75" style={{ width: `${Math.min(100, micLevel * 900)}%` }} />
                    </div>
                  ) : st.recording && <span className="max-w-xs truncate text-xs italic text-slate-500">{heard || "…"}</span>}
                  <span className="text-xs text-slate-500">{st.recording ? "Take your time. I'll send it after a short pause." : "Microphone is off."}</span>
                  <div className="ml-auto flex gap-1">
                    <Button size="sm" variant="ghost" onClick={replay}><Volume2 size={14} /> Say that again</Button>
                    <Button size="sm" variant="ghost" onClick={typeInstead}><Keyboard size={14} /> Type</Button>
                  </div>
                </div>
              )}
              {st.status === E.LISTENING && (inputMode === "text" || sttEngine === "none") && (
                <form onSubmit={submitText} className="flex flex-wrap gap-2">
                  <input ref={inputRef} className="input min-w-0 flex-1" value={draft} maxLength={3000} aria-label="Your reply"
                    placeholder="Type your reply in full sentences…" onChange={(e) => { setDraft(e.target.value); lastVoiceAt.current = Date.now(); }} />
                  <Button type="submit" disabled={!draft.trim()} aria-label="Send"><Send size={16} /></Button>
                  {sttEngine && sttEngine !== "none" && <Button type="button" variant="ghost" onClick={speakNow}><Mic size={14} /> Speak instead</Button>}
                  <Button type="button" size="sm" variant="ghost" onClick={replay}><Volume2 size={14} /> Say that again</Button>
                </form>
              )}
              {st.status === E.TRANSCRIBING && <p className="text-sm text-slate-500">Catching your words…</p>}
              {st.status === E.THINKING && <p className="text-sm text-slate-500">Aria is thinking about what you said…</p>}
              {[E.SPEAKING, E.PREPARING_SPEECH].includes(st.status) && (
                <p className="flex items-center gap-2 text-sm text-slate-500"><span className="inline-block h-2 w-2 rounded-full bg-slate-400" /> Microphone is off while Aria is speaking.</p>
              )}
            </div>
          )}
          {st.status === E.ENDING && <p className="text-sm text-slate-500">Aria is preparing your fluency, vocabulary, grammar and sentence-formation report…</p>}

          {/* hesitation helpers */}
          {st.status === E.LISTENING && (
            <div className={`rounded-xl border p-4 transition-colors ${stuck ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"}`}>
              <p className="flex items-center gap-2 text-sm font-medium text-slate-700">
                <Lightbulb size={16} className={stuck ? "text-amber-500" : "text-slate-400"} />
                {stuck ? "No rush - take a breath. You could start with one of these:"
                  : s.learning_mode === "confidence" ? "Need an idea? Read one of these example answers aloud, or change it a little"
                    : "Stuck? Try a starter phrase"}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {starters.map((p) => (
                  <button key={p} type="button" onClick={() => pickStarter(p)}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1 text-sm text-slate-700 hover:border-brand-400 hover:text-brand-700">{p}</button>
                ))}
              </div>
            </div>
          )}

          <Conversation messages={s.messages} />
        </div>

        {/* sidebar */}
        <div className="space-y-4">
          <Card title="Confidence meter">
            <div className="flex items-center gap-3">
              <Gauge size={28} className="text-brand-600" />
              <div className="flex-1">
                <div className="h-3 overflow-hidden rounded-full bg-slate-200" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={confidence ?? 0} aria-label="Confidence">
                  <div className={`h-full transition-all duration-700 ${confidence >= 65 ? "bg-emerald-500" : confidence >= 40 ? "bg-brand-500" : "bg-amber-400"}`} style={{ width: `${confidence ?? 4}%` }} />
                </div>
                <p className="mt-1 text-sm font-medium text-slate-700">{confidenceLabel(confidence)}</p>
              </div>
              <span className="text-xl font-bold text-slate-800">{confidence ?? "–"}</span>
            </div>
            <p className="mt-2 text-xs text-slate-500">Grows as you give longer answers, keep the conversation going and speak aloud. Your real scores come at the end.</p>
          </Card>

          <Card title="Practice streak">
            <div className="flex items-center gap-3">
              <Flame size={28} className={stats?.current_streak ? "text-orange-500" : "text-slate-300"} />
              <div>
                <p className="text-2xl font-bold">{stats ? stats.current_streak : "–"} <span className="text-sm font-normal text-slate-500">day{stats?.current_streak === 1 ? "" : "s"}</span></p>
                <p className="text-xs text-slate-500">
                  {!stats ? "Loading…" : stats.practiced_today ? "You've practised today - keep it going tomorrow!"
                    : stats.current_streak ? "Finish this session (1+ active minute) to extend your streak." : "Finish this session to start a streak."}
                </p>
              </div>
            </div>
            {stats && <p className="mt-2 text-xs text-slate-500">Best: {stats.longest_streak} days · {stats.sessions_completed} sessions · {stats.total_minutes} min total</p>}
          </Card>

          <Card title="Verified practice time">
            <p className="flex items-center gap-2 text-2xl font-semibold"><Timer size={20} className="text-slate-400" />{liveMinutes}:{String(liveSecs).padStart(2, "0")}</p>
            <p className="mt-1 text-xs text-slate-500">Counts time spent replying with real sentences (pauses over 2 minutes are not counted). Updates after each reply.</p>
          </Card>

          <Card title="Polish your English">
            {!lastStudent ? <p className="text-sm text-slate-500">Gentle tips on your latest reply will appear here.</p>
              : corrections.length === 0 ? (
                <p className="text-sm text-emerald-700">
                  {s.learning_mode === "english_learning" ? "Nicely said - no corrections on your last reply. 🎉"
                    : "Keep talking! In this mode only the occasional important tip appears here."}
                </p>
              )
                : (
                  <ul className="space-y-3">
                    {corrections.map((c, i) => (
                      <li key={i} className="text-sm">
                        <span className="text-red-600 line-through">{c.original}</span> → <span className="font-medium text-emerald-700">{c.corrected}</span>
                        {c.explanation && <span className="block text-xs text-slate-500">{c.explanation}</span>}
                      </li>
                    ))}
                  </ul>
                )}
          </Card>
          <ConversationMemory memory={s.memory} learningMode={s.learning_mode} />
          <p className="px-1 text-xs text-slate-500"><Pill>{s.mode}</Pill> <Link to="/student/english" className="ml-1 hover:underline">All sessions</Link></p>
        </div>
      </div>
    </div>
  );
}

/** Aria's current line; while she speaks, the word being spoken is highlighted. */
function SubtitleLine({ text, pos, dim }) {
  if (pos == null) {
    return <p className={`rounded-lg bg-slate-900/85 px-4 py-2 text-center text-sm sm:text-base ${dim ? "text-slate-300" : "text-white"}`} aria-live="polite">{text}</p>;
  }
  const at = Math.round(pos * text.length);
  const start = text.lastIndexOf(" ", Math.max(0, at - 1)) + 1;
  const endIdx = text.indexOf(" ", at);
  const end = endIdx === -1 ? text.length : endIdx;
  return (
    <p className="rounded-lg bg-slate-900/85 px-4 py-2 text-center text-sm text-slate-400 sm:text-base" aria-live="polite">
      <span className="text-white">{text.slice(0, start)}</span>
      <span className="rounded bg-brand-500 px-0.5 text-white">{text.slice(start, end)}</span>
      <span>{text.slice(end)}</span>
    </p>
  );
}

function Conversation({ messages }) {
  const bottom = useRef(null);
  useEffect(() => { bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [messages.length]);
  return (
    <Card title="Conversation" bodyClass="max-h-72 space-y-3 overflow-y-auto p-4">
      {messages.map((m) => (
        <div key={m.id} className={`flex ${m.sender === "student" ? "justify-end" : "justify-start"}`}>
          <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${m.sender === "student" ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-800"}`}>
            {m.content}
          </div>
        </div>
      ))}
      <div ref={bottom} />
    </Card>
  );
}
