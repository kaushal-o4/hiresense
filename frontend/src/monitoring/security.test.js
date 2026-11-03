// Interview security module (2026-10-23): calibration, gaze scenarios, partial face, repeated deviations, audio
// attribution, connection outages, the event reporter and the interview monitor's rate-limited reminders.
// Detector inputs are SIMULATED (synthetic MediaPipe-shaped results and audio levels); these tests prove the
// decision logic, not how well MediaPipe sees a real face - that needs the manual camera checks in the README.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api", () => ({ post: vi.fn() }));
import { post } from "../api";
import { ConnectionTracker, SpeechAttribution } from "./audioMonitor";
import { EventReporter } from "./eventReporter";
import { Calibration, analyzeFaces, observe, observeMeta, setupGuidance } from "./frameAnalysis";
import { FocusTracker, RepeatTracker, SignalTracker, thresholdsFrom } from "./signalTracker";

// --- synthetic MediaPipe results ------------------------------------------------------------------------------------
const box = (cx, cy, w = 0.3) => Array.from({ length: 468 }, (_, i) => ({ x: cx - w / 2 + (i % 2) * w, y: cy - w / 2 + (i % 3 ? w : 0) }));
const yawMatrix = (deg) => { // rotation about the vertical axis, column-major, as MediaPipe returns it
  const r = (deg * Math.PI) / 180;
  return [Math.cos(r), 0, -Math.sin(r), 0, 0, 1, 0, 0, Math.sin(r), 0, Math.cos(r), 0, 0, 0, 0, 1];
};
const blend = ({ gx = 0, jaw = 0 } = {}) => ["eyeLookInLeft", "eyeLookOutLeft", "eyeLookInRight", "eyeLookOutRight",
  "eyeLookUpLeft", "eyeLookUpRight", "eyeLookDownLeft", "eyeLookDownRight", "jawOpen"].map((categoryName) => ({
  categoryName,
  score: categoryName === "jawOpen" ? jaw : gx > 0 && ["eyeLookInLeft", "eyeLookOutRight"].includes(categoryName) ? gx
    : gx < 0 && ["eyeLookOutLeft", "eyeLookInRight"].includes(categoryName) ? -gx : 0,
}));
const result = ({ yaw = 0, gx = 0, jaw = 0, faces = 1, cx = 0.5 } = {}) => ({
  faceLandmarks: Array.from({ length: faces }, (_, i) => box(i ? 0.2 : cx, 0.5)),
  facialTransformationMatrixes: [{ data: yawMatrix(yaw) }],
  faceBlendshapes: [{ categories: blend({ gx, jaw }) }],
});
const LIGHT = { mean: 120, std: 30 };
const TH = thresholdsFrom({ gaze_record_ms: 3000, gaze_warn_ms: 8000 });

/** Feed frames at `step` ms through analysis + tracker like InterviewMonitor does; returns all outputs. */
function play(frames, { baseline = null, step = 500, tracker = new SignalTracker({ attention_away: true, face_absent: true, multiple_faces: true, low_light: true, face_partial: true }, TH) } = {}) {
  const out = { events: [], warnings: [] };
  frames.forEach((f, i) => {
    const faces = analyzeFaces(f.r, { yaw: 25, pitch: 20, gaze: 0.5 }, baseline);
    const o = tracker.update(i * step, observe(faces, f.light || LIGHT, { attention: true }), observeMeta(faces));
    out.events.push(...o.events);
    out.warnings.push(...o.warnings);
  });
  const fl = tracker.flush();
  out.events.push(...fl.events);
  return out;
}
const n = (count, r, light) => Array.from({ length: count }, () => ({ r, light }));

