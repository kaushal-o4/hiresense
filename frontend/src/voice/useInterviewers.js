import { useEffect, useState } from "react";
import { get } from "../api";

// Interviewer personalities come from the server (GET /api/interviewers) - one source of truth for names,
// voices and behaviour. Cached for the page's lifetime.
let cache = null;

export function useInterviewers() {
  const [state, setState] = useState(() => ({ list: cache, error: null }));
  useEffect(() => {
    if (cache) return;
    let alive = true;
    get("/interviewers")
      .then((list) => { cache = list; if (alive) setState({ list, error: null }); })
      .catch((e) => alive && setState({ list: null, error: e.message }));
    return () => { alive = false; };
  }, []);
  return state;
}

export function findInterviewer(list, id) {
  return list?.find((i) => i.id === id) || list?.find((i) => i.id === "aria") || null;
}

/** /voice/speak body for an interviewer, with the student's speed preference applied on top of the persona's. */
export function speakBody(persona, text, userRate = 1) {
  const speed = Math.min(1.4, Math.max(0.7, (persona?.tts_speed || 1) * (userRate || 1)));
  return { text: text.slice(0, 1500), voice: persona?.tts_voice, speed: Math.round(speed * 100) / 100 };
}

/** Options for SpeechPlayer.playBrowser (browser-voice fallback). */
export function browserVoiceOpts(persona, userRate = 1) {
  const b = persona?.browser_voice || {};
  return { lang: b.lang || "en-US", gender: b.gender || null, pitch: b.pitch || 1,
    rate: Math.min(1.6, Math.max(0.6, (persona?.tts_speed || 1) * (userRate || 1))) };
}

export const FILTERS = [
  { id: "all", label: "All interviewers" },
  { id: "friendly", label: "Friendly Interview" },
  { id: "standard", label: "Standard Interview" },
  { id: "strict", label: "Strict Technical Interview" },
  { id: "stress", label: "Stress Interview" },
  { id: "hr", label: "HR Interview" },
  { id: "english", label: "English Confidence Practice" },
];
