// Avatar animation states and per-interviewer expression profiles. Pure (no React / three.js), so it is tested.
//
// Exactly ONE avatar state is active at a time, derived from the conversation state, so animations can never
// conflict. Expressions blend smoothly between states in the renderer (exponential smoothing, ~0.3-0.6 s), which
// is what makes every change a gradual TRANSITION rather than a jump.
// The mouth is NOT part of the state: it follows the audio that is actually playing (SpeechPlayer.getVisemes),
// so it moves only while sound plays and closes when sound stops, whatever the state says.

export const A = {
  IDLE: "idle", // breathing, blinking, relaxed
  GREETING: "greeting", // first words of the interview: personality-specific welcome expression
  SPEAKING: "speaking", // asking a question
  PROBING: "probing", // asking a follow-up that challenges the previous answer (raised brow)
  LISTENING: "listening", // attention on the candidate, occasional nods
  THINKING: "thinking", // preparing the next question: gaze up/aside, slight frown
  REACTION: "reaction", // right after the candidate finishes: personality-specific acknowledgement
  FEEDBACK: "feedback", // closing remarks / spoken assessment
  TRANSITION: "transition", // returning to rest (paused, between phases)
};

/** Conversation state (voice/interviewMachine S) + flags -> exactly one avatar state. */
export function avatarStateFor(status, f = {}) {
  switch (status) {
    case "SPEAKING":
      if (f.feedback) return A.FEEDBACK;
      if (f.greeting) return A.GREETING;
      return f.probing ? A.PROBING : A.SPEAKING;
    case "LISTENING":
    case "REVIEWING":
      return A.LISTENING;
    case "TRANSCRIBING":
      return A.REACTION;
    case "EVALUATING":
      return f.reacting ? A.REACTION : A.THINKING;
    case "PREPARING_SPEECH":
    case "COMPLETING":
      return A.THINKING;
    case "WRAP_UP":
      return f.feedback ? A.FEEDBACK : A.TRANSITION;
    case "PAUSED":
      return A.TRANSITION;
    default:
      return A.IDLE;
  }
}

// Base expression for every state (blendshape weights 0-1, head tilt in radians).
//   smile, browUp, browDown, squint, skeptic (one brow raised), lookUp, lookSide, tilt, nodRate (nods while in state)
const BASE = {
  idle: { smile: 0.18, browUp: 0, browDown: 0, squint: 0.05, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0, nodRate: 0 },
  greeting: { smile: 0.5, browUp: 0.25, browDown: 0, squint: 0.2, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0.04, nodRate: 0 },
  speaking: { smile: 0.12, browUp: 0.12, browDown: 0, squint: 0.05, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0, nodRate: 0 },
  probing: { smile: 0.05, browUp: 0.1, browDown: 0.1, squint: 0.15, skeptic: 0.5, lookUp: 0, lookSide: 0, tilt: -0.03, nodRate: 0, lean: 0.035 },
  listening: { smile: 0.32, browUp: 0.18, browDown: 0, squint: 0.15, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0.05, nodRate: 1 },
  thinking: { smile: 0.05, browUp: 0.1, browDown: 0.25, squint: 0.2, skeptic: 0, lookUp: 0.45, lookSide: 0.35, tilt: -0.05, nodRate: 0 },
  reaction: { smile: 0.4, browUp: 0.2, browDown: 0, squint: 0.2, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0.04, nodRate: 0, nodOnEnter: true },
  feedback: { smile: 0.25, browUp: 0.15, browDown: 0, squint: 0.1, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0.02, nodRate: 0 },
  transition: { smile: 0.15, browUp: 0, browDown: 0, squint: 0.05, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0, nodRate: 0 },
  encouraging: { smile: 0.45, browUp: 0.22, browDown: 0, squint: 0.2, skeptic: 0, lookUp: 0, lookSide: 0, tilt: 0.04, nodRate: 0 },
};

