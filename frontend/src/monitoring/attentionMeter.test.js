import { describe, expect, it } from "vitest";
import { AttentionMeter, STATE, classifyFrame } from "./attentionMeter";

const T = STATE.TOWARD, A = STATE.AWAY;
// samples every `step` ms from `from` (inclusive) to `to` (exclusive), all in `state`
function feed(m, from, to, step, state) {
  for (let t = from; t < to; t += step) m.add(t, state);
}
const meter = (o = {}) => new AttentionMeter({ confirmMs: 0, epoch: "test-epoch-1", ...o });

describe("attention percentage = toward / (toward + away), from elapsed time", () => {
  it("24 s toward + 6 s away = 80%", () => {
    const m = meter();
    feed(m, 0, 24000, 500, T);
    feed(m, 24000, 30000, 500, A);
    expect(m.rolling(30000).pct).toBe(80);
    m.finish(30000);
    const s = m.snapshot();
    expect([s.toward_ms, s.away_ms, s.unobserved_ms]).toEqual([24000, 6000, 0]);
  });

  it("15 s toward + 15 s away = 50%", () => {
    const m = meter();
    feed(m, 0, 15000, 500, T);
    feed(m, 15000, 30000, 500, A);
    expect(m.rolling(30000).pct).toBe(50);
  });

  it("does not depend on the frame rate", () => {
    const hi = meter(), lo = meter();
    for (const [m, step] of [[hi, 100], [lo, 1000]]) {
      feed(m, 0, 20000, step, T);
      feed(m, 20000, 30000, step, A);
    }
    expect(hi.rolling(30000).pct).toBe(67);
    expect(lo.rolling(30000).pct).toBe(67);
  });

  it("uneven sample spacing is weighted by elapsed time, not by count", () => {
    const m = meter();
    m.add(0, T); m.add(100, T); m.add(200, T); m.add(300, T); // four quick samples ...
    m.add(2000, A); // ... then samples that each hold for up to 2 s (inside the 2.5 s gap limit)
    m.add(4000, A);
    m.finish(6000);
    const s = m.snapshot();
    expect(s.toward_ms).toBe(2000);
    expect(s.away_ms).toBe(4000);
  });

  it("duplicates and out-of-order samples are not counted twice", () => {
    const m = meter();
    m.add(0, T); m.add(500, T); m.add(500, A); m.add(400, A); m.add(1000, T);
    m.finish(1000);
    expect(m.snapshot().toward_ms).toBe(1000);
    expect(m.snapshot().away_ms).toBe(0);
  });
});

