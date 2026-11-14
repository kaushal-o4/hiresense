// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/useSpeechAndPreferences.jsx
//
// FILE PURPOSE:
// Browser speech helpers for the English practice pages: speech-to-text, text-to-speech, subtitles and
// voice preferences.
//
// WHAT THIS FILE DOES:
// 1. usePrefs(): reads speech language, subtitles and speech rate from the user's preferences.
// 2. useSpeechToText(): uses the browser Web Speech API to turn the microphone into text.
// 3. useSpeaker(): reads text aloud with browser speechSynthesis and tracks the current word for
//    subtitles.
// 4. Subtitles: caption bar that highlights the word being spoken.
// 5. speak()/stopSpeaking(): simple fire-and-forget speech.
//
// HOW THIS FILE WORKS:
// These are React hooks around the browser's SpeechRecognition and speechSynthesis APIs.
//
// IMPORTANT FUNCTIONS:
//    - usePrefs()
//        Returns the user's speech language, subtitle and rate preferences.
//    - useSpeechToText()
//        Starts/stops browser speech recognition and returns the transcript.
//    - useSpeaker()
//        Speaks text and exposes subtitle state.
//    - Subtitles()
//        Shows highlighted subtitles while speaking.
//    - speak()
//        Back-compat helpers for places that only need fire-and-forget speech.
//    Other helper functions: stopSpeaking
//
// INPUT:
// User preferences; microphone audio; text to speak.
//
// OUTPUT:
// Transcripts, spoken audio and subtitle UI.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: AuthContext.jsx
//    Used by: pages/AccountSettings.jsx, pages/student/EnglishAvatarSession.jsx,
//    pages/student/EnglishSession.jsx, pages/student/InterviewSession.jsx,
//    pages/student/InterviewerPicker.jsx, pages/student/LiveVoiceInterview.jsx
//
// IMPORTANT DEPENDENCIES:
//    react
//
// IMPORTANT NOTE:
// In Chrome/Edge the Web Speech API sends audio to Google/Microsoft. The live AI interview does NOT
// use it; it uses voice/recorder.js and the backend Whisper model.
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../AuthContext";

// Browser speech-to-text (Web Speech API, supported in Chrome/Edge) and text-to-speech.
// PRIVACY NOTE: in Chrome and Edge the Web Speech API sends microphone audio to Google/Microsoft speech
// servers. It is used only by the English-practice pages. The live AI interview uses local recognition instead
// (src/voice/recorder.js + backend Whisper), so interview audio stays on this server.

const Recognition = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

export function usePrefs() {
  const { user } = useAuth();
  const p = user?.preferences || {};
  return { speech_lang: p.speech_lang || "en-IN", subtitles: p.subtitles !== false, speech_rate: p.speech_rate || 1 };
}

export function useSpeechToText() {
  const { speech_lang: lang } = usePrefs();
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState(null);
  const recRef = useRef(null);
  const confidences = useRef([]);

  const supported = !!Recognition;

  const start = useCallback(() => {
    if (!Recognition) return setError("Voice input is not supported in this browser. Please use Chrome or Edge.");
    setError(null);
    const rec = new Recognition();
    rec.lang = lang;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let finalText = "";
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) {
          finalText += r[0].transcript;
          if (typeof r[0].confidence === "number" && r[0].confidence > 0) confidences.current.push(r[0].confidence);
        } else interimText += r[0].transcript;
      }
      if (finalText) setTranscript((t) => (t ? `${t} ${finalText.trim()}` : finalText.trim()));
      setInterim(interimText);
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed") setError("Microphone permission was denied.");
      else if (e.error !== "no-speech" && e.error !== "aborted") setError(`Speech recognition error: ${e.error}`);
    };
    rec.onend = () => { setListening(false); setInterim(""); };
    recRef.current = rec;
    rec.start();
    setListening(true);
  }, [lang]);

  const stop = useCallback(() => { recRef.current?.stop(); setListening(false); }, []);

  const reset = useCallback(() => { setTranscript(""); setInterim(""); confidences.current = []; }, []);

  const avgConfidence = () => {
    const c = confidences.current;
    return c.length ? c.reduce((a, b) => a + b, 0) / c.length : null;
  };

  useEffect(() => () => recRef.current?.abort(), []);

  return { supported, listening, transcript, setTranscript, interim, error, start, stop, reset, avgConfidence };
}

/** Text-to-speech with live subtitle tracking (the word currently being spoken). */
export function useSpeaker() {
  const { speech_lang, speech_rate, subtitles } = usePrefs();
  const [sub, setSub] = useState({ text: "", index: 0, speaking: false });

  const speak = useCallback((text) => {
    if (typeof window === "undefined" || !window.speechSynthesis || !text) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = speech_lang;
    u.rate = speech_rate;
    u.onstart = () => setSub({ text, index: 0, speaking: true });
    u.onboundary = (e) => setSub((s) => ({ ...s, index: e.charIndex }));
    u.onend = () => setSub((s) => ({ ...s, index: text.length, speaking: false }));
    u.onerror = () => setSub((s) => ({ ...s, speaking: false }));
    window.speechSynthesis.speak(u);
  }, [speech_lang, speech_rate]);

  const stop = useCallback(() => {
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
    setSub((s) => ({ ...s, speaking: false }));
  }, []);

  useEffect(() => () => { if (typeof window !== "undefined") window.speechSynthesis?.cancel(); }, []);

  return { speak, stop, subtitle: sub, showSubtitles: subtitles };
}

/** Caption bar shown while the AI is speaking; spoken words are highlighted. */
export function Subtitles({ subtitle, show }) {
  if (!show || !subtitle.speaking || !subtitle.text) return null;
  const done = subtitle.text.slice(0, subtitle.index);
  const rest = subtitle.text.slice(subtitle.index);
  const [current, ...after] = rest.split(/(?<=\s)/);
  return (
    <div className="fixed inset-x-0 bottom-6 z-40 flex justify-center px-4" aria-live="polite">
      <p className="max-w-3xl rounded-xl border border-snow/10 bg-night-950/80 px-5 py-2.5 text-center text-base leading-relaxed text-slate-600 shadow-pop backdrop-blur-xl">
        <span className="text-snow">{done}</span>
        <span className="rounded bg-brand-500/80 px-1 text-snow shadow-[0_0_12px_rgb(99_102_241/0.6)]">{current}</span>
        <span>{after.join("")}</span>
      </p>
    </div>
  );
}

// Back-compat helpers for places that only need fire-and-forget speech.
export function speak(text, lang = "en-IN", rate = 1) {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang;
  u.rate = rate;
  window.speechSynthesis.speak(u);
}

export function stopSpeaking() {
  if (typeof window !== "undefined") window.speechSynthesis?.cancel();
}
