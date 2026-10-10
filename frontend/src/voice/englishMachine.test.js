// Unit tests for the spoken-English (Aria) conversation loop.
import { describe, expect, it } from "vitest";
import { E, confidenceLabel, englishAvatarMode, englishTransition, initialEnglishState } from "./englishMachine";
import { vadStep } from "./recorder";

const run = (events, from = initialEnglishState) => events.reduce((s, e) => englishTransition(s, e), from);

describe("english conversation machine", () => {
  it("loops hands-free: speak -> listen -> transcribe -> think -> speak", () => {
    const s = run(["START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START"]);
    expect(s).toMatchObject({ status: E.LISTENING, recording: true });
    const next = run(["RECORD_STOP", "SEND", "REPLY"], s);
    expect(next).toMatchObject({ status: E.PREPARING_SPEECH, recording: false });
    expect(run(["AUDIO_READY", "SPEECH_DONE"], next).status).toBe(E.LISTENING);
  });

  it("never records while Aria is speaking and ignores double sends", () => {
    const speaking = run(["START", "AUDIO_READY"]);
    expect(englishTransition(speaking, "RECORD_START")).toBe(speaking);
    expect(englishTransition(speaking, "SEND")).toBe(speaking);
    const thinking = run(["SPEECH_DONE", "SEND"], speaking);
    expect(englishTransition(thinking, "SEND")).toBe(thinking);
  });

  it("keeps the student in their turn after failures", () => {
    const listening = run(["START", "SPEECH_FAILED"]);
    expect(listening).toMatchObject({ status: E.LISTENING, error: expect.any(String) });
    const failed = run(["SEND", { type: "SEND_FAILED", error: "offline" }], listening);
    expect(failed).toMatchObject({ status: E.LISTENING, error: "offline" });
    const noSpeech = run(["RECORD_START", "RECORD_STOP", { type: "NO_SPEECH", notice: "again" }], failed);
    expect(noSpeech).toMatchObject({ status: E.LISTENING, notice: "again", error: null });
  });

  it("pause during speech replays it; pause during the student's turn resumes listening", () => {
    expect(run(["START", "AUDIO_READY", "PAUSE", "RESUME"]).status).toBe(E.PREPARING_SPEECH);
    expect(run(["START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START", "PAUSE"]).recording).toBe(false);
    expect(run(["START", "AUDIO_READY", "SPEECH_DONE", "PAUSE", "RESUME"]).status).toBe(E.LISTENING);
  });

  it("ends cleanly (and can retry if ending fails)", () => {
    const ending = run(["START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START", "END"]);
    expect(ending).toMatchObject({ status: E.ENDING, recording: false });
    expect(run([{ type: "END_FAILED", error: "x" }, "END", "ENDED"], ending).status).toBe(E.ENDED);
    expect(englishTransition(run(["START", "AUDIO_READY", "SPEECH_DONE", "SEND"]), "END").status).toBe(E.THINKING);
  });

  it("maps states to avatar expressions, using Aria's chosen mood while she speaks", () => {
    expect(englishAvatarMode(E.SPEAKING, "encouraging")).toBe("encouraging");
    expect(englishAvatarMode(E.SPEAKING, "nonsense")).toBe("speaking");
    expect(englishAvatarMode(E.LISTENING)).toBe("listening");
    expect(englishAvatarMode(E.THINKING)).toBe("thinking");
    expect(englishAvatarMode(E.TRANSCRIBING)).toBe("thinking");
    expect(englishAvatarMode(E.ENDED)).toBe("idle");
  });

  it("labels the confidence meter", () => {
    expect(confidenceLabel(null)).toMatch(/hello/);
    expect(confidenceLabel(20)).toMatch(/Warming/);
    expect(confidenceLabel(90)).toMatch(/fire/);
  });

  it("recorder can flag hesitation after a configurable quiet time", () => {
    const st = { elapsed: 0, speechMs: 0, quietMs: 0, started: false, warned: false };
    let r = null;
    for (let i = 0; i < 49; i++) r = vadStep(st, 0, 100, { noSpeechMs: 5000 }) || r;
    expect(r).toBe(null);
    expect(vadStep(st, 0, 100, { noSpeechMs: 5000 })).toBe("no_speech");
  });
});