describe("calibration and eye gaze", () => {
  it("baseline is the candidate's own median position; too few usable frames gives none", () => {
    const c = new Calibration({ durationMs: 5000 });
    [30, 31, 29, 60, 30, 32, 28, 30, 31, 30, 29].forEach((y, i) => c.add(i * 500, analyzeFaces(result({ yaw: y }))));
    const b = c.add(5500, analyzeFaces(result({ yaw: 30 }))).baseline;
    expect(b.yaw).toBeCloseTo(30, 0); // the one glance (60) does not move the median
    const empty = new Calibration({ durationMs: 2000 });
    [0, 500, 1000, 1500].forEach((t) => empty.add(t, { faces: 0 }));
    expect(empty.add(2000, { faces: 0 })).toMatchObject({ done: true, baseline: null });
  });

  it("a camera placed to the side is not 'looking away' once calibrated", () => {
    const side = result({ yaw: 35 });
    expect(analyzeFaces(side).away).toBe(true); // absolute limits would flag this candidate all interview
    expect(analyzeFaces(side, { yaw: 25, pitch: 20, gaze: 0.5 }, { yaw: 35, pitch: 0, gaze: { x: 0, y: 0 } }).away).toBe(false);
  });

  it("looking at the screen: no events, no warnings", () => {
    expect(play(n(60, result()))).toEqual({ events: [], warnings: [] });
  });

  it("a brief natural glance (2 s) is not recorded", () => {
    const r = play([...n(10, result()), ...n(4, result({ yaw: 45 })), ...n(20, result())]);
    expect(r.events).toEqual([]);
  });

  it("a prolonged deviation becomes ONE event with duration and cause, reminder only after 8 s", () => {
    const short = play([...n(4, result()), ...n(10, result({ gx: 0.9 })), ...n(10, result())]); // ~4.5 s, eyes
    expect(short.events).toHaveLength(1);
    expect(short.events[0]).toMatchObject({ event_type: "attention_away", details: { cause: "eyes" } });
    expect(short.events[0].duration_ms).toBeGreaterThanOrEqual(4000);
    expect(short.warnings).toEqual([]);
    const long = play([...n(30, result({ yaw: 50 })), ...n(10, result())]);
    expect(long.events).toHaveLength(1); // not one per frame
    expect(long.warnings.map((w) => w.type)).toEqual(["attention_away"]);
    expect(long.warnings[0].message).toMatch(/Brief natural movements are acceptable/);
  });

  it("repeated deviations within the window produce one 'repeated' event", () => {
    const rep = new RepeatTracker({ count: 3, windowS: 60 });
    expect(rep.add({ t_ms: 0, duration_ms: 3000 })).toBeNull();
    expect(rep.add({ t_ms: 70_000, duration_ms: 3000 })).toBeNull(); // the first one fell out of the window
    expect(rep.add({ t_ms: 80_000, duration_ms: 3000 })).toBeNull();
    const ev = rep.add({ t_ms: 100_000, duration_ms: 4000 });
    expect(ev).toMatchObject({ event_type: "attention_repeated", t_ms: 70_000, duration_ms: 34_000, details: { count: 3, window_s: 60 } });
    expect(rep.add({ t_ms: 101_000, duration_ms: 3000 })).toBeNull(); // counting starts again
  });

  it("low-confidence (flickering) landmarks give a low agreement score", () => {
    const flicker = Array.from({ length: 30 }, (_, i) => ({ r: result({ yaw: i % 2 ? 50 : 0 }) }));
    const r = play(flicker, { step: 250 });
    r.events.filter((e) => e.event_type === "attention_away").forEach((e) => expect(e.confidence).toBeLessThan(0.6));
  });

  it("poor lighting and no face: gaze is not judged at all", () => {
    const dark = play(n(30, result({ yaw: 50 }), { mean: 30, std: 20 }));
    expect(dark.events.map((e) => e.event_type)).toEqual(["low_light"]); // lighting noted; gaze not guessed in the dark
    const none = play(n(30, { faceLandmarks: [] }));
    expect(none.events.map((e) => e.event_type)).toEqual(["face_absent"]);
    const blocked = observe(analyzeFaces({ faceLandmarks: [] }), { mean: 3, std: 1 }, { attention: true });
    expect(blocked).toMatchObject({ camera_obstructed: true, face_absent: null, attention_away: null });
  });
});

