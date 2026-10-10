// Unit tests: avatar state machine, personality expression profiles, stress-interview interruption, true pause,
// and interviewer voice selection.
import { describe, expect, it } from "vitest";
import { A, PROFILES, avatarStateFor, expressionFor } from "./avatarStates";
import { S, initialState, transition } from "./interviewMachine";
import { pickBrowserVoice } from "./speechPlayer";
import { browserVoiceOpts, speakBody } from "./useInterviewers";

const run = (events, from = initialState) => events.reduce((s, e) => transition(s, e), from);

describe("avatar states", () => {
  it("derives exactly one state from the conversation", () => {
    expect(avatarStateFor("READY")).toBe(A.IDLE);
    expect(avatarStateFor("SPEAKING", { greeting: true })).toBe(A.GREETING);
    expect(avatarStateFor("SPEAKING")).toBe(A.SPEAKING);
    expect(avatarStateFor("SPEAKING", { probing: true })).toBe(A.PROBING);
    expect(avatarStateFor("LISTENING")).toBe(A.LISTENING);
    expect(avatarStateFor("REVIEWING")).toBe(A.LISTENING);
    expect(avatarStateFor("TRANSCRIBING")).toBe(A.REACTION);
    expect(avatarStateFor("EVALUATING", { reacting: true })).toBe(A.REACTION);
    expect(avatarStateFor("EVALUATING")).toBe(A.THINKING);
    expect(avatarStateFor("PREPARING_SPEECH")).toBe(A.THINKING);
    expect(avatarStateFor("WRAP_UP", { feedback: true })).toBe(A.FEEDBACK);
    expect(avatarStateFor("WRAP_UP")).toBe(A.TRANSITION);
    expect(avatarStateFor("PAUSED")).toBe(A.TRANSITION);
    // feedback wins over greeting if both were set
    expect(avatarStateFor("SPEAKING", { greeting: true, feedback: true })).toBe(A.FEEDBACK);
  });

  it("covers every required state for every interviewer", () => {
    for (const who of ["aria", "victor", "marcus", "elena"]) {
      for (const state of Object.values(A)) {
        const ex = expressionFor(who, state);
        for (const k of ["smile", "browUp", "browDown", "squint", "skeptic", "lookUp", "lookSide", "tilt", "nodRate"]) {
          expect(typeof ex[k], `${who}/${state}/${k}`).toBe("number");
          expect(Math.abs(ex[k])).toBeLessThanOrEqual(1.2);
        }
      }
    }
  });

  it("gives each personality a visibly different face", () => {
    // Aria smiles while listening; Victor and Marcus stay serious
    expect(expressionFor("aria", A.LISTENING).smile).toBeGreaterThan(0.25);
    expect(expressionFor("victor", A.LISTENING).smile).toBeLessThan(0.1);
    expect(expressionFor("marcus", A.LISTENING).smile).toBeLessThan(0.1);
    // Victor reacts with scepticism, Aria and Elena warmly
    expect(expressionFor("victor", A.REACTION).skeptic).toBeGreaterThan(0.3);
    expect(expressionFor("aria", A.REACTION).skeptic).toBe(0);
    expect(expressionFor("elena", A.REACTION).smile).toBeGreaterThan(0.25);
    // raised brow when asking for clarification
    expect(expressionFor("victor", A.PROBING).skeptic).toBeGreaterThan(expressionFor("elena", A.PROBING).skeptic);
    // controlled head movement for the strict interviewer
    expect(PROFILES.victor.motion).toBeLessThan(PROFILES.aria.motion);
    // unknown ids fall back to Aria, unknown states to idle
    expect(expressionFor("nobody", "nonsense")).toEqual(expressionFor("aria", A.IDLE));
  });

  it("keeps Aria's original expressions", () => {
    expect(expressionFor("aria", A.LISTENING)).toMatchObject({ smile: 0.32, browUp: 0.18, nodRate: 1 });
    expect(expressionFor("aria", A.THINKING)).toMatchObject({ lookUp: 0.45, lookSide: 0.35 });
  });
});

describe("interview machine extensions", () => {
  it("stress interview: INTERRUPT stops the answer and marks it until submitted", () => {
    const rec = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START"]);
    const s = transition(rec, "INTERRUPT");
    expect(s).toMatchObject({ status: S.TRANSCRIBING, recording: false, interrupted: true });
    const reviewing = transition(s, "TRANSCRIPT");
    expect(reviewing.interrupted).toBe(true);
    const evaluating = transition(reviewing, "SUBMIT");
    expect(evaluating.interrupted).toBe(true); // read when the answer is sent
    expect(transition(evaluating, "NEXT_QUESTION").interrupted).toBe(false);
    expect(transition(reviewing, "RERECORD").interrupted).toBe(false);
    // only possible while recording/listening
    const speaking = run(["LOADED", "START", "AUDIO_READY"]);
    expect(transition(speaking, "INTERRUPT")).toBe(speaking);
  });

  it("pausing speech that the player paused resumes the same speech", () => {
    const speaking = run(["LOADED", "START", "AUDIO_READY"]);
    const paused = transition(speaking, { type: "PAUSE", speechPaused: true });
    expect(transition(paused, "RESUME").status).toBe(S.SPEAKING);
    // without a pausable player the question is replayed (original behaviour)
    expect(transition(transition(speaking, "PAUSE"), "RESUME").status).toBe(S.PREPARING_SPEECH);
  });
});

describe("interviewer voices", () => {
  const voices = [
    { name: "Microsoft David - English (United States)", lang: "en-US" },
    { name: "Microsoft Zira - English (United States)", lang: "en-US" },
    { name: "Microsoft Hazel - English (United Kingdom)", lang: "en-GB" },
    { name: "Microsoft George - English (United Kingdom)", lang: "en-GB" },
    { name: "Microsoft Heera - English (India)", lang: "en-IN" },
  ];
  it("picks a browser voice by language and gender", () => {
    expect(pickBrowserVoice(voices, "en-GB", "male").name).toMatch(/George/);
    expect(pickBrowserVoice(voices, "en-GB", "female").name).toMatch(/Hazel/);
    expect(pickBrowserVoice(voices, "en-US", "male").name).toMatch(/David/);
    expect(pickBrowserVoice(voices, "en-AU", "female").name).toMatch(/Zira|Hazel/); // falls back to any English
    expect(pickBrowserVoice([], "en-US", "male")).toBe(null);
  });

  it("applies the interviewer's voice and speed, clamped for the TTS service", () => {
    const marcus = { tts_voice: "am_michael", tts_speed: 1.12, browser_voice: { gender: "male", lang: "en-US", pitch: 0.95 } };
    expect(speakBody(marcus, "Next.", 1)).toEqual({ text: "Next.", voice: "am_michael", speed: 1.12 });
    expect(speakBody(marcus, "Next.", 1.3).speed).toBe(1.4); // server limit
    expect(speakBody(marcus, "x".repeat(2000)).text.length).toBe(1500);
    expect(browserVoiceOpts(marcus)).toMatchObject({ lang: "en-US", gender: "male", pitch: 0.95, rate: 1.12 });
  });
});
