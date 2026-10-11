import { Suspense, lazy, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Camera, CameraOff, Keyboard, Mic, MicOff, Pause, PhoneOff, Play, RotateCcw, Send, Settings2, Timer, Volume2, VolumeX,
} from "lucide-react";
import { api, del, get, post } from "../../api";
import { usePrefs } from "../../components/useSpeech";
import { Button, ConfirmButton, ErrorBox, Notice, Spinner, useToast } from "../../components/ui";
import Avatar from "../../voice/Avatar";
// three.js is large: load the 3D interviewer only when this page is opened.
const Avatar3D = lazy(() => import("../../voice/Avatar3D"));
import { AVATAR_QUALITY, AVATAR_STATE_LABEL, avatarStateFor, saveQuality, storedQuality } from "../../voice/avatarStates";
import { S, STATUS_LABEL, initialState, transition } from "../../voice/interviewMachine";
import { MicRecorder } from "../../voice/recorder";
import { SpeechPlayer } from "../../voice/speechPlayer";
import { streamTurn } from "../../voice/turnStream";
import { browserVoiceOpts, findInterviewer, speakBody, useInterviewers } from "../../voice/useInterviewers";
import { reportMetric } from "../../monitoring/eventReporter";
import { InterviewMonitor } from "../../monitoring/interviewMonitor";
import { CameraSession } from "../../monitoring/mediaSession";
import { MonitorBar, MonitoringSummary } from "../../monitoring/MonitorBar";
import InterviewerFeedback from "./InterviewerFeedback";
import InterviewSetup from "./InterviewSetup";
import { InterviewReport } from "./InterviewSession";

// Used only if the interviewer list cannot be loaded: the original Aria behaviour.
const FALLBACK = {
  id: "aria", name: "Aria", title: "Friendly interviewer", tts_voice: undefined, tts_speed: 1, interrupts: false,
  answer_seconds: 180, browser_voice: { gender: "female", lang: "en-US", pitch: 1.05 },
  ui: { accent: "#0ea5e9", model: "/avatars/interviewer.glb", badge: "Friendly" },
  greeting: "Hi, I'm Aria, and I'll be your interviewer today for the {role} role. Take your time with each answer. Let's begin.",
  reactions: ["Thank you. Let me think about that for a moment.", "Okay, thanks for that. Give me a second."],
  closing: "Thank you, that was my last question. When you are ready, press Finish and I will prepare your feedback.",
};
const INTERJECTION = "Let me stop you there. I have what I need.";
const REACTION_MS = 1800; // how long the avatar visibly reacts after an answer before it starts "thinking"
const SUB_SIZE = { sm: "text-sm", md: "text-base", lg: "text-lg sm:text-xl" };
// endOfSpeechMs: null = the default for the chosen response mode (from /voice/status). autoSend: submit the
// transcript right after it is ready instead of waiting for the Submit button.
const DEFAULT_SETTINGS = { voiceOn: true, rate: 1, captions: true, subtitleSize: "md", autoMic: true, endOfSpeechMs: null, autoSend: false };
const splitSentences = (t) => (t || "").split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
const turnId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

const fmtClock = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const store = (kind) => ({
  get: (k) => { try { return window[kind].getItem(k); } catch { return null; } },
  set: (k, v) => { try { window[kind].setItem(k, v); } catch { /* private mode */ } },
});
const session_ = store("sessionStorage");
const local = store("localStorage");

function currentQuestion(session) {
  const q = session?.questions?.[session.questions.length - 1];
  return q && !q.answer ? q : null;
}

