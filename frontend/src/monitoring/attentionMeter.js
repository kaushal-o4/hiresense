// Estimated visual attention toward the interview screen, from TIME, not frame counts.
//
//   attention % = time looking toward the screen / (time toward + time away)       (valid observations only)
//   coverage %  = (time toward + time away) / (time toward + away + unobserved)
//
// Every sample says what the camera saw at time t (ms on the interview clock). The state stays in force until the next
// sample ("hold"), but never longer than maxGapMs: missing frames (a stalled tab, a slow device) become UNOBSERVED
// time, so they can neither inflate nor lower the percentage. Frame rate therefore does not matter, a duplicate or
// out-of-order sample is ignored, and no face / low light / unavailable tracking is unobserved too - never "attention"
// and never "looking away". Paused and calibration time are outside both numbers.
//
// A change between toward and away must last `confirmMs` before it counts, so a natural glance or a blink of the
// detector does not move the percentage. Pure and deterministic: no timers, no DOM, no camera.

export const STATE = {
  TOWARD: "toward", AWAY: "away", FACE_NOT_VISIBLE: "face_not_visible", LOW_CONFIDENCE: "low_confidence",
  UNAVAILABLE: "unavailable", PAUSED: "paused", CALIBRATING: "calibrating",
};
const REASONS = ["face_not_visible", "low_confidence", "unavailable", "gap"];
const UNOBSERVED = new Set(REASONS);
const VALID = new Set([STATE.TOWARD, STATE.AWAY]);

export class AttentionMeter {
  constructor({ windowMs = 30000, maxGapMs = 2500, bucketMs = 10000, minValidMs = 5000, confirmMs = 1000, epoch } = {}) {
    this.windowMs = windowMs;
    this.maxGapMs = maxGapMs;
    this.bucketMs = bucketMs;
    this.minValidMs = minValidMs;
    this.confirmMs = confirmMs;
    this.epoch = epoch || newEpoch();
    this.last = null; // {t, state}: the state in force since time t
    this.pending = null; // {state, since}: an unconfirmed switch between toward and away
    this.paused = false;
    this.intervals = []; // closed [t0, t1, state] spans for the rolling window
    this.total = { toward: 0, away: 0, paused: 0, calibrating: 0, reasons: Object.fromEntries(REASONS.map((r) => [r, 0])) };
    this.buckets = new Map(); // bucket index -> {toward, away, unobserved}
  }

  /** One observation at time tMs (interview clock, ms). state is one of STATE.*. */
  add(tMs, state) {
    if (!Number.isFinite(tMs) || (this.last && tMs <= this.last.t)) return; // duplicate / out of order
    if (this.firstT === undefined) this.firstT = tMs;
    let effective = this.paused ? STATE.PAUSED : state;
    if (VALID.has(effective)) effective = this._confirm(tMs, effective);
    else this.pending = null;
    if (this.last) this._close(this.last.t, tMs, this._heldState(this.last, tMs - this.last.t));
    this.last = { t: tMs, state: effective };
    this._prune(tMs);
  }

  /** The interview is paused/resumed: that time is outside the percentage and the coverage. */
  setPaused(tMs, paused) {
    if (paused === this.paused) return;
    if (this.last && tMs > this.last.t) this._close(this.last.t, tMs, this._heldState(this.last, tMs - this.last.t));
    this.paused = paused;
    this.pending = null;
    this.last = { t: Math.max(tMs, this.last?.t ?? tMs), state: paused ? STATE.PAUSED : STATE.UNAVAILABLE };
  }

  /** Account for the time up to tMs (the monitor is stopping). */
  finish(tMs) {
    if (this.last && tMs > this.last.t) {
      this._close(this.last.t, tMs, this._heldState(this.last, tMs - this.last.t));
      this.last = { t: tMs, state: this.last.state };
    }
  }

  // Natural glances: toward <-> away only counts after it has lasted confirmMs.
  _confirm(t, raw) {
    const held = this.last && VALID.has(this.last.state) ? this.last.state : null;
    if (held === null || raw === held) { this.pending = null; return raw; }
    if (!this.pending || this.pending.state !== raw) this.pending = { state: raw, since: t };
    if (t - this.pending.since >= this.confirmMs) { this.pending = null; return raw; }
    return held;
  }

  // What the span after `last` counts as: its own state while samples keep coming, "gap" once they stop.
  _heldState(last, dt) {
    if (last.state === STATE.PAUSED) return STATE.PAUSED; // no frames are expected while paused
    return dt <= this.maxGapMs ? last.state : "gap";
  }

  _close(t0, t1, state) {
    if (t1 <= t0) return;
    this.intervals.push([t0, t1, state]);
    this._count(this.total, this.buckets, t0, t1, state);
  }

