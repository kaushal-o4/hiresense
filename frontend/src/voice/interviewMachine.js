// Voice-interview state machine. Pure: transition(state, event) -> new state. Disallowed events are ignored,
// which is what prevents double submissions, recording while the avatar speaks, and similar races.

export const S = {
  INITIALIZING: "INITIALIZING", // loading the interview session
  READY: "READY", // consent screen: candidate has not started yet
  PREPARING_SPEECH: "PREPARING_SPEECH", // generating the question's audio
  SPEAKING: "SPEAKING", // avatar is speaking; microphone is OFF
  LISTENING: "LISTENING", // waiting for / recording the candidate's answer
  TRANSCRIBING: "TRANSCRIBING", // converting the recording to text
  REVIEWING: "REVIEWING", // candidate checks / edits the transcript before submitting
  EVALUATING: "EVALUATING", // backend scores the answer and generates the next question (avatar "thinking")
  WRAP_UP: "WRAP_UP", // all questions answered; waiting for the candidate to finish
  COMPLETING: "COMPLETING", // generating the final report
  COMPLETED: "COMPLETED",
  PAUSED: "PAUSED",
  ERROR: "ERROR",
};

// event -> { from: [...states], to }
const T = {
  LOADED: { from: [S.INITIALIZING], to: S.READY },
  LOAD_FAILED: { from: [S.INITIALIZING], to: S.ERROR },
  START: { from: [S.READY], to: S.PREPARING_SPEECH },
  AUDIO_READY: { from: [S.PREPARING_SPEECH], to: S.SPEAKING },
  SPEECH_FAILED: { from: [S.PREPARING_SPEECH, S.SPEAKING], to: S.LISTENING }, // question stays on screen as text
  SPEECH_DONE: { from: [S.SPEAKING], to: S.LISTENING },
  REPLAY: { from: [S.LISTENING, S.REVIEWING], to: S.PREPARING_SPEECH },
  RECORD_START: { from: [S.LISTENING], to: S.LISTENING },
  RECORD_STOP: { from: [S.LISTENING], to: S.TRANSCRIBING },
  RECORD_FAILED: { from: [S.LISTENING], to: S.LISTENING },
  TRANSCRIPT: { from: [S.TRANSCRIBING], to: S.REVIEWING },
  NO_SPEECH: { from: [S.TRANSCRIBING], to: S.LISTENING },
  TRANSCRIBE_FAILED: { from: [S.TRANSCRIBING], to: S.REVIEWING }, // empty box: candidate can type instead
  TYPE_INSTEAD: { from: [S.LISTENING], to: S.REVIEWING },
  RERECORD: { from: [S.REVIEWING], to: S.LISTENING },
  SUBMIT: { from: [S.REVIEWING], to: S.EVALUATING },
  SUBMIT_FAILED: { from: [S.EVALUATING], to: S.REVIEWING }, // keeps the transcript; session is not lost
  NEXT_QUESTION: { from: [S.EVALUATING], to: S.PREPARING_SPEECH },
  ALL_ANSWERED: { from: [S.EVALUATING], to: S.WRAP_UP },
  FINISH: { from: [S.WRAP_UP, S.LISTENING, S.REVIEWING, S.READY, S.PAUSED], to: S.COMPLETING },
  COMPLETE_FAILED: { from: [S.COMPLETING], to: S.WRAP_UP },
  COMPLETED: { from: [S.COMPLETING], to: S.COMPLETED },
  PAUSE: { from: [S.PREPARING_SPEECH, S.SPEAKING, S.LISTENING, S.REVIEWING], to: S.PAUSED },
  RESUME: { from: [S.PAUSED], to: null }, // computed below
  INTERRUPT: { from: [S.LISTENING], to: S.TRANSCRIBING }, // time limit reached (stress interview): stop and move on
  FATAL: { from: Object.values(S).filter((s) => s !== S.COMPLETED), to: S.ERROR },
  RETRY: { from: [S.ERROR], to: S.INITIALIZING },
};

export const initialState = { status: S.INITIALIZING, resumeTo: null, recording: false, error: null, notice: null,
  interrupted: false };

export function canTransition(state, type) {
  const t = T[type];
  return !!t && t.from.includes(state.status);
}

export function transition(state, event) {
  const type = typeof event === "string" ? event : event.type;
  if (!canTransition(state, type)) return state; // ignored
  const payload = typeof event === "string" ? {} : event;
  const base = { ...state, error: null, notice: payload.notice ?? null };
  switch (type) {
    case "RECORD_START":
      return { ...base, recording: true, interrupted: false };
    case "RECORD_FAILED":
      return { ...base, recording: false, error: payload.error || "The microphone could not be used." };
    case "RECORD_STOP":
      return { ...base, status: S.TRANSCRIBING, recording: false };
    case "INTERRUPT":
      return { ...base, status: S.TRANSCRIBING, recording: false, interrupted: true };
    case "SUBMIT":
    case "TYPE_INSTEAD":
    case "RERECORD":
      return { ...base, status: T[type].to, recording: false, interrupted: type === "SUBMIT" ? state.interrupted : false };
    case "NEXT_QUESTION":
    case "ALL_ANSWERED":
      return { ...base, status: T[type].to, recording: false, interrupted: false };
    case "PAUSE":
      // Speech that the player could pause (payload.speechPaused) continues where it stopped; otherwise a question
      // that was being spoken is replayed on resume. An answer in progress is kept.
      if (state.status === S.SPEAKING && payload.speechPaused) return { ...base, status: S.PAUSED, recording: false, resumeTo: S.SPEAKING };
      return { ...base, status: S.PAUSED, recording: false,
        resumeTo: [S.PREPARING_SPEECH, S.SPEAKING].includes(state.status) ? S.PREPARING_SPEECH : state.status };
    case "RESUME":
      return { ...base, status: state.resumeTo || S.LISTENING, resumeTo: null };
    case "LOAD_FAILED":
    case "FATAL":
    case "SUBMIT_FAILED":
    case "COMPLETE_FAILED":
    case "TRANSCRIBE_FAILED":
    case "SPEECH_FAILED":
      return { ...base, status: T[type].to, recording: false, error: payload.error || "Something went wrong." };
    default:
      return { ...base, status: T[type].to, recording: false };
  }
}

/** What the avatar should look like in each state. */
export function avatarMode(status) {
  if (status === S.SPEAKING) return "speaking";
  if (status === S.LISTENING || status === S.REVIEWING) return "listening";
  if ([S.PREPARING_SPEECH, S.TRANSCRIBING, S.EVALUATING, S.COMPLETING].includes(status)) return "thinking";
  return "idle";
}

export const STATUS_LABEL = {
  INITIALIZING: "Connecting…", READY: "Ready", PREPARING_SPEECH: "Preparing question…", SPEAKING: "Interviewer speaking",  LISTENING: "Your turn", TRANSCRIBING: "Transcribing your answer…", REVIEWING: "Review your answer",
  EVALUATING: "Evaluating your answer…", WRAP_UP: "All questions answered", COMPLETING: "Preparing your report…",
  COMPLETED: "Interview complete", PAUSED: "Paused", ERROR: "Problem",
};