export default function VoiceInterview() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { speech_rate } = usePrefs();
  const [st, dispatch] = useReducer(transition, initialState);
  const stRef = useRef(st);
  stRef.current = st;
  const [session, setSession] = useState(null);
  const [voice, setVoice] = useState(null); // /voice/status
  const { list: interviewers, error: ivError } = useInterviewers();
  const persona = findInterviewer(interviewers, session?.interviewer) || (ivError ? FALLBACK : null);
  const [settings, setSettings] = useState(() => {
    try { return { ...DEFAULT_SETTINGS, rate: speech_rate || 1, ...JSON.parse(local.get("hs-room-settings") || "{}") }; } catch { return DEFAULT_SETTINGS; }
  });
  const setSetting = (patch) => setSettings((s) => { const n = { ...s, ...patch }; local.set("hs-room-settings", JSON.stringify(n)); return n; });
  const [showSettings, setShowSettings] = useState(false);
  const [avatarQuality, setAvatarQuality] = useState(storedQuality);
  const [lipsync, setLipsync] = useState(null); // "phoneme" | "approx" | "silent" | null
  const [speechKind, setSpeechKind] = useState(null); // "greeting" | "question"
  const [subPos, setSubPos] = useState(null);
  const [draft, setDraft] = useState("");
  const [inputMode, setInputMode] = useState("voice");
  const [micLevel, setMicLevel] = useState(0);
  const [recSeconds, setRecSeconds] = useState(0);
  const [lastFeedback, setLastFeedback] = useState(null);
  const [closing, setClosing] = useState(false);
  const [reacting, setReacting] = useState(false);
  const [notes, setNotes] = useState(() => local.get(`hs-notes-${id}`) || "");
  const greeted = useRef(false);
  const [camOn, setCamOn] = useState(false);
  const [elapsed, setElapsed] = useState(() => Number(session_.get(`hs-voice-${id}`) || 0));
  const player = useRef(null);
  const recorder = useRef(null);
  const audioRef = useRef(null); // prepared speech for the current question
  const recId = useRef(0);
  const askedAt = useRef(Date.now());
  const speechSecs = useRef(null); // seconds of speech in the last transcribed recording
  const camVideo = useRef(null);
  const camStream = useRef(null);
  if (!player.current) player.current = new SpeechPlayer();
  if (!recorder.current) recorder.current = new MicRecorder();
  const getMouth = useCallback(() => player.current.getMouth(), []);
  const getVisemes = useCallback(() => player.current.getVisemes(), []);
  const [use3d, setUse3d] = useState(true);
  const current = currentQuestion(session);
  const p = persona || FALLBACK;
  const coaching = session?.response_mode === "coaching";
  // Test hook (tests_e2e): a shorter answer time limit, so the stress-interview interruption can be exercised.
  // Coaching mode gives 50% more time to answer.
  const answerLimit = Number(session_.get("hs-test-answer-limit")) || Math.round((p.answer_seconds || 180) * (coaching ? 1.5 : 1));
  const eosMs = settings.endOfSpeechMs || voice?.recognition?.end_of_speech_ms?.[coaching ? "coaching" : "fast"] || (coaching ? 1800 : 1000);
  // ---- streaming turns, partial transcripts, monitoring
  const t0 = useRef(performance.now()); // interview-relative clock for integrity events
  const turnBusy = useRef(false); // a streamed turn owns speech preparation (PREPARING_SPEECH effect stays idle)
  const queueDone = useRef(null); // promise of the streamed speech queue currently playing
  const reaction = useRef(Promise.resolve());
  const [liveText, setLiveText] = useState(""); // next question appearing as it is written
  const [stage, setStage] = useState(null); // "scoring" | "question"
  const [partial, setPartial] = useState(""); // live transcript while the student is speaking
  const partials = useRef([]);
  const appendTo = useRef("");
  const camera = useRef(null);
  if (!camera.current) camera.current = new CameraSession();
  const monitor = useRef(null);
  const [monFeatures, setMonFeatures] = useState(null);
  const [monStatus, setMonStatus] = useState(null);
  // Active monitoring warnings, newest last. The newest is shown; clearing or dismissing it brings back any older
  // warning that is still active (one warning must never hide another, e.g. "face not visible" under "pasted text").
  const [monWarnings, setMonWarnings] = useState([]);
  const monWarning = monWarnings[monWarnings.length - 1] || null;
  const setMonWarning = (w) => setMonWarnings(w ? (list) => [...list.filter((x) => x.type !== w.type), w] : []);
  const onMonWarning = (w) => setMonWarnings((list) => (w.clear ? list.filter((x) => x.type !== w.clear)
    : [...list.filter((x) => x.type !== w.type), w]));
  const [camHidden, setCamHidden] = useState(false);
  const [camLost, setCamLost] = useState(false);

  // speak `text` in this interviewer's voice (local voice with phoneme lip sync, else the browser voice)
  const say = useCallback(async (text) => {
    if (voice?.tts?.enabled) {
      try {
        const res = await post("/voice/speak", speakBody(p, text, settings.rate));
        return player.current.play(res);
      } catch { /* fall through to the browser voice */ }
    }
    return player.current.playBrowser(text, browserVoiceOpts(p, settings.rate));
  }, [voice, p, settings.rate]);

  // ------------------------------------------------------------------ load
  useEffect(() => {
    if (st.status !== S.INITIALIZING) return;
    let alive = true;
    Promise.all([get(`/student/interviews/${id}`), get("/voice/status").catch(() => null)])
      .then(([s, v]) => {
        if (!alive) return;
        setSession(s);
        setVoice(v);
        dispatch({ type: "LOADED" });
      })
      .catch((e) => alive && dispatch({ type: "LOAD_FAILED", error: e.message }));
    return () => { alive = false; };
  }, [st.status, id]);

  // cleanup on leave: stop audio, release microphone and camera, end monitoring (pending events are sent)
  useEffect(() => () => {
    player.current?.close();
    recorder.current?.cancel();
    monitor.current?.stop();
    monitor.current = null;
    camera.current?.stop();
    camStream.current?.getTracks().forEach((t) => t.stop());
  }, []);

  // ------------------------------------------------------------------ monitoring (only what was consented to)
  const stopMonitoring = useCallback(async ({ withdraw = false } = {}) => {
    const m = monitor.current;
    monitor.current = null;
    camera.current.stop();
    camStream.current = null;
    setCamOn(false);
    setMonWarning(null);
    if (m) await m.stop();
    if (withdraw) {
      setMonFeatures((f) => (f ? { ...f, withdrawn: true } : f));
      try { await post(`/student/interviews/${id}/monitoring/withdraw?t_ms=${Math.round(performance.now() - t0.current)}`); } catch { /* recorded best-effort */ }
      toast("Monitoring stopped. The camera is off. Your interview continues.");
    }
  }, [id, toast]);

  const beginInterview = ({ features }) => {
    setMonFeatures(features);
    if (features.camera && camera.current.active) {
      camStream.current = camera.current.stream;
      camera.current.onLost = (reason) => {
        monitor.current?.cameraLost(reason);
        if (reason === "ended" || reason.startsWith("permission:camera")) {
          setCamOn(false);
          setCamLost(true);
          setMonWarning({ type: "camera", message: "The camera stopped (disconnected or permission changed). Your interview continues; camera monitoring is paused." });
        }
      };
      setCamOn(true);
    }
    start();
  };

  // start the consented monitoring once the in-room camera view is showing the stream
  useEffect(() => {
    if (!monFeatures || monFeatures.withdrawn || monitor.current) return;
    const needsVideo = monFeatures.camera;
    if (needsVideo && !(camOn && camVideo.current)) return;
    if (!needsVideo && !monFeatures.focus_changes && !monFeatures.paste && !monFeatures.screen) return;
    const m = new InterviewMonitor({
      sessionId: id, features: monFeatures, t0: t0.current,
      onStatus: setMonStatus,
      onWarning: onMonWarning,
    });
    monitor.current = m;
    m.start(needsVideo ? camVideo.current : null);
  }, [monFeatures, camOn, id]);

  // ------------------------------------------------------------------ timers
  const timed = ![S.INITIALIZING, S.READY, S.PAUSED, S.COMPLETED, S.ERROR, S.WRAP_UP, S.COMPLETING].includes(st.status);
  useEffect(() => {
    if (!timed) return;
    const t = setInterval(() => setElapsed((e) => { session_.set(`hs-voice-${id}`, String(e + 1)); return e + 1; }), 1000);
    return () => clearInterval(t);
  }, [timed, id]);
  useEffect(() => {
    if (!st.recording) { setRecSeconds(0); return; }
    const t0 = Date.now();
    const t = setInterval(() => setRecSeconds(Math.floor((Date.now() - t0) / 1000)), 250);
    return () => clearInterval(t);
  }, [st.recording]);
  useEffect(() => { local.set(`hs-notes-${id}`, notes); }, [notes, id]);

  // ------------------------------------------------------------------ speaking
  // Replays and resume-after-pause: synthesise the whole question here. (New questions arrive through runTurn,
  // which streams and speaks them sentence by sentence.)
  useEffect(() => {
    if (st.status !== S.PREPARING_SPEECH || turnBusy.current) return;
    let alive = true;
    if (!current) {
      // Recovery: the answer was saved but the next question was not created (temporary server problem).
      post(`/student/interviews/${id}/next-question`)
        .then((res) => {
          if (!alive) return;
          if (res.ready_to_complete) { setSession(res.session); dispatch({ type: "FATAL", error: "All questions are answered - please reload to finish." }); }
          else setSession(res.session); // effect re-runs with the new current question
        })
        .catch((e) => alive && dispatch({ type: "FATAL", error: `The next question could not be prepared (${e.message}). Your answers are saved - reload the page to continue.` }));
      return () => { alive = false; };
    }
    const intro = !greeted.current && !session.answered ? p.greeting.replace("{role}", session.job_role) : null;
    greeted.current = true;
    setSpeechKind(intro ? "greeting" : "question");
    const text = [intro, current.preface, current.text].filter(Boolean).join(" ");
    recorder.current.cancel();
    (async () => {
      if (!settings.voiceOn) {
        audioRef.current = { kind: "silent", text };
        return dispatch({ type: "AUDIO_READY" });
      }
      if (voice?.tts?.enabled) {
        try {
          const res = await post("/voice/speak", speakBody(p, text, settings.rate));
          if (!alive) return;
          audioRef.current = { kind: "phoneme", res, text };
          return dispatch({ type: "AUDIO_READY" });
        } catch (e) {
          if (!alive) return;
          toast(`${p.name}'s voice is unavailable (${e.message}). Using the browser voice instead.`, "error");
        }
      }
      audioRef.current = { kind: "approx", text };
      dispatch({ type: "AUDIO_READY" });
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status, current?.id]);

  useEffect(() => {
    if (st.status !== S.SPEAKING) return;
    if (player.current.paused) { player.current.resume(); return; } // resumed: the original playback continues
    if (queueDone.current) { // streamed turn: speech is already playing sentence by sentence
      setLipsync(voice?.tts?.enabled ? "phoneme" : "approx");
      const done = queueDone.current;
      done.then(({ stopped }) => {
        if (queueDone.current === done) queueDone.current = null;
        if (!stopped) { askedAt.current = Date.now(); dispatch({ type: "SPEECH_DONE" }); }
      });
      return undefined;
    }
    if (!audioRef.current) return;
    const a = audioRef.current;
    setLipsync(a.kind);
    if (a.kind === "silent") {
      // voice off: give time to read the question, mouth stays closed (nothing is being said)
      const t = setTimeout(() => { askedAt.current = Date.now(); dispatch({ type: "SPEECH_DONE" }); },
        Math.max(1500, a.text.split(/\s+/).length * 330));
      return () => clearTimeout(t);
    }
    const playing = a.kind === "phoneme" ? player.current.play(a.res) : player.current.playBrowser(a.text, browserVoiceOpts(p, settings.rate));
    playing
      .then(({ stopped }) => { if (!stopped) { askedAt.current = Date.now(); dispatch({ type: "SPEECH_DONE" }); } })
      .catch((e) => dispatch({ type: "SPEECH_FAILED", error: `The question could not be played aloud (${e.message}). Please read it on screen.` }));
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status]);

  // subtitles follow the playback position
  useEffect(() => {
    if (st.status !== S.SPEAKING) { setSubPos(null); return; }
    const t = setInterval(() => setSubPos(player.current.progress()), 90);
    return () => clearInterval(t);
  }, [st.status]);

  // ------------------------------------------------------------------ listening / recording
  const startRecording = useCallback(async () => {
    if (player.current.speaking) player.current.stop(); // never record while the interviewer is talking
    const myId = ++recId.current;
    partials.current = [];
    setPartial("");
    const qid = current?.id;
    try {
      await recorder.current.start({
        silenceMs: eosMs, // end-of-speech timeout (adjustable in Settings)
        minAnswerMs: voice?.recognition?.min_speech_ms ?? 1200,
        maxSeconds: p.interrupts ? answerLimit : Math.max(answerLimit, 180),
        onLevel: (l) => setMicLevel(l),
        onSilence: () => finishRef.current?.(myId),
        onMax: () => finishRef.current?.(myId, { interrupted: p.interrupts }),
        onNoSpeech: () => toast("We can't hear you yet. Check your microphone, or type your answer.", "error"),
        // Live partial transcript: each stretch of speech is transcribed while the student keeps talking.
        onSegment: voice?.stt?.enabled && qid ? (seg) => {
          const t = performance.now();
          const fd = new FormData();
          fd.append("question_id", String(qid));
          fd.append("partial", "true");
          fd.append("audio", new Blob([seg.wav], { type: "audio/wav" }), `part${seg.index}.wav`);
          partials.current[seg.index] = api(`/student/interviews/${id}/transcribe`, { method: "POST", body: fd })
            .then((r) => {
              reportMetric("client.stt_partial", performance.now() - t, { audio_s: Math.round(seg.seconds) });
              if (myId === recId.current || stRef.current.status === S.TRANSCRIBING) {
                setPartial((prev) => [prev, r.text].filter(Boolean).join(" "));
              }
              return r;
            })
            .catch(() => null);
        } : undefined,
      });
      if (myId !== recId.current) { recorder.current.cancel(); return; }
      dispatch({ type: "RECORD_START" });
    } catch (e) {
      dispatch({ type: "RECORD_FAILED", error: e.message });
    }
  }, [toast, p.interrupts, answerLimit, eosMs, voice, current?.id, id]); // eslint-disable-line react-hooks/exhaustive-deps

  // stop recording -> transcribe -> review. `interrupted`: the stress interviewer stopped the answer at the time limit.
  const finishRef = useRef(null);
  finishRef.current = async (myId = recId.current, { interrupted = false } = {}) => {
    if (myId !== recId.current || !stRef.current.recording) return; // stale or already stopped: process once
    recId.current++;
    const tStop = performance.now();
    const usedSegments = partials.current.length > 0;
    const clip = await recorder.current.stop({ tailOnly: usedSegments });
    setMicLevel(0);
    dispatch({ type: interrupted ? "INTERRUPT" : "RECORD_STOP" });
    if (interrupted && settings.voiceOn) say(INTERJECTION).catch(() => {}); // mic is already off
    const prefix = appendTo.current;
    appendTo.current = "";
    if (!clip || (!usedSegments && clip.seconds < 0.4)) {
      if (prefix) setDraft(prefix);
      dispatch(prefix ? { type: "TRANSCRIPT" } : { type: "NO_SPEECH", notice: "The recording was too short. Please answer again." });
      return;
    }
    const fd = new FormData();
    fd.append("question_id", String(current.id));
    fd.append("audio", new Blob([clip.wav], { type: "audio/wav" }), "answer.wav");
    try {
      // Only the last piece is transcribed now; earlier pieces were transcribed while the student was speaking.
      const tail = clip.seconds >= 0.4 ? api(`/student/interviews/${id}/transcribe`, { method: "POST", body: fd }) : Promise.resolve({ text: "" });
      const [parts, r] = await Promise.all([Promise.all(partials.current), tail]);
      partials.current = [];
      setPartial("");
      const pieces = [...parts.filter(Boolean), r];
      const text = [prefix, ...pieces.map((x) => x.text)].filter(Boolean).join(" ").trim();
      reportMetric("client.stt_roundtrip", performance.now() - tStop, { segments: parts.length });
      if (!text) { dispatch({ type: "NO_SPEECH", notice: r.note || "No speech was recognised. Please try again." }); return; }
      const secs = pieces.reduce((a, x) => a + (x.speech_seconds || 0), 0);
      speechSecs.current = secs || null;
      setDraft(text);
      dispatch({ type: "TRANSCRIPT", notice: interrupted ? `${p.name} stopped your answer at the ${answerLimit}-second limit. Check the text and submit.` : null });
      if (settings.autoSend && !interrupted) setTimeout(() => submitRef.current?.(text), 0);
    } catch (e) {
      setDraft(prefix);
      dispatch({ type: "TRANSCRIBE_FAILED", error: `${e.message} You can type your answer below.` });
    }
  };
  const submitRef = useRef(null);

  useEffect(() => {
    if (st.status !== S.LISTENING || st.recording || inputMode !== "voice" || !settings.autoMic || st.error) return;
    const t = setTimeout(() => startRecording(), 350); // small gap so no tail of the question is captured
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status, inputMode, settings.autoMic]);

  // ------------------------------------------------------------------ streamed turn (answer -> next question)
  /**
   * One conversational turn over /turn (Server-Sent Events). The server scores the answer (if any), then writes the
   * next question; each finished sentence arrives with its audio and is played at once, in order, while the rest
   * is still being written. answer = null for the first question (prepared while the student did the setup).
   */
  const runTurn = async (answer) => {
    if (turnBusy.current) return;
    turnBusy.current = true;
    const tStart = performance.now();
    const voiceOn = settings.voiceOn;
    const localVoice = voiceOn && !!voice?.tts?.enabled;
    const body = { client_turn_id: turnId(), ...(answer ? { answer } : {}),
      ...(localVoice ? { tts: (({ voice: v, speed }) => ({ voice: v, speed }))(speakBody(p, "x", settings.rate)) } : {}) };
    let base = 0; // server sentence index where the current (non-retracted) reply starts
    let nextIndex = 0;
    let spoken = "";
    let began = false;
    let firstText = false;
    let doneData = null;
    let failure = null;
    let ttsWarned = false;
    setLiveText("");
    setStage(answer ? "scoring" : "question");

    if (voiceOn) {
      queueDone.current = null;
      // Fast mode keeps the opening short (first sentence of the greeting only).
      const intro = !answer && !greeted.current && !session.answered ? p.greeting.replace("{role}", session.job_role) : null;
      greeted.current = true;
      setSpeechKind(intro ? "greeting" : "question");
      const introSentences = intro ? (coaching ? splitSentences(intro) : splitSentences(intro).slice(0, 1)) : [];
      await reaction.current; // never talk over the interviewer's own short acknowledgement
      queueDone.current = player.current.startQueue(["intro", "question"], {
        browser: browserVoiceOpts(p, settings.rate),
        onFirstAudio: () => reportMetric(answer ? "client.answer_to_next_question" : "client.first_question_audio",
          performance.now() - tStart, { mode: coaching ? "coaching" : "fast" }),
      });
      introSentences.forEach((s, i) => player.current.queueAdd("intro", i, s));
      player.current.queueClose("intro");
      (async () => { // greeting sentences, one request each so the first can play quickly
        for (let i = 0; i < introSentences.length; i++) {
          if (!localVoice) { player.current.queueBrowserFrom("intro", i); break; }
          try { player.current.queueFill("intro", i, { kind: "phoneme", res: await post("/voice/speak", speakBody(p, introSentences[i], settings.rate)) }); }
          catch { player.current.queueBrowserFrom("intro", i); break; }
        }
      })();
    }
    const beginSpeaking = () => {
      if (began || !voiceOn) return;
      began = true;
      if (stRef.current.status === S.EVALUATING) dispatch({ type: "NEXT_QUESTION" });
      dispatch({ type: "AUDIO_READY" });
    };
    if (voiceOn && !answer) beginSpeaking(); // greeting can start while the question is prepared

    try {
      await streamTurn(id, body, {
        stage: (d) => setStage(d.stage),
        scored: (d) => setLastFeedback((lf) => ({ ...(lf || {}), score: d.score, details: { next_difficulty: d.next_difficulty } })),
        sentence: (d) => {
          if (d.index < base) return;
          nextIndex = Math.max(nextIndex, d.index + 1);
          spoken = spoken ? `${spoken} ${d.text}` : d.text;
          setLiveText(spoken);
          if (!firstText) { firstText = true; if (answer) reportMetric("client.answer_to_first_text", performance.now() - tStart); }
          if (!voiceOn) return;
          player.current.queueAdd("question", d.index - base, d.text);
          if (!localVoice) { player.current.queueFill("question", d.index - base, { kind: "browser" }); beginSpeaking(); }
        },
        audio: (d) => {
          if (d.index < base || !voiceOn) return;
          player.current.queueFill("question", d.index - base, { kind: "phoneme", res: d });
          beginSpeaking();
        },
        tts_error: (d) => {
          if (!voiceOn) return;
          if (!ttsWarned) { ttsWarned = true; toast(`${p.name}'s voice is unavailable (${d.message}). Using the browser voice instead.`, "error"); }
          player.current.queueBrowserFrom("question", Math.max(0, d.from_index - base));
          setLipsync("approx");
          beginSpeaking();
        },
        retract: () => {
          base = nextIndex;
          spoken = "";
          setLiveText("");
          if (voiceOn) player.current.queueRetract("question");
        },
        done: (d) => { doneData = d; },
        error: (d) => { failure = d; },
      });
    } catch (e) {
      failure = { message: e.message, status: e.status };
    }
    setStage(null);
    turnBusy.current = false;

    if (doneData) {
      setSession(doneData.session);
      if (answer) {
        setLastFeedback(doneData.session.questions.find((q) => q.id === answer.question_id)?.answer || null);
        setDraft("");
        speechSecs.current = null;
        if (voice?.stt?.enabled) setInputMode("voice"); // "Type instead" applies to one answer only
        if (doneData.evaluation_error) toast(`Answer saved. ${doneData.evaluation_error}`, "error");
      }
      if (doneData.ready_to_complete) {
        player.current.queueClose("question");
        if (voiceOn && !began) player.current.stop();
        dispatch({ type: "ALL_ANSWERED" });
        return;
      }
      if (voiceOn) {
        player.current.queueClose("question");
        beginSpeaking(); // e.g. every sentence fell back to the browser voice
      } else {
        const q = currentQuestion(doneData.session);
        audioRef.current = { kind: "silent", text: [q?.preface, q?.text].filter(Boolean).join(" ") };
        if (stRef.current.status === S.EVALUATING) dispatch({ type: "NEXT_QUESTION" });
        dispatch({ type: "AUDIO_READY" });
      }
      return;
    }
    // failed
    player.current.stop();
    queueDone.current = null;
    if (!answer) {
      dispatch({ type: "FATAL", error: `The first question could not be prepared (${failure?.message}). Press Reconnect to try again.` });
      return;
    }
    // If the answer actually reached the server (lost response, duplicate submit), continue instead of duplicating it.
    const fresh = await get(`/student/interviews/${id}`).catch(() => null);
    const saved = fresh?.questions?.find((q) => q.id === answer.question_id)?.answer;
    if (failure?.status === 409) reportMetric("client.repeat_submit", 0);
    if (saved && fresh) {
      setSession(fresh);
      setDraft("");
      dispatch({ type: fresh.answered >= fresh.planned_questions ? "ALL_ANSWERED" : "NEXT_QUESTION" }); // replays via PREPARING_SPEECH
    } else dispatch({ type: "SUBMIT_FAILED", error: `${failure?.message || "The answer could not be sent."} Your answer is kept - press Submit to try again.` });
  };

  const submit = async (override) => {
    const text = (typeof override === "string" ? override : draft).trim();
    if (!text) return toast("Your answer is empty. Speak again or type it.", "error");
    if (!current || turnBusy.current) return;
    const interrupted = st.interrupted;
    dispatch({ type: "SUBMIT" });
    // Coaching mode: a short spoken acknowledgement in the interviewer's style plays while the answer is scored
    // (cached audio, ~1-2 s). The next question starts right after it; fast mode skips it.
    reaction.current = Promise.resolve();
    if (coaching && settings.voiceOn && p.reactions?.length) {
      const line = p.reactions[Math.floor(Math.random() * p.reactions.length)];
      reaction.current = (voice?.tts?.enabled ? post("/voice/speak", speakBody(p, line, settings.rate)) : Promise.resolve(null))
        .then((res) => (res ? player.current.play(res) : player.current.playBrowser(line, browserVoiceOpts(p, settings.rate))))
        .catch(() => {});
    }
    await runTurn({
      question_id: current.id, answer: text, input_mode: inputMode === "voice" ? "voice" : "text",
      response_seconds: Math.round((Date.now() - askedAt.current) / 1000),
      speech_seconds: inputMode === "voice" ? speechSecs.current : null, interrupted,
    });
  };
  submitRef.current = submit;

  // REACTION: right after an answer the avatar visibly acknowledges it (expression only - it never delays the next
  // question), then switches to THINKING. The spoken acknowledgement (coaching mode) is started in submit().
  useEffect(() => {
    if (st.status !== S.EVALUATING) return undefined;
    setReacting(true);
    const t = setTimeout(() => setReacting(false), REACTION_MS);
    return () => clearTimeout(t);
  }, [st.status]);

  // Detailed feedback is written in the background after scoring: refresh until it is there.
  const feedbackPending = session?.questions?.some((q) => q.answer?.evaluation_status === "scored");
  useEffect(() => {
    if (!feedbackPending) return;
    const t = setInterval(() => {
      get(`/student/interviews/${id}`).then((fresh) => {
        setSession((s) => (s && fresh.questions.length === s.questions.length ? fresh : s));
        setLastFeedback((lf) => {
          if (!lf) return lf;
          const q = fresh.questions.find((x) => x.answer && x.answer.text === lf.text);
          return q?.answer || lf;
        });
      }).catch(() => {});
    }, 5000);
    return () => clearInterval(t);
  }, [feedbackPending, id]);

  // ------------------------------------------------------------------ wrap up / complete
  useEffect(() => {
    if (st.status !== S.WRAP_UP || closing || !settings.voiceOn) return;
    setClosing(true);
    say(p.closing).catch(() => {}).finally(() => setClosing(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [st.status]);

  useEffect(() => {
    if (st.status !== S.COMPLETING) return;
    player.current.stop();
    recorder.current.cancel();
    stopMonitoring(); // interview over: camera off, analysis stopped, last events sent
    post(`/student/interviews/${id}/complete`)
      .then((res) => {
        setSession(res.session);
        if (res.report_error) toast(res.report_error, "error");
        if (res.new_badges?.length) toast(`🏅 New badge: ${res.new_badges.join(", ")}`);
        dispatch({ type: "COMPLETED" });
      })
      .catch((e) => dispatch({ type: "COMPLETE_FAILED", error: e.message }));
  }, [st.status, id, toast]);

  // ------------------------------------------------------------------ controls
  const cancelRecording = () => { recId.current++; recorder.current.cancel(); setMicLevel(0); };
  const pause = () => {
    const speechPaused = st.status === S.SPEAKING && player.current.pause();
    if (!speechPaused) player.current.stop();
    if (st.recording) cancelRecording();
    dispatch({ type: "PAUSE", speechPaused, notice: st.recording ? "Recording discarded. You can answer again after resuming." : null });
  };
  const resume = () => { player.current.unlock(); dispatch({ type: "RESUME" }); };
  const start = () => {
    player.current.unlock(); // user gesture: allow audio playback
    if (voice && !voice.stt?.enabled) setInputMode("text");
    if (session.answered && !current && session.answered >= session.planned_questions) { dispatch({ type: "FINISH" }); return; }
    dispatch({ type: "START" });
    runTurn(null); // first (prefetched) question, or the next one after a reconnect
  };
  const replay = () => { cancelRecording(); player.current.stop(); dispatch({ type: "REPLAY" }); };
  const typeInstead = () => { cancelRecording(); setInputMode("text"); dispatch({ type: "TYPE_INSTEAD" }); };
  const toggleMic = () => {
    if (st.recording) finishRef.current();
    else if (st.status === S.LISTENING) { setInputMode("voice"); startRecording(); }
  };
  const toggleVoice = () => {
    if (settings.voiceOn && player.current.speaking) player.current.stop(); // muting mid-question: question stays on screen
    if (settings.voiceOn && st.status === S.SPEAKING) dispatch({ type: "SPEECH_DONE" });
    setSetting({ voiceOn: !settings.voiceOn, captions: settings.voiceOn ? true : settings.captions });
  };
  const endInterview = async () => {
    player.current.stop();
    cancelRecording();
    if (!session?.answered) {
      await stopMonitoring();
      try { await del(`/student/interviews/${id}`); } catch { /* ignore */ }
      navigate("/student/interviews");
      return;
    }
    dispatch({ type: "FINISH" });
  };
  const monitoredCamera = !!(monFeatures?.camera && !monFeatures.withdrawn && camOn);
  // monitoring keeps the camera on; this only hides/shows the self-view (the "Camera on" badge stays visible)
  const toggleCamera = () => { if (monitoredCamera) setCamHidden((h) => !h); };
  useEffect(() => { if (camOn && camVideo.current) camVideo.current.srcObject = camStream.current; }, [camOn]);

  // ------------------------------------------------------------------ render
  if ((st.status === S.INITIALIZING && !session) || (session && !persona)) return <Spinner label="Loading interview…" />;
  if (st.status === S.ERROR && !session) return <ErrorBox message={st.error} onRetry={() => dispatch({ type: "RETRY" })} />;
  if (session?.status === "completed" || st.status === S.COMPLETED) {
    return (
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-bold">{session.job_role} interview with {p.name} - feedback</h1>
          <Link to="/student/interviews"><Button variant="secondary">All interviews</Button></Link>
        </div>
        <InterviewerFeedback session={session} persona={p} voice={voice} rate={settings.rate} />
        <InterviewReport session={session} />
        <MonitoringSummary sessionId={id} />
      </div>
    );
  }
  if (session?.status === "abandoned") return <Notice>This interview was ended without answers.</Notice>;

  const avatarState = avatarStateFor(st.status, {
    greeting: speechKind === "greeting", probing: !!current?.is_followup, reacting, feedback: closing,
  });
  const qNumber = current?.position ?? session?.questions?.length ?? 0;
  const total = session?.planned_questions ?? 0;
  const live = ![S.READY, S.INITIALIZING].includes(st.status);
  const talking = st.status === S.SPEAKING && lipsync !== "silent";
  const showSubs = settings.captions || !settings.voiceOn;
  const timeLeft = answerLimit - recSeconds;
  const answered = session.questions.filter((q) => q.answer);

  return (
    <div className="mx-auto max-w-7xl space-y-3">
      {/* top bar */}
      <div className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-900 px-4 py-3 text-slate-100">
        <div className="mr-auto min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold">
            <span className="rounded-full px-2 py-0.5 text-[11px] text-white" style={{ background: p.ui.accent }}>{p.ui.badge}</span>
            {p.name} · {session.job_role} · {session.category}
          </p>
          <p className="text-xs text-slate-400">Question {Math.min(qNumber, total)} of {total} · {fmtClock(elapsed)}</p>
        </div>
        <span role="status" aria-live="polite" className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
          st.recording ? "bg-red-600" : st.status === S.SPEAKING ? "bg-brand-600" : st.status === S.PAUSED ? "bg-amber-600" : "bg-slate-700"}`}>
          {st.recording && <span className="h-2 w-2 animate-pulse rounded-full bg-white" />}
          {st.recording ? "Recording your answer" : STATUS_LABEL[st.status]}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-200" aria-label="Interview progress">
        <div className="h-full transition-all" style={{ width: `${total ? ((session.answered || 0) / total) * 100 : 0}%`, background: p.ui.accent }} />
      </div>
      {live && (
        <MonitorBar features={monFeatures?.withdrawn ? null : monFeatures} status={monStatus} cameraOn={camOn} cameraLost={camLost}
          recording={st.recording} warning={monWarning} onDismiss={() => setMonWarnings((list) => list.slice(0, -1))}
          onStop={monFeatures && !monFeatures.withdrawn && ![S.COMPLETING, S.COMPLETED].includes(st.status) ? () => stopMonitoring({ withdraw: true }) : null} />
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-3">
          {/* stage: the interviewer is the visual focus */}
          <div className="relative overflow-hidden rounded-2xl bg-slate-800 shadow-lg">
            {use3d ? (
              <Suspense fallback={<div className="flex h-[min(62vh,580px)] w-full items-center justify-center text-sm text-slate-300">Loading {p.name}…</div>}>
                <Avatar3D getVisemes={getVisemes} mode={avatarState} interviewer={p.id} modelUrl={p.ui.model} hdModelUrl={p.ui.hd_model}
                  quality={avatarQuality} label={`${p.name}, AI interviewer`}
                  className="h-[min(62vh,580px)] min-h-[320px] w-full"
                  onFailed={(why) => { setUse3d(false); toast(`${why} Showing a simplified 2D interviewer instead.`, "error"); }} />
              </Suspense>
            ) : (
              <Avatar getMouth={getMouth} mode={avatarState} palette={p.id} className="block h-[min(62vh,580px)] w-full" />
            )}
            <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-full bg-black/55 px-3 py-1 text-xs text-white">
              <span className={`h-2.5 w-2.5 rounded-full ${talking ? "animate-pulse bg-emerald-400" : st.recording ? "bg-red-500" : "bg-slate-400"}`} aria-hidden="true" />
              {p.name} · {p.title}
              <span className="hidden text-slate-300 sm:inline">· {AVATAR_STATE_LABEL[avatarState]}</span>
            </div>
            {lipsync && st.status === S.SPEAKING && (
              <span className="absolute right-3 top-3 z-10 rounded-full bg-black/50 px-3 py-1 text-[11px] text-slate-200">
                {lipsync === "phoneme" ? "local voice · phoneme lip sync" : lipsync === "approx" ? "browser voice · approximate lip sync" : "voice off · read the question"}
              </span>
            )}
            {st.recording && (
              <div className={`absolute right-3 top-12 z-10 flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold text-white ${p.interrupts && timeLeft <= 15 ? "bg-red-600" : "bg-black/55"}`}>
                <Timer size={13} /> {p.interrupts ? `${Math.max(0, timeLeft)} s left` : fmtClock(recSeconds)}
              </div>
            )}
            {camOn && (
              // Hidden self-view stays mounted (transparent) so on-device monitoring keeps working; the status bar
              // above always shows that the camera is on.
              <video ref={camVideo} autoPlay muted playsInline
                className={`absolute bottom-3 right-3 z-10 w-28 -scale-x-100 rounded-lg border-2 border-white/70 shadow sm:w-40 ${camHidden ? "pointer-events-none opacity-0" : ""}`}
                aria-label={monitoredCamera ? "Your camera (analysed only in this browser, not recorded)" : "Your camera preview (not recorded)"} />
            )}
            {live && st.status !== S.WRAP_UP && showSubs && (current || liveText || (talking && player.current.queueActive)) && (
              <div className="absolute inset-x-3 bottom-3 z-10 sm:inset-x-10" style={camOn && !camHidden ? { right: "11rem" } : undefined}>
                <SubtitleLine text={talking && player.current.queueActive ? player.current.queueText()
                  : talking && audioRef.current?.text ? audioRef.current.text
                    : st.status === S.EVALUATING && liveText ? liveText
                      : [current?.preface, current?.text].filter(Boolean).join(" ")}
                  pos={subPos} size={settings.subtitleSize} speaking={talking} />
              </div>
            )}
          </div>

          {st.error && <Notice>{st.error}</Notice>}
          {st.status === S.ERROR && session && (
            <Button onClick={() => { player.current.stop(); recorder.current.cancel(); dispatch({ type: "RETRY" }); }}><RotateCcw size={16} /> Reconnect and continue</Button>
          )}
          {st.notice && !st.error && <Notice tone="sky">{st.notice}</Notice>}

          {/* consent / start */}
          {st.status === S.READY && (session.answered >= session.planned_questions && !current ? (
            <Button onClick={start}><Play size={16} /> Finish interview</Button>
          ) : (
            <InterviewSetup session={session} persona={p} voice={voice} camera={camera.current} answerLimit={answerLimit}
              onUnlockAudio={() => player.current.unlock()} onStart={beginInterview} />
          ))}

          {/* answer dock */}
          {[S.LISTENING, S.TRANSCRIBING, S.REVIEWING, S.EVALUATING].includes(st.status) && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              {st.status === S.LISTENING && inputMode === "voice" && (
                <div className="flex flex-wrap items-center gap-3">
                  <div className="h-2 w-40 overflow-hidden rounded-full bg-slate-200" role="meter" aria-label="Microphone level" aria-valuenow={Math.round(micLevel * 900)} aria-valuemin={0} aria-valuemax={100}>
                    <div className="h-full bg-emerald-500 transition-[width] duration-75" style={{ width: `${Math.min(100, micLevel * 900)}%` }} />
                  </div>
                  <span className="text-xs text-slate-500">{st.recording
                    ? `Recording - it stops after a ${(eosMs / 1000).toFixed(1)} s pause (change in Settings), or press the microphone button when you're done.`
                    : "Microphone is off. Press the microphone button to answer."}</span>
                  <Button size="sm" variant="ghost" className="ml-auto" onClick={typeInstead}><Keyboard size={14} /> Type instead</Button>
                  {st.recording && (appendTo.current || partial) && (
                    <p className="w-full rounded bg-slate-50 px-2 py-1 text-sm italic text-slate-600" aria-live="polite">
                      <span className="text-xs font-semibold not-italic text-slate-500">Heard so far: </span>{[appendTo.current, partial].filter(Boolean).join(" ")}
                    </p>
                  )}
                </div>
              )}
              {st.status === S.LISTENING && inputMode === "text" && (
                <div className="flex items-center gap-3">
                  <Button onClick={() => dispatch({ type: "TYPE_INSTEAD" })}><Keyboard size={16} /> Write my answer</Button>
                  {voice?.stt?.enabled && <Button variant="ghost" onClick={() => setInputMode("voice")}><Mic size={14} /> Use microphone</Button>}
                </div>
              )}
              {st.status === S.TRANSCRIBING && <Spinner label={partial ? "Finishing the transcript…" : "Transcribing your answer locally…"} />}
              {st.status === S.REVIEWING && (
                <div>
                  <label className="label" htmlFor="answer">{inputMode === "voice" ? "Your answer (transcribed - correct any mistakes)" : "Your answer"}</label>
                  <textarea id="answer" className="input" rows={5} maxLength={8000} value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <Button onClick={submit} disabled={!draft.trim()}><Send size={16} /> Submit answer</Button>
                    {voice?.stt?.enabled && draft.trim() && <Button variant="secondary" onClick={() => { appendTo.current = draft.trim(); setInputMode("voice"); dispatch({ type: "RERECORD" }); }}><Mic size={14} /> Continue speaking</Button>}
                    {voice?.stt?.enabled && <Button variant="ghost" onClick={() => { appendTo.current = ""; setInputMode("voice"); setDraft(""); dispatch({ type: "RERECORD" }); }}><RotateCcw size={14} /> Record again</Button>}
                    <span className="ml-auto text-xs text-slate-500">{draft.trim() ? draft.trim().split(/\s+/).length : 0} words</span>
                  </div>
                </div>
              )}
              {st.status === S.EVALUATING && <Spinner label={stage === "question" ? `${p.name} is preparing the next question…` : `${p.name} is considering your answer…`} />}
            </div>
          )}

          {st.status === S.WRAP_UP && (
            <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 bg-white p-6 text-center">
              <p className="font-medium">All {total} questions answered.</p>
              <Button onClick={() => dispatch({ type: "FINISH" })}>Finish & get my feedback</Button>
            </div>
          )}
          {st.status === S.COMPLETING && <Spinner label={`${p.name} is preparing your interview report…`} />}

          {/* control bar */}
          {live && ![S.COMPLETING, S.WRAP_UP].includes(st.status) && (
            <div className="flex flex-wrap items-center justify-center gap-2 rounded-xl bg-slate-900 px-3 py-2" role="toolbar" aria-label="Interview controls">
              <RoundButton label={st.recording ? "Stop recording (I'm done)" : "Turn microphone on"} active={st.recording} danger={st.recording}
                disabled={!st.recording && !(st.status === S.LISTENING && voice?.stt?.enabled)} onClick={toggleMic}>
                {st.recording ? <MicOff size={18} /> : <Mic size={18} />}
              </RoundButton>
              <RoundButton label="Repeat question" disabled={![S.LISTENING, S.REVIEWING].includes(st.status)} onClick={replay}><Volume2 size={18} /></RoundButton>
              {st.status === S.PAUSED
                ? <RoundButton label="Resume" onClick={resume}><Play size={18} /></RoundButton>
                : <RoundButton label="Pause" disabled={![S.PREPARING_SPEECH, S.SPEAKING, S.LISTENING, S.REVIEWING].includes(st.status)} onClick={pause}><Pause size={18} /></RoundButton>}
              <RoundButton label={settings.voiceOn ? "Turn interviewer voice off" : "Turn interviewer voice on"} onClick={toggleVoice}>
                {settings.voiceOn ? <Volume2 size={18} /> : <VolumeX size={18} />}
              </RoundButton>
              {/* The camera runs only when the candidate opted into monitoring at setup; this hides/shows the self-view. */}
              {monitoredCamera && (
                <RoundButton label={camHidden ? "Show my self-view (camera stays on for monitoring)" : "Hide my self-view (camera stays on for monitoring - use Stop monitoring to turn it off)"} onClick={toggleCamera}>
                  {camHidden ? <Camera size={18} /> : <CameraOff size={18} />}
                </RoundButton>
              )}
              <RoundButton label="Settings" active={showSettings} onClick={() => setShowSettings((v) => !v)}><Settings2 size={18} /></RoundButton>
              <ConfirmButton size="sm" variant="danger" className="ml-1 rounded-full"
                message={session?.answered ? "End the interview now and get feedback on the answers so far?" : "End this interview? No answers have been given, so it will be discarded."}
                onConfirm={endInterview}><PhoneOff size={14} /> End</ConfirmButton>
            </div>
          )}
          {lastFeedback?.score != null && (
            <p className="text-sm text-slate-600">Last answer: <b>{lastFeedback.score}/100</b>{lastFeedback.details?.next_difficulty && <> · next question: {lastFeedback.details.next_difficulty}</>}</p>
          )}
          {coaching && lastFeedback?.feedback && (
            <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-slate-700">
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-800">Coaching notes on your last answer</p>
              <p className="whitespace-pre-line">{lastFeedback.feedback}</p>
              {lastFeedback.details?.improvements?.length > 0 && (
                <ul className="mt-2 list-disc pl-5">{lastFeedback.details.improvements.map((x) => <li key={x}>{x}</li>)}</ul>
              )}
            </div>
          )}
        </div>

        {/* right panel */}
        <aside className="space-y-3">
          {showSettings && (
            <Panel title="Settings">
              <div className="space-y-3 text-sm">
                <Toggle label="Interviewer voice" checked={settings.voiceOn} onChange={toggleVoice} />
                <Toggle label="Subtitles / captions" checked={settings.captions || !settings.voiceOn} disabled={!settings.voiceOn}
                  onChange={(v) => setSetting({ captions: v })} hint={!settings.voiceOn ? "Always on while the voice is off." : null} />
                <label className="block">
                  <span className="text-slate-600">Speech speed: {settings.rate.toFixed(2)}×</span>
                  <input type="range" min="0.75" max="1.3" step="0.05" value={settings.rate} className="w-full"
                    onChange={(e) => setSetting({ rate: Number(e.target.value) })} aria-label="Speech speed" />
                  <span className="text-xs text-slate-400">Applies from the next question.</span>
                </label>
                <div>
                  <span className="text-slate-600">Subtitle size</span>
                  <div className="mt-1 flex gap-1">
                    {["sm", "md", "lg"].map((z) => (
                      <button key={z} type="button" onClick={() => setSetting({ subtitleSize: z })} aria-pressed={settings.subtitleSize === z}
                        className={`rounded border px-3 py-1 text-xs ${settings.subtitleSize === z ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300"}`}>
                        {{ sm: "Small", md: "Medium", lg: "Large" }[z]}
                      </button>
                    ))}
                  </div>
                </div>
                <Toggle label="Turn the microphone on automatically" checked={settings.autoMic} onChange={(v) => setSetting({ autoMic: v })} />
                <label className="block">
                  <span className="text-slate-600">Stop recording after a pause of {(eosMs / 1000).toFixed(1)} s</span>
                  <input type="range" min="600" max="4000" step="100" value={eosMs} className="w-full"
                    onChange={(e) => setSetting({ endOfSpeechMs: Number(e.target.value) })} aria-label="Pause that ends an answer (milliseconds)" />
                  <span className="text-xs text-slate-400">Raise it if you get cut off while thinking. You can always press "Continue speaking" to add more.
                    {settings.endOfSpeechMs && <button type="button" className="ml-1 underline" onClick={() => setSetting({ endOfSpeechMs: null })}>Use the default</button>}</span>
                </label>
                <Toggle label="Send my answer automatically after it is transcribed" checked={settings.autoSend} onChange={(v) => setSetting({ autoSend: v })}
                  hint="Off: you can read and correct the text first." />
                {use3d && (
                  <div>
                    <span className="text-slate-600">Interviewer graphics</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {Object.entries(AVATAR_QUALITY).map(([q, name]) => (
                        <button key={q} type="button" onClick={() => { saveQuality(q); setAvatarQuality(q); }} aria-pressed={avatarQuality === q}
                          className={`rounded border px-3 py-1 text-xs ${avatarQuality === q ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300"}`}>
                          {name}
                        </button>
                      ))}
                    </div>
                    <span className="text-xs text-slate-400">Use Performance if the interviewer stutters. Changing it reloads the 3D view.</span>
                  </div>
                )}
                <label className="block">
                  <span className="text-slate-600">Language</span>
                  <select className="input mt-1" value="en" disabled aria-describedby="lang-note"><option value="en">English</option></select>
                  <span id="lang-note" className="text-xs text-slate-400">The local speech models (Kokoro voice, Whisper base.en) support English only.</span>
                </label>
              </div>
            </Panel>
          )}
          <Panel title="Progress">
            <div className="grid grid-cols-3 gap-2 text-center">
              <Stat label="Question" value={`${Math.min(qNumber, total)}/${total}`} />
              <Stat label="Answered" value={session.answered || 0} />
              <Stat label="Duration" value={fmtClock(elapsed)} />
            </div>
          </Panel>
          <Panel title="Transcript">
            <ol className="max-h-72 space-y-3 overflow-y-auto pr-1 text-sm" aria-live="polite">
              {session.questions.map((q) => (
                <li key={q.id}>
                  <p className="text-xs font-semibold" style={{ color: p.ui.accent }}>{p.name} · Q{q.position}{q.is_followup ? " · follow-up" : ""}</p>
                  <p className="text-slate-800">{q.text}</p>
                  {q.answer
                    ? <p className="mt-1 rounded bg-slate-50 px-2 py-1 text-slate-600"><span className="text-xs font-semibold text-slate-500">You: </span>{q.answer.text}</p>
                    : st.status === S.REVIEWING && draft && <p className="mt-1 rounded border border-dashed border-slate-300 px-2 py-1 italic text-slate-500">{draft}</p>}
                </li>
              ))}
              {!answered.length && !current && <li className="text-slate-400">The conversation will appear here.</li>}
            </ol>
          </Panel>
          <Panel title="My notes (private)">
            <textarea className="input text-sm" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={4000}
              placeholder="Jot down points to remember. Notes stay in this browser and are never sent or scored." aria-label="Interview notes" />
          </Panel>
          <Link to={`/student/interviews/${id}`} className="block text-center text-xs text-slate-500 hover:underline">Switch to text view</Link>
        </aside>
      </div>
    </div>
  );
}

