/*
 * Live voice interview with an animated interviewer (route /student/interviews/:id/live).
 * Flow: InterviewSetup (consent + device check) -> the interviewer speaks each question (SpeechPlayer, lip sync) ->
 * the student answers by microphone (MicRecorder -> server Whisper) or by typing -> the answer is sent with streamTurn
 * (POST .../turn, Server-Sent Events), which returns the score and streams the next question -> Finish
 * (POST .../complete) -> InterviewerFeedback + InterviewReport. The screen state lives in voice/interviewMachine.js
 * (a pure reducer); camera and integrity monitoring run through monitoring/*.
 * Timing-sensitive: change with care and re-run the voice E2E tests in backend/tests_e2e.
 */

import { Suspense, lazy, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Lightbulb, Play, RotateCcw, Timer } from "lucide-react";
import { api, del, get, post } from "../../api";
import { usePrefs } from "../../components/useSpeech";
import { Button, ErrorBox, Notice, Spinner, useToast } from "../../components/ui";
import Avatar from "../../voice/Avatar";
// three.js is large: load the 3D interviewer only when this page is opened.
const Avatar3D = lazy(() => import("../../voice/Avatar3D"));
import { AVATAR_STATE_LABEL, avatarStateFor, storedQuality } from "../../voice/avatarStates";
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
import { scoreBand } from "../../components/scoreBand";

import { DEFAULT_SETTINGS, FALLBACK, INTERJECTION, REACTION_MS, currentQuestion, fmtClock, localStore as local, savedSettings,
  sessionStore as session_, splitSentences, turnId } from "../../voice/roomUtils";
