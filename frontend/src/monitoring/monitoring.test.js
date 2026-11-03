import { describe, expect, it } from "vitest";
import { analyzeFaces, brightness, gazeFromBlendshapes, headAngles, observe, setupGuidance } from "./frameAnalysis";
import { FocusTracker, SignalTracker } from "./signalTracker";

const ALL = { face_absent: true, multiple_faces: true, attention_away: true, low_light: true, camera_obstructed: true };
const run = (tracker, frames) => frames.reduce((acc, [t, obs]) => {
  const o = tracker.update(t, obs);
  return { events: [...acc.events, ...o.events], warnings: [...acc.warnings, ...o.warnings], cleared: [...acc.cleared, ...o.cleared] };
}, { events: [], warnings: [], cleared: [] });
const series = (fromMs, toMs, obs, step = 250) => {
  const out = [];
  for (let t = fromMs; t <= toMs; t += step) out.push([t, typeof obs === "function" ? obs(t) : obs]);
  return out;
};

describe("SignalTracker (false-positive handling)", () => {
  it("ignores a brief face dropout (no warning, no event)", () => {
    const tr = new SignalTracker(ALL);
    const r = run(tr, [...series(0, 2000, { face_absent: true }), ...series(2250, 6000, { face_absent: false })]);
    expect(r.warnings).toEqual([]);
    expect(r.events).toEqual([]);
  });

  it("warns only after the grace period and records duration + confidence", () => {
    const tr = new SignalTracker(ALL);
    const r = run(tr, [...series(0, 12000, { face_absent: true }), ...series(12250, 15000, { face_absent: false })]);
    expect(r.warnings.map((w) => w.type)).toEqual(["face_absent"]);
    expect(r.warnings[0].message).toMatch(/cannot clearly detect your face/);
    expect(r.cleared).toEqual(["face_absent"]);
    expect(r.events).toHaveLength(1);
    expect(r.events[0]).toMatchObject({ event_type: "face_absent", t_ms: 0, duration_ms: 12000 });
    expect(r.events[0].confidence).toBeGreaterThan(0.85);
  });

  it("short detector flickers inside an episode do not split it (hysteresis)", () => {
    const tr = new SignalTracker(ALL);
    const flicker = (t) => ({ multiple_faces: Math.floor(t / 250) % 5 !== 0 }); // 1 frame in 5 misses the 2nd face
    const r = run(tr, [...series(0, 8000, flicker), ...series(8250, 12000, { multiple_faces: false })]);
    expect(r.events).toHaveLength(1);
    expect(r.events[0].event_type).toBe("multiple_faces");
    expect(r.events[0].confidence).toBeLessThan(0.9);
  });

  it("null observations (cannot judge) neither extend nor end an episode", () => {
    const tr = new SignalTracker(ALL);
    const r = run(tr, series(0, 30000, { attention_away: null }));
    expect(r).toEqual({ events: [], warnings: [], cleared: [] });
  });

  it("only consented signals are tracked", () => {
    const tr = new SignalTracker({ face_absent: true });
    const r = run(tr, series(0, 20000, { attention_away: true, multiple_faces: true }));
    expect(r.events).toEqual([]);
    expect(r.warnings).toEqual([]);
  });

  it("flush closes open episodes at the end of the interview", () => {
    const tr = new SignalTracker(ALL);
    run(tr, series(0, 9000, { attention_away: true }));
    expect(tr.flush().events[0]).toMatchObject({ event_type: "attention_away", duration_ms: 9000 });
  });
});

describe("FocusTracker", () => {
  it("records time away and skips sub-second blurs", () => {
    const f = new FocusTracker();
    f.away(1000);
    expect(f.back(1300)).toBeNull();
    f.away(5000);
    expect(f.back(9000)).toEqual({ event_type: "focus_change", t_ms: 5000, duration_ms: 4000 });
  });
});

describe("frame analysis", () => {
  const face = (cx, cy, w = 0.3) => Array.from({ length: 468 }, (_, i) => ({ x: cx - w / 2 + (i % 2) * w, y: cy - w / 2 + (i % 3 ? w : 0) }));

  it("brightness of dark and bright frames", () => {
    const dark = new Uint8ClampedArray(64 * 48 * 4).fill(5);
    const bright = new Uint8ClampedArray(64 * 48 * 4).fill(180);
    expect(brightness(dark).mean).toBeLessThan(10);
    expect(brightness(bright).mean).toBeGreaterThan(170);
  });

  it("counts faces, framing and approximate head angles", () => {
    expect(analyzeFaces({ faceLandmarks: [] }).faces).toBe(0);
    const a = analyzeFaces({ faceLandmarks: [face(0.5, 0.5)] });
    expect(a.faces).toBe(1);
    expect(a.centered).toBe(true);
    expect(analyzeFaces({ faceLandmarks: [face(0.9, 0.5)] }).centered).toBe(false);
    expect(analyzeFaces({ faceLandmarks: [face(0.5, 0.5), face(0.2, 0.2)] }).faces).toBe(2);
    // identity matrix = facing the camera
    expect(headAngles([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])).toEqual({ yaw: -0, pitch: 0 });
  });

  it("gaze from eye blendshapes is approximate and symmetric", () => {
    const cats = (o) => ["eyeLookInLeft", "eyeLookOutLeft", "eyeLookInRight", "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeLookDownLeft", "eyeLookDownRight"]
      .map((categoryName) => ({ categoryName, score: o[categoryName] || 0 }));
    expect(gazeFromBlendshapes(cats({})).x).toBe(0);
    expect(gazeFromBlendshapes(cats({ eyeLookInLeft: 0.8, eyeLookOutRight: 0.8 })).x).toBeCloseTo(0.8);
  });

  it("observe: attention only judged with exactly one face; darkness is not treated as a missing face", () => {
    const ok = { mean: 120, std: 30 };
    expect(observe({ faces: 2, away: true }, ok, { attention: true }).attention_away).toBeNull();
    expect(observe({ faces: 1, away: true }, ok, { attention: false }).attention_away).toBeNull();
    expect(observe({ faces: 1, away: true }, ok, { attention: true }).attention_away).toBe(true);
    const dark = observe({ faces: 0 }, { mean: 5, std: 2 });
    expect(dark.camera_obstructed).toBe(true);
    expect(dark.face_absent).toBeNull();
  });

  it("setup guidance uses neutral, appearance-independent wording", () => {
    expect(setupGuidance({ faces: 0 }, { mean: 120, std: 30 }).text).toMatch(/center of the camera/);
    expect(setupGuidance({ faces: 1, centered: true, tooSmall: false }, { mean: 120, std: 30 }).ok).toBe(true);
  });
});
