import { describe, expect, it } from "vitest";
import { Blinker, Gaze, HeadMotion, Micro, noise1, rng } from "./motion";

const run = (seconds, fps, fn) => { for (let i = 0; i < seconds * fps; i++) fn(i / fps, 1 / fps); };

describe("Blinker", () => {
  it("blinks at varied intervals inside the personality range, with no fixed rhythm", () => {
    const b = new Blinker(rng(3));
    const starts = [];
    let prev = 0;
    run(120, 60, (t) => {
      const v = b.update(t, [2, 6]);
      if (v > 0 && prev === 0) starts.push(t);
      prev = v;
    });
    const gaps = starts.slice(1).map((s, i) => s - starts[i]);
    const single = gaps.filter((g) => g > 0.5); // ignore the short gap inside a double blink
    expect(starts.length).toBeGreaterThan(18); // ~one every 2-6 s over two minutes
    expect(starts.length).toBeLessThan(70);
    expect(Math.max(...single)).toBeLessThanOrEqual(6 * 1.0 + 0.3);
    expect(Math.min(...single)).toBeGreaterThanOrEqual(2 - 0.3);
    const distinct = new Set(single.map((g) => g.toFixed(1)));
    expect(distinct.size).toBeGreaterThan(single.length * 0.5); // not the same interval over and over
    expect(gaps.some((g) => g < 0.5)).toBe(true); // at least one double blink
  });

  it("never stares: the longest open stretch stays below the range maximum (+ listening scale)", () => {
    const b = new Blinker(rng(9));
    let open = 0;
    let longest = 0;
    run(300, 30, (t) => {
      const v = b.update(t, [3, 7], { listening: true });
      open = v > 0 ? 0 : open + 1 / 30;
      longest = Math.max(longest, open);
    });
    expect(longest).toBeLessThan(7 * 1.2 + 0.2);
  });
});

describe("Gaze", () => {
  it("mostly holds eye contact while listening, with only small micro-saccades", () => {
    const g = new Gaze(rng(5));
    let maxDev = 0;
    run(30, 30, (t, dt) => {
      const p = g.update(t, dt, "listening");
      maxDev = Math.max(maxDev, Math.abs(p.x), Math.abs(p.y));
    });
    expect(maxDev).toBeLessThan(0.08);
  });

  it("looks away briefly while talking and comes back to the candidate", () => {
    const g = new Gaze(rng(11));
    let away = 0;
    let total = 0;
    run(60, 30, (t, dt) => {
      const p = g.update(t, dt, "speaking", { talking: true });
      total++;
      if (Math.hypot(p.x, p.y) > 0.09) away++;
    });
    expect(away).toBeGreaterThan(0); // some conversational gaze aversion
    expect(away / total).toBeLessThan(0.35); // but eye contact dominates
  });

  it("looks up and aside while thinking", () => {
    const g = new Gaze(rng(2));
    let p;
    run(3, 30, (t, dt) => { p = g.update(t, dt, "thinking", { base: { x: 0.3, y: 0.4 } }); });
    expect(p.y).toBeGreaterThan(0.25);
    expect(Math.abs(p.x)).toBeGreaterThan(0.15);
  });
});

describe("HeadMotion", () => {
  it("does not repeat: the motion over two windows 20 s apart differs", () => {
    const h = new HeadMotion(4, rng(4));
    const trace = [];
    run(60, 30, (t, dt) => trace.push(h.update(t, dt).head[1]));
    const a = trace.slice(0, 300);
    const b = trace.slice(600, 900);
    const diff = a.reduce((s, v, i) => s + Math.abs(v - b[i]), 0) / a.length;
    expect(diff).toBeGreaterThan(0.002);
  });

  it("stays subtle (no exaggerated head movement)", () => {
    const h = new HeadMotion(8, rng(8));
    let max = 0;
    run(60, 30, (t, dt) => {
      const m = h.update(t, dt, { amp: 0.9, talking: true });
      max = Math.max(max, ...m.head.map(Math.abs));
    });
    expect(max).toBeLessThan(0.12); // ~7 degrees
  });

  it("noise is smooth (no jumps between frames)", () => {
    const n = noise1(1);
    let maxStep = 0;
    for (let i = 1; i < 3000; i++) maxStep = Math.max(maxStep, Math.abs(n(i * 0.01) - n((i - 1) * 0.01)));
    expect(maxStep).toBeLessThan(0.1);
  });
});

describe("Micro", () => {
  it("produces short, small expressions while listening", () => {
    const m = new Micro(rng(6));
    let peak = 0;
    let activeFrames = 0;
    run(40, 30, (t, dt) => {
      const o = m.update(t, dt, "listening", { warmth: 0.7 });
      const v = Math.max(o.smile, o.browUp);
      peak = Math.max(peak, v);
      if (v > 0.01) activeFrames++;
    });
    expect(peak).toBeGreaterThan(0.03);
    expect(peak).toBeLessThan(0.25);
    expect(activeFrames / (40 * 30)).toBeLessThan(0.4); // occasional, not constant
  });
});