import { SubtitleLine } from "../../voice/RoomParts";
import AnswerDock from "../../voice/AnswerDock";
import ControlBar from "../../voice/ControlBar";
import RoomSettingsPanel from "../../voice/RoomSettingsPanel";
import RoomSidePanels from "../../voice/RoomSidePanels";

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
    try { return { ...DEFAULT_SETTINGS, rate: speech_rate || 1, ...savedSettings(local.get("hs-room-settings")) }; } catch { return DEFAULT_SETTINGS; }
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
  const levelAt = useRef(0); // last mic-meter update (throttled)
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
  const eosMs = settings.endOfSpeechMs || voice?.recognition?.end_of_speech_ms?.[coaching ? "coaching" : "fast"] || (coaching ? 3000 : 2000);
  // ---- streaming turns, partial transcripts, monitoring
  const t0 = useRef(performance.now()); // interview-relative clock for integrity events
  const turnBusy = useRef(false); // a streamed turn owns speech preparation (PREPARING_SPEECH effect stays idle)
  const queueDone = useRef(null); // promise of the streamed speech queue currently playing
  const reaction = useRef(Promise.resolve());
  const [liveText, setLiveText] = useState(""); // next question appearing as it is written
  const [stage, setStage] = useState(null); // "scoring" | "question"
  const [partial, setPartial] = useState(""); // live transcript while the student is speaking
  const partials = useRef([]);
  const segTexts = useRef([]); // finished pieces' text by index (requests can finish out of order)
  const cutAt = useRef(0); // where the latest finished piece ended (recorder chunk index)
  const interim = useRef(null); // latest live caption request: {from, to, promise, done}
  const appendTo = useRef("");
  const camera = useRef(null);
  if (!camera.current) camera.current = new CameraSession();
  const monitor = useRef(null);
  const [monFeatures, setMonFeatures] = useState(null);
  const [monStatus, setMonStatus] = useState(null);
  // Active monitoring warnings, newest last. The newest is shown; clearing or dismissing it brings back any older
  // warning that is still active (one warning must never hide another, e.g. "face not visible" under "pasted text").
  const [monWarnings, setMonWarnings] = useState([]);
  // the newest is shown, except that an actionable one (return to full screen) is never covered by another
  const monWarning = monWarnings.find((w) => w.type === "fullscreen_exit") || monWarnings[monWarnings.length - 1] || null;
  const setMonWarning = (w) => setMonWarnings(w ? (list) => [...list.filter((x) => x.type !== w.type), w] : []);
  const onMonWarning = (w) => setMonWarnings((list) => (w.clear ? list.filter((x) => x.type !== w.clear)
    : [...list.filter((x) => x.type !== w.type), w]));
  const [camHidden, setCamHidden] = useState(false);
  const [camLost, setCamLost] = useState(false);
  const [micProblem, setMicProblem] = useState(null); // microphone failed during the interview
  const monPolicy = useRef(null); // admin security settings as shown on the setup screen
  const monBaseline = useRef(null); // calibrated neutral viewing position (setup screen), if any
  const pauseRef = useRef(null);

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

  const beginInterview = ({ features, policy, baseline, elapsedMs = 0 }) => {
    // the interview clock started at the first consent; after a reload it continues instead of restarting at 0
    t0.current = performance.now() - elapsedMs;
    monPolicy.current = policy || null;
    monBaseline.current = baseline || null;
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
      sessionId: id, features: monFeatures, t0: t0.current, policy: monPolicy.current, baseline: monBaseline.current,
      onStatus: setMonStatus,
      onWarning: onMonWarning,
      onPauseRequest: () => pauseRef.current?.("face_absent"),
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
    segTexts.current = [];
    cutAt.current = 0;
    interim.current = null;
    setPartial("");
    const qid = current?.id;
    const showLive = (interimText) => setPartial([...segTexts.current.filter(Boolean), interimText].filter(Boolean).join(" "));
    const upload = (clip, name, extra = {}) => {
      const fd = new FormData();
      fd.append("question_id", String(qid));
      fd.append("partial", "true");
      Object.entries(extra).forEach(([k, v]) => fd.append(k, v));
      fd.append("audio", new Blob([clip.wav], { type: "audio/wav" }), name);
      return api(`/student/interviews/${id}/transcribe`, { method: "POST", body: fd });
    };
    try {
      await recorder.current.start({
        silenceMs: eosMs, // end-of-speech timeout (adjustable in Settings)
        minAnswerMs: voice?.recognition?.min_speech_ms ?? 1200,
        maxSeconds: p.interrupts ? answerLimit : Math.max(answerLimit, 180),
        onLevel: (l, dt) => {
          monitor.current?.audioLevel(l, dt);
          // the meter re-renders this whole page: ~12 updates/s are enough and leave frames for the avatar
          const now = performance.now();
          if (now - levelAt.current >= 80) { levelAt.current = now; setMicLevel(l); }
        },
        onEnded: () => { // unplugged / disabled mid-answer
          monitor.current?.micLost("ended");
          setMicProblem("The microphone disconnected. Reconnect it, or type your answer.");
          finishRef.current?.(myId);
        },
        onSilence: () => finishRef.current?.(myId),
        onMax: () => finishRef.current?.(myId, { interrupted: p.interrupts }),
        onNoSpeech: () => toast("We can't hear you yet. Check your microphone, or type your answer.", "error"),
        // Live partial transcript: each stretch of speech is transcribed while the student keeps talking.
        onSegment: voice?.stt?.enabled && qid ? (seg) => {
          const t = performance.now();
          cutAt.current = seg.to;
          partials.current[seg.index] = upload(seg, `part${seg.index}.wav`)
            .then((r) => {
              reportMetric("client.stt_partial", performance.now() - t, { audio_s: Math.round(seg.seconds) });
              segTexts.current[seg.index] = r.text;
              if (myId === recId.current || stRef.current.status === S.TRANSCRIBING) {
                const live = interim.current?.done && interim.current.from >= cutAt.current ? interim.current.text : "";
                showLive(live);
              }
              return r;
            })
            .catch(() => null);
        } : undefined,
        // Live captions of the piece being spoken (one request at a time). The latest one also serves as the final
        // text when it already reaches the end of the speech, so nothing is left to transcribe after the pause.
        interimBusy: () => !!interim.current && !interim.current.done,
        onInterim: voice?.stt?.enabled && voice.stt.live_captions !== false && qid ? (clip) => {
          const t = performance.now();
          const it = { from: clip.from, to: clip.to, done: false, text: "" };
          it.promise = upload(clip, "live.wav", { live: "true" })
            .then((r) => {
              reportMetric("client.stt_live", performance.now() - t, { audio_s: Math.round(clip.seconds) });
              Object.assign(it, { done: true, text: r.text || "" });
              if (myId === recId.current && it.from >= cutAt.current) showLive(it.text);
              return r;
            })
            .catch(() => { it.done = true; it.failed = true; return null; });
          interim.current = it;
        } : undefined,
      });
      if (myId !== recId.current) { recorder.current.cancel(); return; }
      setMicProblem(null);
      monitor.current?.audioStart();
      dispatch({ type: "RECORD_START" });
    } catch (e) {
      if (e.name === "NotFoundError" || e.name === "NotReadableError") {
        monitor.current?.micLost(e.name === "NotFoundError" ? "not_found" : "not_readable");
        setMicProblem(e.message);
      }
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
    monitor.current?.audioStop();
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
      // Only the last piece is transcribed now; earlier pieces were transcribed while the student was speaking. If the
      // latest live caption already covers all of the last piece's speech, its text is used and nothing is sent.
      const it = interim.current;
      const covered = it && !it.failed && it.from === clip.from && it.to >= clip.speechTo;
      const noTailSpeech = usedSegments && clip.speechTo <= clip.from;
      const tail = covered ? it.promise.then((r) => r || { text: "" })
        : noTailSpeech || clip.seconds < 0.4 ? Promise.resolve({ text: "" })
        : api(`/student/interviews/${id}/transcribe`, { method: "POST", body: fd });
      interim.current = null;
      const [parts, r] = await Promise.all([Promise.all(partials.current), tail]);
      partials.current = [];
      setPartial("");
      const pieces = [...parts.filter(Boolean), r];
      const text = [prefix, ...pieces.map((x) => x.text)].filter(Boolean).join(" ").trim();
      reportMetric("client.stt_roundtrip", performance.now() - tStop, { segments: parts.length, reused_live: covered ? 1 : 0 });
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
    // A short spoken acknowledgement in the interviewer's style plays at once while the answer is scored (audio
    // pre-synthesised at server start, so it costs nothing): without it the room was silent for the whole scoring +
    // first-sentence wait. The next question takes longer than the acknowledgement, so it is never delayed by it.
    reaction.current = Promise.resolve();
    if (settings.voiceOn && p.reactions?.length) {
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
  const cancelRecording = () => { recId.current++; recorder.current.cancel(); monitor.current?.audioStop(); setMicLevel(0); };
  const pause = (reason = "manual") => {
    const speechPaused = st.status === S.SPEAKING && player.current.pause();
    if (!speechPaused) player.current.stop();
    if (st.recording) cancelRecording();
    monitor.current?.paused(reason);
    const notice = reason === "face_absent"
      ? "The interview is paused because your face has not been visible for a while. Adjust your camera, then press Resume."
      : st.recording ? "Recording discarded. You can answer again after resuming." : null;
    dispatch({ type: "PAUSE", speechPaused, notice });
  };
  // admin pause rule (security settings): only pauses a running interview; never ends or fails it
  pauseRef.current = (reason) => {
    if ([S.PREPARING_SPEECH, S.SPEAKING, S.LISTENING, S.REVIEWING].includes(st.status)) pause(reason); // as the Pause button
  };
  const resume = () => { player.current.unlock(); monitor.current?.resumed(); dispatch({ type: "RESUME" }); };
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

  return (
    <div className="mx-auto max-w-7xl space-y-3">
      {/* top bar */}
      <div className="card relative overflow-hidden">
        <div className="flex flex-wrap items-center gap-3 px-4 py-3">
          <div className="mr-auto min-w-0">
            <p className="flex flex-wrap items-center gap-x-2 text-sm">
              <span className="font-semibold text-slate-900">{p.name}</span>
              <span className="text-slate-400">·</span><span className="text-slate-600">{session.job_role}</span>
              <span className="text-slate-400">·</span><span className="text-slate-600">{session.category}</span>
            </p>
            <p className="num text-xs text-slate-500">Question {Math.min(qNumber, total)} of {total} · {fmtClock(elapsed)}</p>
          </div>
          <span role="status" aria-live="polite" className={`inline-flex items-center gap-2 rounded-md px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${
            st.recording ? "bg-rose-50 text-rose-700 ring-rose-200" : st.status === S.SPEAKING ? "bg-brand-50 text-brand-700 ring-brand-200"
              : st.status === S.PAUSED ? "bg-amber-50 text-amber-800 ring-amber-200" : "bg-slate-100 text-slate-700 ring-slate-200"}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${st.recording ? "animate-pulse bg-rose-500" : st.status === S.SPEAKING ? "animate-pulse bg-brand-500" : st.status === S.PAUSED ? "bg-amber-500" : "bg-slate-400"}`} />
            {st.recording ? "Recording your answer" : STATUS_LABEL[st.status]}
          </span>
        </div>
        <div className="h-0.5 bg-slate-100" aria-label="Interview progress">
          <div className="h-full bg-gradient-to-r from-brand-500 to-violet-500 transition-all" style={{ width: `${total ? ((session.answered || 0) / total) * 100 : 0}%` }} />
        </div>
      </div>
      {live && (
        <MonitorBar features={monFeatures?.withdrawn ? null : monFeatures} status={monStatus} cameraOn={camOn} cameraLost={camLost} micProblem={micProblem}
          recording={st.recording} warning={monWarning} onDismiss={() => setMonWarnings((list) => list.slice(0, -1))}
          onStop={monFeatures && !monFeatures.withdrawn && ![S.COMPLETING, S.COMPLETED].includes(st.status) ? () => stopMonitoring({ withdraw: true }) : null} />
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-3">
          {/* stage: the interviewer is the visual focus */}
          <div className={`relative overflow-hidden rounded-2xl bg-night-900 ring-1 transition-shadow duration-500 ${st.recording ? "ring-rose-400/50 shadow-[0_0_0_1px_rgb(251_113_133/0.35),0_0_60px_-12px_rgb(244_63_94/0.6)]"
              : talking ? "ring-brand-400/45 shadow-[0_0_0_1px_rgb(129_140_248/0.3),0_0_60px_-12px_rgb(99_102_241/0.65)]"
                : "ring-slate-200 shadow-[0_30px_60px_-30px_rgb(0_0_0/0.9)]"}`}>
            {use3d ? (
              <Suspense fallback={<div className="flex h-[min(62vh,580px)] w-full items-center justify-center text-sm text-slate-600">Loading {p.name}…</div>}>
                <Avatar3D getVisemes={getVisemes} mode={avatarState} interviewer={p.id} modelUrl={p.ui.model} hdModelUrl={p.ui.hd_model}
                  quality={avatarQuality} label={`${p.name}, AI interviewer`}
                  className="h-[min(62vh,580px)] min-h-[320px] w-full"
                  onFailed={(why) => { setUse3d(false); toast(`${why} Showing a simplified 2D interviewer instead.`, "error"); }} />
              </Suspense>
            ) : (
              <Avatar getMouth={getMouth} mode={avatarState} palette={p.id} className="block h-[min(62vh,580px)] w-full" />
            )}
            <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-full border border-snow/10 bg-black/45 px-3 py-1 text-xs text-snow backdrop-blur-md">
              <span className={`h-2 w-2 rounded-full ${talking ? "animate-pulse bg-emerald-400 shadow-[0_0_8px_rgb(52_211_153)]" : st.recording ? "animate-pulse bg-rose-500 shadow-[0_0_8px_rgb(244_63_94)]" : "bg-slate-500"}`} aria-hidden="true" />
              {p.name} · {p.title}
              <span className="hidden text-slate-600 sm:inline">· {AVATAR_STATE_LABEL[avatarState]}</span>
            </div>
            {lipsync && st.status === S.SPEAKING && (
              <span className="absolute right-3 top-3 z-10 rounded-full border border-snow/10 bg-black/45 px-3 py-1 text-[11px] text-slate-700 backdrop-blur-md">
                {lipsync === "phoneme" ? "local voice · phoneme lip sync" : lipsync === "approx" ? "browser voice · approximate lip sync" : "voice off · read the question"}
              </span>
            )}
            {st.recording && (
              <div className={`absolute right-3 top-12 z-10 flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold text-snow backdrop-blur-md ${p.interrupts && timeLeft <= 15 ? "bg-rose-600 shadow-[0_0_18px_rgb(244_63_94/0.7)]" : "border border-snow/10 bg-black/45"}`}>
                <Timer size={13} /> {p.interrupts ? `${Math.max(0, timeLeft)} s left` : fmtClock(recSeconds)}
              </div>
            )}
            {camOn && (
              // Hidden self-view stays mounted (transparent) so on-device monitoring keeps working; the status bar
              // above always shows that the camera is on.
              <video ref={camVideo} autoPlay muted playsInline
                className={`absolute bottom-3 right-3 z-10 w-28 -scale-x-100 rounded-xl border border-snow/25 shadow-pop ring-1 ring-black/40 sm:w-40 ${camHidden ? "pointer-events-none opacity-0" : ""}`}
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
            <AnswerDock st={st} dispatch={dispatch} inputMode={inputMode} setInputMode={setInputMode} micLevel={micLevel} eosMs={eosMs}
              typeInstead={typeInstead} appendTo={appendTo} partial={partial} sttEnabled={voice?.stt?.enabled} draft={draft}
              setDraft={setDraft} submit={submit} stage={stage} interviewerName={p.name} />
          )}

          {st.status === S.WRAP_UP && (
            <div className="card flex flex-col items-center gap-3 p-6 text-center">
              <p className="font-medium">All {total} questions answered.</p>
              <Button onClick={() => dispatch({ type: "FINISH" })}>Finish & get my feedback</Button>
            </div>
          )}
          {st.status === S.COMPLETING && <Spinner label={`${p.name} is preparing your interview report…`} />}

          {/* control bar */}
          {live && ![S.COMPLETING, S.WRAP_UP].includes(st.status) && (
            <ControlBar st={st} sttEnabled={voice?.stt?.enabled} toggleMic={toggleMic} replay={replay} resume={resume} pause={pause}
              voiceOn={settings.voiceOn} toggleVoice={toggleVoice} monitoredCamera={monitoredCamera} camHidden={camHidden}
              toggleCamera={toggleCamera} showSettings={showSettings} setShowSettings={setShowSettings}
              answered={session?.answered} endInterview={endInterview} />
          )}
          {lastFeedback?.score != null && (
            <p className="text-center text-sm text-slate-500">Last answer <b className={`num font-semibold ${lastFeedback.score >= 75 ? "text-emerald-700" : lastFeedback.score >= 50 ? "text-amber-700" : "text-rose-700"}`}>{lastFeedback.score}/100</b> <span className="text-slate-400">({scoreBand(lastFeedback.score).label})</span>{lastFeedback.details?.next_difficulty && <> · next question {lastFeedback.details.next_difficulty}</>}</p>
          )}
          {coaching && lastFeedback?.feedback && (
            <div className="card p-4 text-sm leading-relaxed text-slate-700">
              <p className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-slate-900"><Lightbulb size={15} className="text-amber-600" /> Coaching notes on your last answer</p>
              <p className="whitespace-pre-line">{lastFeedback.feedback}</p>
              {lastFeedback.details?.improvements?.length > 0 && (
                <ul className="mt-3 space-y-1.5">{lastFeedback.details.improvements.map((x) => <li key={x} className="flex gap-2"><span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-slate-400" />{x}</li>)}</ul>
              )}
            </div>
          )}
        </div>

        {/* right panel */}
        <aside className="space-y-3">
          {showSettings && (
            <RoomSettingsPanel settings={settings} setSetting={setSetting} toggleVoice={toggleVoice} eosMs={eosMs} use3d={use3d}
              avatarQuality={avatarQuality} setAvatarQuality={setAvatarQuality} />
          )}
          <RoomSidePanels id={id} session={session} interviewerName={p.name} qNumber={qNumber} total={total} elapsed={elapsed}
            reviewingDraft={st.status === S.REVIEWING && draft} hasCurrent={!!current} notes={notes} setNotes={setNotes} />
        </aside>
      </div>
    </div>
  );
}
