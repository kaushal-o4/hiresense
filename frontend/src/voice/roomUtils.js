/* Small helpers and defaults of the live interview room (pages/student/VoiceInterview.jsx). */

// Used only if the interviewer list cannot be loaded: the original Aria behaviour.
export const FALLBACK = {
  id: "aria", name: "Aria", title: "Friendly interviewer", tts_voice: undefined, tts_speed: 1, interrupts: false,
  answer_seconds: 180, browser_voice: { gender: "female", lang: "en-US", pitch: 1.05 },
  ui: { accent: "#0ea5e9", model: "/avatars/interviewer.glb", badge: "Friendly" },
  greeting: "Hi, I'm Aria, and I'll be your interviewer today for the {role} role. Take your time with each answer. Let's begin.",
  reactions: ["Thank you. Let me think about that for a moment.", "Okay, thanks for that. Give me a second."],
  closing: "Thank you, that was my last question. When you are ready, press Finish and I will prepare your feedback.",
};
export const INTERJECTION = "Let me stop you there. I have what I need.";
export const REACTION_MS = 1800; // how long the avatar visibly reacts after an answer before it starts "thinking"

// endOfSpeechMs: null = the default for the chosen response mode (from /voice/status). autoSend: submit the
// transcript right after it is ready instead of waiting for the Submit button.
// Settings version 2 (2026-10-29): answers are sent automatically by default, like talking to a live interviewer;
// "autoSend" saved by an older version is dropped once so the new default applies.
export const DEFAULT_SETTINGS = { v: 2, voiceOn: true, rate: 1, captions: true, subtitleSize: "md", autoMic: true, endOfSpeechMs: null, autoSend: true };
export function savedSettings(raw) {
  const saved = JSON.parse(raw || "{}");
  if (saved.v !== 2) { delete saved.autoSend; delete saved.v; }
  return saved;
}
export const splitSentences = (t) => (t || "").split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
export const turnId = () => Math.random().toString(36).slice(2) + Date.now().toString(36);

export const fmtClock = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
const store = (kind) => ({
  get: (k) => { try { return window[kind].getItem(k); } catch { return null; } },
  set: (k, v) => { try { window[kind].setItem(k, v); } catch { /* private mode */ } },
});
export const sessionStore = store("sessionStorage");
export const localStore = store("localStorage");

export function currentQuestion(session) {
  const q = session?.questions?.[session.questions.length - 1];
  return q && !q.answer ? q : null;
}