// Per-interviewer overrides on top of BASE, plus motion style.
//   motion: scale of head sway/talk movement; nodSize: nod depth; blinkEvery: [min, max] seconds
//   warmth: share of listening micro-expressions that are smiles (vs. interested brow lifts)
//   expressiveness: size of micro-expressions; press (in states): lips pressed together (controlled, serious)
//   lean (in states): forward head inclination in radians, e.g. when pressing a question
export const PROFILES = {
  aria: { motion: 1, nodSize: 1, blinkEvery: [2, 6], warmth: 0.7, expressiveness: 1, states: {} }, // original Aria
  victor: {
    motion: 0.55, nodSize: 0.5, blinkEvery: [3, 7], warmth: 0.1, expressiveness: 0.55,
    states: {
      idle: { smile: 0.02, browDown: 0.12, press: 0.15 },
      greeting: { smile: 0.12, browUp: 0.08 },
      speaking: { smile: 0.0, browUp: 0.05, browDown: 0.1 },
      probing: { smile: 0, skeptic: 0.75, browDown: 0.15, squint: 0.25 },
      listening: { smile: 0.03, browUp: 0.05, squint: 0.22, nodRate: 0.35, press: 0.2 },
      thinking: { smile: 0, browDown: 0.35, lookUp: 0.25, lookSide: 0.2 },
      reaction: { smile: 0.02, browUp: 0, skeptic: 0.45, squint: 0.25 }, // measured scepticism, no smile
      feedback: { smile: 0.05, browDown: 0.1 },
      transition: { smile: 0.02, browDown: 0.1 },
    },
  },
  marcus: {
    motion: 0.8, nodSize: 0.6, blinkEvery: [2.5, 5], warmth: 0.05, expressiveness: 0.6,
    states: {
      idle: { smile: 0.0, squint: 0.2, browDown: 0.15, press: 0.12 },
      greeting: { smile: 0.08, squint: 0.2 },
      speaking: { smile: 0, squint: 0.2, browDown: 0.15 },
      probing: { smile: 0, skeptic: 0.6, browDown: 0.25, squint: 0.3 },
      listening: { smile: 0, browUp: 0.08, squint: 0.3, browDown: 0.1, nodRate: 0.5 },
      thinking: { smile: 0, browDown: 0.3, lookUp: 0.2, lookSide: 0.15 },
      reaction: { smile: 0, skeptic: 0.35, squint: 0.3 },
      feedback: { smile: 0.06, squint: 0.15 },
      transition: { smile: 0, squint: 0.15 },
    },
  },
  elena: {
    motion: 0.8, nodSize: 0.8, blinkEvery: [2, 5.5], warmth: 0.5, expressiveness: 0.8,
    states: {
      idle: { smile: 0.2 },
      greeting: { smile: 0.42, browUp: 0.2 },
      speaking: { smile: 0.15, browUp: 0.1 },
      probing: { smile: 0.12, skeptic: 0.2, browUp: 0.2 }, // curious, not sceptical
      listening: { smile: 0.28, browUp: 0.15, nodRate: 1.1 },
      reaction: { smile: 0.32, browUp: 0.15 },
      feedback: { smile: 0.25 },
    },
  },
};

/** Expression target for (interviewer, avatar state). Unknown ids fall back to Aria / idle. */
export function expressionFor(interviewer, state) {
  const p = PROFILES[interviewer] || PROFILES.aria;
  const base = BASE[state] || BASE.idle;
  return { ...base, ...(p.states[state] || {}) };
}

export function profileFor(interviewer) {
  return PROFILES[interviewer] || PROFILES.aria;
}

// Rendering quality of the 3D interviewer (presets live in Avatar3D.jsx). Stored per browser.
export const AVATAR_QUALITY = {
  high: "High quality",
  balanced: "Balanced",
  performance: "Performance",
};
export const QUALITY_KEY = "hs-avatar-quality";

export function storedQuality() {
  try {
    const q = window.localStorage.getItem(QUALITY_KEY);
    return q in AVATAR_QUALITY ? q : "balanced";
  } catch {
    return "balanced";
  }
}

export function saveQuality(q) {
  try { window.localStorage.setItem(QUALITY_KEY, q); } catch { /* private mode */ }
}

export const AVATAR_STATE_LABEL = {
  idle: "Idle", greeting: "Greeting", speaking: "Speaking", probing: "Asking a follow-up", listening: "Listening",
  thinking: "Thinking", reaction: "Reacting", feedback: "Giving feedback", transition: "Resting",
};