describe("missing data is never attention and never looking away", () => {
  it("frames that stop arriving become unobserved time", () => {
    const m = meter();
    feed(m, 0, 10000, 500, T);
    m.add(25000, T); // 15 s without a single frame (stalled tab / slow device)
    m.finish(25000);
    const s = m.snapshot();
    expect(s.toward_ms).toBe(9500);
    expect(s.by_reason.gap).toBe(15500);
    expect(s.away_ms).toBe(0);
  });

  it("no face, low confidence and unavailable tracking are separate unobserved reasons", () => {
    const m = meter();
    feed(m, 0, 5000, 500, STATE.FACE_NOT_VISIBLE);
    feed(m, 5000, 8000, 500, STATE.LOW_CONFIDENCE);
    feed(m, 8000, 10000, 500, STATE.UNAVAILABLE);
    m.finish(10000);
    const s = m.snapshot();
    expect(s.by_reason).toEqual({ face_not_visible: 5000, low_confidence: 3000, unavailable: 2000, gap: 0 });
    expect(s.toward_ms + s.away_ms).toBe(0);
    expect(s.unobserved_ms).toBe(10000);
  });

  it("shows 'unavailable' (null), not 0%, when the camera is dead", () => {
    const m = meter();
    feed(m, 0, 60000, 500, STATE.UNAVAILABLE);
    const r = m.rolling(60000);
    expect(r.pct).toBeNull();
    expect(r.coveragePct).toBe(0);
  });

  it("an old percentage is not shown as current once tracking stops", () => {
    const m = meter();
    feed(m, 0, 30000, 500, T);
    expect(m.rolling(30000).pct).toBe(100);
    expect(m.rolling(33000).pct).toBeNull(); // 3.5 s after the last frame nothing recent is valid
    expect(m.rolling(60000).pct).toBeNull();
  });

  it("stops showing the percentage within about a second of losing the face, but not for one missed frame", () => {
    const m = meter();
    feed(m, 0, 30000, 500, T);
    feed(m, 30000, 31000, 500, STATE.FACE_NOT_VISIBLE); // 1 s without a face
    expect(m.rolling(30500).pct).toBe(100); // a blink of the detector: still current
    feed(m, 31000, 33000, 500, STATE.FACE_NOT_VISIBLE);
    expect(m.rolling(33000).pct).toBeNull(); // face gone for 3 s: unavailable, not the old 100%
  });

  it("needs enough valid time before it shows a number, and says it is still collecting", () => {
    const m = meter({ minValidMs: 5000 });
    feed(m, 0, 3000, 500, T);
    expect(m.rolling(3000).pct).toBeNull();
    expect(m.rolling(3000).collecting).toBe(true);
    expect(m.rolling(40000).collecting).toBe(false); // long after the last frame: unavailable, not "collecting"
    feed(m, 3000, 8000, 500, T);
    expect(m.rolling(8000).pct).toBe(100);
  });

  it("coverage reports valid time against monitored time", () => {
    const m = meter();
    feed(m, 0, 24000, 500, T);
    feed(m, 24000, 30000, 500, STATE.FACE_NOT_VISIBLE);
    const r = m.rolling(30000);
    expect(r.pct).toBeNull(); // the last 5 s had no usable face, so no current estimate is shown
    expect(r.coveragePct).toBe(80); // the 6 s without a face lower the coverage; they are not "away"
    m.finish(30000);
    expect(m.snapshot().away_ms).toBe(0);
  });
});

describe("rolling window", () => {
  it("old observations expire", () => {
    const m = meter({ windowMs: 30000 });
    feed(m, 0, 30000, 500, A); // 30 s away ...
    feed(m, 30000, 60000, 500, T); // ... then 30 s toward
    expect(m.rolling(60000).pct).toBe(100);
    expect(m.rolling(45000).pct).toBe(50); // window 15000-45000: 15 s away, 15 s toward
  });

  it("uses the elapsed time so far before the window is full", () => {
    const m = meter();
    feed(m, 0, 10000, 500, T);
    expect(m.rolling(10000).coveragePct).toBe(100);
  });

  it("the window length is configurable", () => {
    const m = meter({ windowMs: 10000 });
    feed(m, 0, 20000, 500, A);
    feed(m, 20000, 30000, 500, T);
    expect(m.rolling(30000).pct).toBe(100);
  });
});

describe("natural movement", () => {
  it("a glance shorter than the confirm time does not count as looking away", () => {
    const m = new AttentionMeter({ confirmMs: 1000, epoch: "test-epoch-1" });
    feed(m, 0, 5000, 500, T);
    feed(m, 5000, 5500, 500, A); // one away sample (0.5 s)
    feed(m, 5500, 10000, 500, T);
    m.finish(10000);
    expect(m.snapshot().away_ms).toBe(0);
  });

  it("a change that lasts is counted, from the moment it was confirmed", () => {
    const m = new AttentionMeter({ confirmMs: 1000, epoch: "test-epoch-1" });
    feed(m, 0, 5000, 500, T);
    feed(m, 5000, 10000, 500, A);
    m.finish(10000);
    const s = m.snapshot();
    expect(s.away_ms).toBe(4000); // confirmed at 6000, so 6000..10000
    expect(s.toward_ms).toBe(6000);
  });
});

