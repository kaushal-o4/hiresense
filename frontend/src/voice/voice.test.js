// Unit tests for the voice interview's pure logic: state machine, lip-sync maths, audio encoding, silence detection.
import { describe, expect, it } from "vitest";
import { S, avatarMode, canTransition, initialState, transition } from "./interviewMachine";
import { SHAPES, amplitudeFactor, approximateVisemes, mouthAt, mouthGeometry, segmentAt, visemeWeightsAt } from "./visemes";
import { downsample, encodeWav, rms, vadStep } from "./recorder";

const run = (events, from = initialState) => events.reduce((s, e) => transition(s, e), from);

describe("interview state machine", () => {
  it("follows the full happy path", () => {
    const s = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START", "RECORD_STOP", "TRANSCRIPT", "SUBMIT", "NEXT_QUESTION"]);
    expect(s.status).toBe(S.PREPARING_SPEECH);
    const end = run(["AUDIO_READY", "SPEECH_DONE", "TYPE_INSTEAD", "SUBMIT", "ALL_ANSWERED", "FINISH", "COMPLETED"], s);
    expect(end.status).toBe(S.COMPLETED);
  });

  it("cannot record while the interviewer is speaking", () => {
    const speaking = run(["LOADED", "START", "AUDIO_READY"]);
    expect(speaking.status).toBe(S.SPEAKING);
    expect(canTransition(speaking, "RECORD_START")).toBe(false);
    expect(transition(speaking, "RECORD_START")).toBe(speaking); // ignored, same object
    expect(transition(speaking, "TYPE_INSTEAD")).toBe(speaking);
  });

  it("ignores a second submit (no duplicate answers)", () => {
    const evaluating = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "TYPE_INSTEAD", "SUBMIT"]);
    expect(evaluating.status).toBe(S.EVALUATING);
    expect(transition(evaluating, "SUBMIT")).toBe(evaluating);
  });

  it("processes each recording once", () => {
    const transcribing = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START", "RECORD_STOP"]);
    expect(transcribing.status).toBe(S.TRANSCRIBING);
    expect(transition(transcribing, "RECORD_STOP")).toBe(transcribing);
    expect(transcribing.recording).toBe(false);
  });

  it("keeps the answer when submission fails", () => {
    const s = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "TYPE_INSTEAD", "SUBMIT", { type: "SUBMIT_FAILED", error: "offline" }]);
    expect(s.status).toBe(S.REVIEWING);
    expect(s.error).toBe("offline");
  });

  it("pause during speech replays the question; pause while answering resumes answering", () => {
    const p1 = run(["LOADED", "START", "AUDIO_READY", "PAUSE"]);
    expect(p1.status).toBe(S.PAUSED);
    expect(transition(p1, "RESUME").status).toBe(S.PREPARING_SPEECH);
    const p2 = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START", "PAUSE"]);
    expect(p2.recording).toBe(false);
    expect(transition(p2, "RESUME").status).toBe(S.LISTENING);
    expect(transition(p1, "SUBMIT")).toBe(p1); // nothing happens while paused
  });

  it("cannot finish accidentally while speaking or evaluating", () => {
    const speaking = run(["LOADED", "START", "AUDIO_READY"]);
    expect(transition(speaking, "FINISH")).toBe(speaking);
    const evaluating = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "TYPE_INSTEAD", "SUBMIT"]);
    expect(transition(evaluating, "FINISH")).toBe(evaluating);
    expect(transition(evaluating, "NEXT_QUESTION").status).toBe(S.PREPARING_SPEECH);
  });

  it("speech and transcription failures fall back without losing the interview", () => {
    expect(run(["LOADED", "START", { type: "SPEECH_FAILED", error: "no audio" }]).status).toBe(S.LISTENING);
    const t = run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START", "RECORD_STOP", "TRANSCRIBE_FAILED"]);
    expect(t.status).toBe(S.REVIEWING); // candidate types the answer
    expect(run(["LOADED", "START", "AUDIO_READY", "SPEECH_DONE", "RECORD_START", "RECORD_STOP", "NO_SPEECH"]).status).toBe(S.LISTENING);
  });

  it("maps states to avatar expressions", () => {
    expect(avatarMode(S.SPEAKING)).toBe("speaking");
    expect(avatarMode(S.LISTENING)).toBe("listening");
    expect(avatarMode(S.EVALUATING)).toBe("thinking");
    expect(avatarMode(S.PAUSED)).toBe("idle");
  });
});