describe("face presence, partial face and multiple faces", () => {
  it("one face visible: nothing recorded", () => {
    expect(play(n(40, result())).events).toEqual([]);
  });

  it("face partly outside the frame is detected with the edge", () => {
    const a = analyzeFaces(result({ cx: 0.9 }));
    expect(a.edge).toBe("right");
    expect(setupGuidance(a, LIGHT).ok).toBe(false);
    const r = play(n(30, result({ cx: 0.9 })));
    expect(r.events.find((e) => e.event_type === "face_partial")).toMatchObject({ details: { edge: "right" } });
  });

  it("multiple faces across consecutive frames: one event with the face count", () => {
    const r = play([...n(10, result({ faces: 2 })), ...n(10, result())]);
    const mf = r.events.filter((e) => e.event_type === "multiple_faces");
    expect(mf).toHaveLength(1);
    expect(mf[0].details).toEqual({ max_faces: 2 });
  });

  it("a brief detection failure is ignored", () => {
    const r = play([...n(10, result()), ...n(3, { faceLandmarks: [] }), ...n(10, result())]);
    expect(r.events).toEqual([]);
  });
});

describe("audio: possible additional voice", () => {
  const speak = (sa, fromMs, toMs, mouth, faces = 1) => {
    for (let t = fromMs; t < toMs; t += 100) {
      sa.audio(0.08, 100, t);
      if (t % 500 === 0) sa.face(t, faces, typeof mouth === "function" ? mouth(t) : mouth);
    }
  };

  it("the candidate talking (mouth moving) is not flagged", () => {
    const sa = new SpeechAttribution();
    sa.begin();
    speak(sa, 0, 8000, (t) => ((t / 500) % 2 ? 0.25 : 0.02));
    expect(sa.end()).toBeNull();
  });

  it("speech while the visible mouth stays still is flagged (uncertain, with agreement)", () => {
    const sa = new SpeechAttribution();
    sa.begin();
    speak(sa, 0, 8000, 0.01);
    const ev = sa.end();
    expect(ev).toMatchObject({ event_type: "background_speech", t_ms: 0 });
    expect(ev.confidence).toBeGreaterThan(0.8);
  });

  it("cannot attribute (no single face) or too little speech: nothing reported", () => {
    const sa = new SpeechAttribution();
    sa.begin();
    speak(sa, 0, 8000, 0.01, 0);
    expect(sa.end()).toBeNull();
    sa.begin();
    speak(sa, 0, 2000, 0.01);
    expect(sa.end()).toBeNull();
  });

  it("a silent gap ends a stretch and judges it; nothing happens while the mic is closed", () => {
    const sa = new SpeechAttribution();
    expect(sa.audio(0.5, 100, 0)).toBeNull(); // not begun: interviewer speaking, mic closed
    sa.begin();
    speak(sa, 0, 6000, 0.0);
    expect(sa.audio(0.0, 100, 7600)).toMatchObject({ event_type: "background_speech" });
  });
});

describe("browser and connection", () => {
  it("tab switch: one event with its duration", () => {
    const f = new FocusTracker(500);
    f.away(10_000);
    expect(f.back(16_000)).toEqual({ event_type: "focus_change", t_ms: 10_000, duration_ms: 6000 });
  });

  it("network outage: one event when it comes back; blips are ignored", () => {
    const c = new ConnectionTracker(2000);
    c.down(1000, "offline");
    c.down(1500, "server_unreachable"); // same outage
    expect(c.online).toBe(false);
    expect(c.up(7000)).toEqual({ event_type: "network_interruption", t_ms: 1000, duration_ms: 6000, details: { reason: "offline" } });
    c.down(9000);
    expect(c.up(9500)).toBeNull();
  });
});