/** Subtitles: exactly what is being said (greeting included); the word being spoken is highlighted. */
function SubtitleLine({ text: full, pos, size, speaking }) {
  let body = <span>{full}</span>;
  if (speaking && pos != null) {
    const at = Math.round(pos * full.length);
    const startIdx = full.lastIndexOf(" ", Math.max(0, at - 1)) + 1;
    const endIdx = full.indexOf(" ", at);
    const end = endIdx === -1 ? full.length : endIdx;
    body = (
      <>
        <span className="text-white">{full.slice(0, startIdx)}</span>
        <span className="rounded bg-brand-500 px-0.5 text-white">{full.slice(startIdx, end)}</span>
        <span className="text-slate-300">{full.slice(end)}</span>
      </>
    );
  }
  return <p className={`rounded-lg bg-slate-900/85 px-4 py-2 text-center text-white ${SUB_SIZE[size] || SUB_SIZE.md}`} aria-live="polite">{body}</p>;
}

function RoundButton({ label, children, onClick, disabled, active, danger }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={label} title={label} aria-pressed={active || undefined}
      className={`flex h-11 w-11 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-40 ${
        danger ? "bg-red-600 text-white hover:bg-red-700" : active ? "bg-brand-600 text-white" : "bg-slate-700 text-white hover:bg-slate-600"}`}>
      {children}
    </button>
  );
}

function Panel({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h2>
      {children}
    </section>
  );
}

function Stat({ label, value }) {
  return <div><p className="text-lg font-semibold">{value}</p><p className="text-[11px] text-slate-500">{label}</p></div>;
}

function Toggle({ label, checked, onChange, disabled, hint }) {
  return (
    <label className={`flex items-start gap-2 ${disabled ? "opacity-60" : ""}`}>
      <input type="checkbox" className="mt-0.5" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}{hint && <span className="block text-xs text-slate-400">{hint}</span>}</span>
    </label>
  );
}