describe("lip sync", () => {
  const tl = [{ t: 0.1, d: 0.1, v: "PP" }, { t: 0.2, d: 0.2, v: "AA" }, { t: 0.4, d: 0.1, v: "O" }];

  it("finds the active segment", () => {
    expect(segmentAt(tl, 0.05)).toBe(-1);
    expect(segmentAt(tl, 0.15)).toBe(0);
    expect(segmentAt(tl, 0.25)).toBe(1);
    expect(segmentAt(tl, 0.45)).toBe(2);
    expect(segmentAt(tl, 0.6)).toBe(-1);
  });

  it("closes the mouth outside speech and on bilabials", () => {
    expect(mouthAt(tl, 0.0).open).toBe(0);
    expect(mouthAt(tl, 0.7).open).toBe(0); // after speech ends
    expect(mouthAt(tl, 0.12).press).toBe(1); // P/B/M: lips pressed
    expect(mouthAt(tl, 0.25).open).toBeGreaterThan(0.7); // "aa": open
  });

  it("blends into the next shape near the end of a segment (coarticulation)", () => {
    const mid = mouthAt(tl, 0.29).open;
    const late = mouthAt(tl, 0.39).open;
    expect(late).toBeLessThan(mid);
    expect(late).toBeGreaterThan(SHAPES.O.open);
  });

  it("scales opening with audio level", () => {
    expect(amplitudeFactor(0)).toBeCloseTo(0.25);
    expect(amplitudeFactor(0.2)).toBeCloseTo(1);
    expect(amplitudeFactor(0.02)).toBeGreaterThan(amplitudeFactor(0.01));
  });

  it("produces valid mouth geometry for every shape", () => {
    for (const [name, shape] of Object.entries(SHAPES)) {
      const g = mouthGeometry(shape);
      expect(g.upper, name).not.toMatch(/NaN/);
      expect(g.lower, name).not.toMatch(/NaN/);
      expect(g.gap).toBeGreaterThanOrEqual(0);
    }
    expect(mouthGeometry(SHAPES.AA).gap).toBeGreaterThan(mouthGeometry(SHAPES.U).gap);
    expect(mouthGeometry(SHAPES.PP).gap).toBe(0);
  });

  it("gives blendshape weights for the 3D face, blending into the next viseme", () => {
    expect(visemeWeightsAt(tl, 0.0)).toEqual({ sil: 1 });
    expect(visemeWeightsAt(tl, 0.25)).toEqual({ AA: 1 });
    const late = visemeWeightsAt(tl, 0.39);
    expect(late.AA).toBeGreaterThan(late.O);
    expect(late.AA + late.O).toBeCloseTo(1);
  });

  it("approximate visemes for the browser-voice fallback", () => {
    const v = approximateVisemes("map", 1.0);
    expect(v.map((s) => s.v)).toEqual(["PP", "AA", "PP"]);
    expect(v[0].t).toBe(1.0);
  });
});

describe("audio capture helpers", () => {
  it("encodes a valid 16 kHz mono PCM WAV", () => {
    const wav = encodeWav(new Float32Array([0, 0.5, -0.5, 1]), 16000);
    const v = new DataView(wav.buffer);
    expect(String.fromCharCode(...wav.slice(0, 4))).toBe("RIFF");
    expect(String.fromCharCode(...wav.slice(8, 12))).toBe("WAVE");
    expect(v.getUint32(24, true)).toBe(16000);
    expect(v.getUint16(22, true)).toBe(1);
    expect(v.getUint32(40, true)).toBe(8);
    expect(v.getInt16(46, true)).toBe(16383); // 0.5 * 32767, truncated
    expect(v.getInt16(48, true)).toBe(-16384); // -0.5 * 32768
    expect(v.getInt16(50, true)).toBe(0x7fff);
  });

  it("downsamples 48 kHz to 16 kHz", () => {
    const out = downsample(new Float32Array(48000).fill(0.25), 48000, 16000);
    expect(out.length).toBe(16000);
    expect(out[100]).toBeCloseTo(0.25);
  });

  it("detects end of speech after a pause, and warns when nothing is heard", () => {
    const st = { elapsed: 0, speechMs: 0, quietMs: 0, started: false, warned: false };
    let r;
    for (let i = 0; i < 20; i++) r = vadStep(st, 0.1, 50); // 1 s of speech
    expect(r).toBe("speech");
    for (let i = 0; i < 69; i++) r = vadStep(st, 0.0, 50, { silenceMs: 3500 });
    expect(r).toBe(null); // 3.45 s of silence: thinking pause, keep recording
    expect(vadStep(st, 0.0, 50, { silenceMs: 3500 })).toBe("silence_stop");

    const quiet = { elapsed: 0, speechMs: 0, quietMs: 0, started: false, warned: false };
    const results = [];
    for (let i = 0; i < 300; i++) results.push(vadStep(quiet, 0.0, 50, { noSpeechMs: 12000 }));
    expect(results.filter((x) => x === "no_speech").length).toBe(1); // warns once, never auto-stops
    expect(results).not.toContain("silence_stop");
    expect(rms(new Float32Array([0.5, -0.5]))).toBeCloseTo(0.5);
  });
});