  _count(total, buckets, t0, t1, state) {
    const d = t1 - t0;
    if (state === STATE.TOWARD) total.toward += d;
    else if (state === STATE.AWAY) total.away += d;
    else if (state === STATE.PAUSED) total.paused += d;
    else if (state === STATE.CALIBRATING) total.calibrating += d;
    else if (UNOBSERVED.has(state)) total.reasons[state] += d;
    else return;
    if (state === STATE.PAUSED || state === STATE.CALIBRATING) return; // not part of the timeline
    for (let i = Math.floor(t0 / this.bucketMs); i * this.bucketMs < t1; i++) {
      const overlap = Math.min(t1, (i + 1) * this.bucketMs) - Math.max(t0, i * this.bucketMs);
      if (overlap <= 0) continue;
      const b = buckets.get(i) || { toward: 0, away: 0, unobserved: 0 };
      if (state === STATE.TOWARD) b.toward += overlap;
      else if (state === STATE.AWAY) b.away += overlap;
      else b.unobserved += overlap;
      buckets.set(i, b);
    }
  }

  _prune(now) {
    const keepFrom = now - this.windowMs - 60000;
    while (this.intervals.length && this.intervals[0][1] < keepFrom) this.intervals.shift();
  }

  // Time per class inside [from, to], including the open span after the last sample.
  _span(from, to) {
    const out = { toward: 0, away: 0, unobserved: 0 };
    const add = (t0, t1, state) => {
      const d = Math.min(t1, to) - Math.max(t0, from);
      if (d <= 0) return;
      if (state === STATE.TOWARD) out.toward += d;
      else if (state === STATE.AWAY) out.away += d;
      else if (UNOBSERVED.has(state)) out.unobserved += d;
    };
    for (const [t0, t1, state] of this.intervals) add(t0, t1, state);
    if (this.last && to > this.last.t) add(this.last.t, to, this._heldState(this.last, to - this.last.t));
    return out;
  }

  /**
   * The live figure for the last windowMs. pct is null ("estimate unavailable") when there is not enough valid
   * observation in the window or no usable observation in the last 2 seconds - an old value is never shown as current.
   */
  rolling(nowMs) {
    const from = Math.max(nowMs - this.windowMs, this.firstT ?? nowMs - this.windowMs);
    const w = this._span(from, nowMs);
    const valid = w.toward + w.away;
    // "Current" = valid observation in the last 2 s (a blink of the detector is tolerated, a lost face is not).
    const recent = this._span(nowMs - 2000, nowMs);
    const live = recent.toward + recent.away >= 1200;
    const monitored = valid + w.unobserved;
    const pct = valid >= this.minValidMs && live ? Math.round((100 * w.toward) / valid) : null;
    // collecting: tracking works but there is not enough valid time yet (start of the interview, after calibration)
    return { pct, collecting: live && valid < this.minValidMs, validMs: Math.round(valid), unobservedMs: Math.round(w.unobserved), windowMs: this.windowMs,
      coveragePct: monitored > 0 ? Math.round((100 * valid) / monitored) : null,
      state: this.paused ? STATE.PAUSED : this.last ? this._heldState(this.last, nowMs - this.last.t) : STATE.UNAVAILABLE };
  }

  /** Cumulative time totals of CLOSED time (what the server stores). Monotonic: a later snapshot is never smaller. */
  snapshot() {
    const r = Object.fromEntries(REASONS.map((k) => [k, Math.round(this.total.reasons[k])]));
    const idx = [...this.buckets.keys()].sort((a, b) => a - b).slice(-720);
    return {
      epoch: this.epoch, window_ms: this.windowMs,
      toward_ms: Math.round(this.total.toward), away_ms: Math.round(this.total.away),
      unobserved_ms: REASONS.reduce((s, k) => s + r[k], 0), // the same rounded numbers, so the parts add up
      paused_ms: Math.round(this.total.paused), calibrating_ms: Math.round(this.total.calibrating), by_reason: r,
      buckets: idx.map((i) => {
        const b = this.buckets.get(i);
        return [i, Math.round(b.toward), Math.round(b.away), Math.round(b.unobserved)];
      }),
    };
  }
}

/** One camera frame -> what it says about attention. faces: analyzeFaces() output; light: brightness summary or null. */
export function classifyFrame({ faces, obstructed, dim, calibrating }) {
  if (calibrating) return STATE.CALIBRATING;
  if (obstructed) return STATE.LOW_CONFIDENCE;
  if (!faces.faces) return STATE.FACE_NOT_VISIBLE;
  if (faces.faces > 1 || faces.edge || dim || faces.yaw === null || faces.yaw === undefined) return STATE.LOW_CONFIDENCE;
  return faces.away ? STATE.AWAY : STATE.TOWARD;
}

function newEpoch() {
  try { if (crypto?.randomUUID) return crypto.randomUUID().replace(/-/g, "").slice(0, 24); } catch { /* older browser */ }
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`;
}
