// Conversation loop for spoken-English practice with Aria. Pure: transition(state, event) -> new state, and
// disallowed events are ignored (no recording while Aria speaks, no double sends).
//
// Aria speaks -> microphone opens -> student talks -> silence or "Done" -> transcribe -> Aria thinks -> Aria speaks...
// Unlike the interview there is no review step: the reply is sent as soon as it is transcribed, to keep the
// conversation flowing. Corrections are shown on screen, never spoken.

export const E = {
  READY: "READY", // start screen (a user gesture is needed to unlock audio)
  PREPARING_SPEECH: "PREPARING_SPEECH", // generating Aria's audio
  SPEAKING: "SPEAKING", // Aria is speaking; microphone is OFF
  LISTENING: "LISTENING", // student's turn (recording, or typing)
  TRANSCRIBING: "TRANSCRIBING",
  THINKING: "THINKING", // reply sent; Aria is preparing her answer
  PAUSED: "PAUSED",
  ENDING: "ENDING", // scoring the session
  ENDED: "ENDED",
};

const T = {
  START: { from: [E.READY], to: E.PREPARING_SPEECH },
  AUDIO_READY: { from: [E.PREPARING_SPEECH], to: E.SPEAKING },
  SPEECH_DONE: { from: [E.SPEAKING], to: E.LISTENING },
  SPEECH_FAILED: { from: [E.PREPARING_SPEECH, E.SPEAKING], to: E.LISTENING }, // the reply stays on screen
  REPLAY: { from: [E.LISTENING], to: E.PREPARING_SPEECH },
  RECORD_START: { from: [E.LISTENING], to: E.LISTENING },
  RECORD_FAILED: { from: [E.LISTENING], to: E.LISTENING },
  RECORD_STOP: { from: [E.LISTENING], to: E.TRANSCRIBING },
  NO_SPEECH: { from: [E.TRANSCRIBING], to: E.LISTENING },
  TRANSCRIBE_FAILED: { from: [E.TRANSCRIBING], to: E.LISTENING },
  SEND: { from: [E.LISTENING, E.TRANSCRIBING], to: E.THINKING },
  REPLY: { from: [E.THINKING], to: E.PREPARING_SPEECH },
  SEND_FAILED: { from: [E.THINKING], to: E.LISTENING },
  PAUSE: { from: [E.PREPARING_SPEECH, E.SPEAKING, E.LISTENING], to: E.PAUSED },
  RESUME: { from: [E.PAUSED], to: null },
  END: { from: [E.READY, E.PREPARING_SPEECH, E.SPEAKING, E.LISTENING, E.PAUSED], to: E.ENDING },
  END_FAILED: { from: [E.ENDING], to: E.LISTENING },
  ENDED: { from: [E.ENDING], to: E.ENDED },
};

export const initialEnglishState = { status: E.READY, recording: false, resumeTo: null, error: null, notice: null };

export function englishTransition(state, event) {
  const type = typeof event === "string" ? event : event.type;
  const t = T[type];
  if (!t || !t.from.includes(state.status)) return state;
  const p = typeof event === "string" ? {} : event;
  const base = { ...state, error: null, notice: p.notice ?? null, recording: false };
  switch (type) {
    case "RECORD_START":
      return { ...base, recording: true };
    case "PAUSE":
      // Aria repeats what she was saying on resume; a student turn resumes as a (fresh) student turn.
      return { ...base, status: E.PAUSED, resumeTo: state.status === E.LISTENING ? E.LISTENING : E.PREPARING_SPEECH };
    case "RESUME":
      return { ...base, status: state.resumeTo || E.LISTENING, resumeTo: null };
    case "RECORD_FAILED":
    case "TRANSCRIBE_FAILED":
    case "SPEECH_FAILED":
    case "SEND_FAILED":
    case "END_FAILED":
      return { ...base, status: t.to, error: p.error || "Something went wrong." };
    default:
      return { ...base, status: t.to };
  }
}

/** Avatar expression: while speaking, Aria uses the expression chosen for that reply ("speaking" | "encouraging"). */
export function englishAvatarMode(status, replyMode = "speaking") {
  if (status === E.SPEAKING) return replyMode === "encouraging" ? "encouraging" : "speaking";
  if (status === E.LISTENING) return "listening";
  if ([E.PREPARING_SPEECH, E.TRANSCRIBING, E.THINKING, E.ENDING].includes(status)) return "thinking";
  return "idle";
}

export const ENGLISH_STATUS_LABEL = {
  READY: "Ready", PREPARING_SPEECH: "Aria is getting ready…", SPEAKING: "Aria is speaking", LISTENING: "Your turn",
  TRANSCRIBING: "Catching your words…", THINKING: "Aria is thinking…", PAUSED: "Paused", ENDING: "Preparing your report…",
  ENDED: "Session complete",
};

/** Confidence meter label (score 0-100 from the server, null before the first reply). */
export function confidenceLabel(score) {
  if (score == null) return "Say hello to get started";
  if (score < 40) return "Warming up - every sentence counts";
  if (score < 65) return "Getting comfortable";
  if (score < 85) return "Speaking with confidence";
  return "On fire!";
}

// Shown when the student is quiet for a while, alongside Aria's own suggestions for the current question.
export const GENERIC_STARTERS = {
  free_talk: ["Let me think… I would say that…", "That's a good question. In my case…", "One thing I really like is…",
    "Can you ask that in another way?"],
  interview: ["Thank you for the question. I would say…", "One example from my project is…",
    "My main strength is… because…", "Could you please repeat the question?"],
};