describe("pause and calibration are outside the percentage", () => {
  it("paused time is reported but not counted", () => {
    const m = meter();
    feed(m, 0, 10000, 500, T);
    m.setPaused(10000, true);
    m.setPaused(70000, false); // a minute paused, no frames needed
    feed(m, 70000, 80000, 500, A);
    m.finish(80000);
    const s = m.snapshot();
    expect(s.paused_ms).toBe(60000);
    expect(s.unobserved_ms).toBeLessThan(1000);
    expect(s.toward_ms).toBe(10000);
    expect(s.away_ms).toBeGreaterThan(9000);
  });

  it("calibration frames are not counted", () => {
    const m = meter();
    feed(m, 0, 5000, 500, STATE.CALIBRATING);
    feed(m, 5000, 15000, 500, T);
    m.finish(15000);
    const s = m.snapshot();
    expect(s.calibrating_ms).toBe(5000);
    expect(s.toward_ms).toBe(10000);
  });
});

describe("snapshot (what the server stores)", () => {
  it("is monotonic, integer, and its parts add up", () => {
    const m = meter();
    let prev = null;
    for (let t = 0; t < 60000; t += 333) {
      m.add(t + 0.37, t % 7000 < 2000 ? A : t % 11000 < 1500 ? STATE.FACE_NOT_VISIBLE : T);
      if (t % 5000 < 333) {
        const s = m.snapshot();
        for (const k of ["toward_ms", "away_ms", "unobserved_ms"]) expect(Number.isInteger(s[k])).toBe(true);
        expect(s.unobserved_ms).toBe(Object.values(s.by_reason).reduce((a, b) => a + b, 0));
        if (prev) for (const k of ["toward_ms", "away_ms", "unobserved_ms", "paused_ms"]) expect(s[k]).toBeGreaterThanOrEqual(prev[k]);
        prev = s;
      }
    }
  });

  it("timeline buckets hold at most their own length and match the totals", () => {
    const m = meter();
    feed(m, 0, 25000, 500, T);
    feed(m, 25000, 40000, 500, A);
    m.finish(40000);
    const s = m.snapshot();
    expect(s.buckets.every(([, t, a, u]) => t + a + u <= 10000)).toBe(true);
    expect(s.buckets.reduce((x, b) => x + b[1], 0)).toBe(s.toward_ms);
    expect(s.buckets.reduce((x, b) => x + b[2], 0)).toBe(s.away_ms);
  });

  it("a time span crossing a bucket edge is split between the buckets", () => {
    const m = meter({ maxGapMs: 20000 });
    m.add(8000, T);
    m.add(13000, T);
    m.finish(13000);
    expect(m.snapshot().buckets).toEqual([[0, 2000, 0, 0], [1, 3000, 0, 0]]);
  });
});

describe("frame classification", () => {
  const one = { faces: 1, yaw: 3, away: false };
  it("maps what the camera saw to a state", () => {
    expect(classifyFrame({ faces: one })).toBe(T);
    expect(classifyFrame({ faces: { ...one, away: true } })).toBe(A);
    expect(classifyFrame({ faces: { faces: 0 } })).toBe(STATE.FACE_NOT_VISIBLE);
    expect(classifyFrame({ faces: { faces: 2, yaw: 0, away: false } })).toBe(STATE.LOW_CONFIDENCE);
    expect(classifyFrame({ faces: { ...one, edge: "left" } })).toBe(STATE.LOW_CONFIDENCE);
    expect(classifyFrame({ faces: one, dim: true })).toBe(STATE.LOW_CONFIDENCE);
    expect(classifyFrame({ faces: { faces: 1, yaw: null, away: false } })).toBe(STATE.LOW_CONFIDENCE);
    expect(classifyFrame({ faces: { faces: 0 }, obstructed: true })).toBe(STATE.LOW_CONFIDENCE);
    expect(classifyFrame({ faces: one, calibrating: true })).toBe(STATE.CALIBRATING);
  });
});