describe("EventReporter", () => {
  let listeners;
  beforeEach(() => {
    listeners = {};
    globalThis.window = { addEventListener: (k, f) => { listeners[k] = f; }, removeEventListener: (k) => { delete listeners[k]; } };
    const mem = {};
    globalThis.sessionStorage = { getItem: (k) => mem[k] ?? null, setItem: (k, v) => { mem[k] = v; }, removeItem: (k) => { delete mem[k]; } };
    post.mockReset();
  });
  afterEach(() => { delete globalThis.window; delete globalThis.sessionStorage; });

  it("gives each event a client id and re-sends the SAME ids after a network failure", async () => {
    const onConnection = vi.fn();
    const r = new EventReporter(7, { onConnection, intervalMs: 1e9 });
    r.add({ event_type: "focus_change", t_ms: 1, duration_ms: 900 });
    post.mockRejectedValueOnce(Object.assign(new Error("offline"), { status: 0 }));
    await r.flush();
    expect(onConnection).toHaveBeenLastCalledWith(false, "server_unreachable");
    const firstIds = post.mock.calls[0][1].events.map((e) => e.client_event_id);
    expect(firstIds[0]).toMatch(/^[A-Za-z0-9_-]{8,40}$/);
    post.mockResolvedValueOnce({ stored: 1 });
    await r.flush();
    expect(post.mock.calls[1][1].events.map((e) => e.client_event_id)).toEqual(firstIds);
    expect(onConnection).toHaveBeenLastCalledWith(true);
    await r.close();
  });

  it("survives a reload: unsent events are picked up by the next page", async () => {
    const a = new EventReporter(8, { intervalMs: 1e9 });
    a.add({ event_type: "face_absent", t_ms: 5, duration_ms: 5000 });
    const b = new EventReporter(8, { intervalMs: 1e9 }); // the reloaded page
    expect(b.queue).toHaveLength(1);
    post.mockResolvedValue({ stored: 1 });
    await b.close();
    expect(post).toHaveBeenCalledTimes(1);
    expect(new EventReporter(8, { intervalMs: 1e9 }).queue).toEqual([]);
  });

  it("keeps events on 429 (rate limited) and drops them when the server rejects them", async () => {
    const r = new EventReporter(9, { intervalMs: 1e9 });
    r.add({ event_type: "focus_change", t_ms: 1, duration_ms: 900 });
    post.mockRejectedValueOnce(Object.assign(new Error("slow down"), { status: 429 }));
    await r.flush();
    expect(r.queue).toHaveLength(1);
    post.mockRejectedValueOnce(Object.assign(new Error("finished"), { status: 400 }));
    await r.flush();
    expect(r.queue).toHaveLength(0);
  });
});

describe("InterviewMonitor reminders and pause rule", () => {
  beforeEach(() => {
    globalThis.window = { addEventListener() {}, removeEventListener() {} };
    globalThis.performance ||= { now: () => Date.now() };
  });
  afterEach(() => { delete globalThis.window; });

  it("does not repeat the same reminder within the cooldown; pause requested only after the configured time", async () => {
    const { InterviewMonitor } = await import("./interviewMonitor");
    const warnings = [];
    const pauses = [];
    const m = new InterviewMonitor({ sessionId: 1, t0: 0, features: { camera: true, face_presence: true },
      policy: { warning_cooldown_s: 30, pause_on_face_absent_s: 10, thresholds: {} },
      onWarning: (w) => warnings.push(w), onPauseRequest: (r) => pauses.push(r) });
    m.onWarning({ type: "face_absent", message: "x" });
    m.onWarning({ type: "face_absent", message: "x" });
    m.onWarning({ type: "multiple_faces", message: "y" });
    expect(warnings.map((w) => w.type)).toEqual(["face_absent", "multiple_faces"]);
    for (let t = 0; t <= 12_000; t += 500) m._pauseRule(t, true);
    expect(pauses).toEqual(["face_absent"]); // once, not every frame
    m._pauseRule(12_500, null); // cannot judge (dark): does not reset
    m._pauseRule(13_000, false); // face back: rule resets
    expect(m.pauseRequested).toBe(false);
    clearInterval(m.reporter.timer);
  });
});
