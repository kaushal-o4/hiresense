// Procedural "aliveness" for the interviewer: gaze, blinks, head motion and micro-expressions.
// Pure (no three.js / DOM). Every controller takes an injectable random source so tests are deterministic.
//
// Why this exists: the original avatar summed a few sine waves, so its head traced the same path every ~20 s and
// blinked on a fixed rhythm - the main reason it read as a doll. Here:
//   * head motion is smooth value noise (never repeats) plus short "beat" nods on vocal emphasis,
//   * the eyes hold a fixation, make small micro-saccades, and look away briefly while speaking or thinking -
//     the way people break eye contact when they talk - then return to the candidate,
//   * blinks have random intervals, varied speed, occasional doubles and half blinks, and big gaze shifts often
//     trigger a blink (as in real people),
//   * micro-expressions are short (0.4-1.2 s), small and tied to the conversation state.

/** Deterministic PRNG (mulberry32) so a test can replay a run exactly. */
export function rng(seed = 1) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Smooth 1-D value noise in [-1, 1] with a few octaves; never repeats for practical durations. */
export function noise1(seed = 1) {
  const r = rng(seed);
  const table = Array.from({ length: 512 }, () => r() * 2 - 1);
  const at = (i) => table[((i % 512) + 512) % 512];
  const octave = (x) => {
    const i = Math.floor(x);
    const f = x - i;
    const s = f * f * (3 - 2 * f);
    return at(i) + (at(i + 1) - at(i)) * s;
  };
  // incommensurate octave frequencies -> no audible/visible period
  return (x) => (octave(x) * 0.62 + octave(x * 2.13 + 17.3) * 0.26 + octave(x * 4.71 + 41.9) * 0.12);
}

const smooth = (cur, target, rate, dt) => cur + (target - cur) * (1 - Math.exp(-rate * dt));

/**
 * Gaze: where the eyes point, in blendshape units (x: + = avatar's left, y: + = up). (0, 0) = the candidate.
 * Eyes move with saccades (fast, ~50 ms) between fixations and hold still in between.
 */
export class Gaze {
  constructor(random = Math.random) {
    this.r = random;
    this.x = 0; this.y = 0;
    this.tx = 0; this.ty = 0;
    this.next = 0.5;
    this.awayUntil = -1;
    this.mode = null;
  }

  /** Returns {x, y, saccade} where saccade = size of a gaze jump started this frame (for blink coupling). */
  update(t, dt, mode, { talking = false, base = { x: 0, y: 0 } } = {}) {
    let saccade = 0;
    const jump = (x, y) => {
      saccade = Math.hypot(x - this.tx, y - this.ty);
      this.tx = x; this.ty = y;
    };
    if (mode !== this.mode) {
      this.mode = mode;
      this.awayUntil = -1;
      this.next = t; // re-plan immediately on a state change
    }
    if (t >= this.next) {
      const r = this.r;
      if (mode === "thinking") {
        // look up and to one side while "thinking", drifting between nearby points
        const side = base.x || (r() < 0.5 ? -0.3 : 0.3);
        jump(side + (r() - 0.5) * 0.1, (base.y || 0.35) + (r() - 0.5) * 0.08);
        this.next = t + 0.8 + r() * 1.4;
      } else if (this.awayUntil > t) {
        this.next = this.awayUntil; // still looking away; come back when it ends
      } else if (this.awayUntil > 0) {
        this.awayUntil = -1; // return to the candidate
        jump(base.x + (r() - 0.5) * 0.04, base.y + (r() - 0.5) * 0.03);
        this.next = t + 0.6 + r() * 1.6;
      } else if ((mode === "speaking" || mode === "probing" || mode === "feedback" || mode === "greeting") && talking
        && r() < 0.22) {
        // brief conversational gaze aversion while talking (down-aside more than up), 0.4-1.0 s
        const sx = (r() < 0.5 ? -1 : 1) * (0.1 + r() * 0.12);
        jump(sx, r() < 0.65 ? -(0.06 + r() * 0.08) : 0.08 + r() * 0.06);
        this.awayUntil = t + 0.4 + r() * 0.6;
        this.next = this.awayUntil;
      } else {
        // fixation on the candidate's face: micro-saccades between eyes and mouth (tiny jumps)
        const listening = mode === "listening";
        jump(base.x + (r() - 0.5) * (listening ? 0.05 : 0.07), base.y + (r() - 0.5) * 0.04 - (r() < 0.25 ? 0.03 : 0));
        this.next = t + (listening ? 0.7 + r() * 2.0 : 0.5 + r() * 1.5);
      }
    }
    // saccades are fast; tiny drift is slower
    this.x = smooth(this.x, this.tx, 32, dt);
    this.y = smooth(this.y, this.ty, 32, dt);
    return { x: this.x, y: this.y, saccade };
  }
}

/**
 * Blinks: 0 (open) .. 1 (closed). Intervals are random within [lo, hi] (per personality) and skewed short, with
 * ~12% double blinks, ~10% half blinks, closing faster than opening, and a blink often accompanying a big gaze shift.
 */
export class Blinker {
  constructor(random = Math.random) {
    this.r = random;
    this.start = -1;
    this.next = 1 + random() * 2;
    this.dur = 0.15;
    this.depth = 1;
    this.pendingDouble = false;
  }

  trigger(t) { if (this.start < 0 && t > this.next - 1.2) this.next = t; } // allowed if not just blinked

  update(t, every = [2, 6], { listening = false, speaking = false } = {}) {
    if (this.start < 0 && t >= this.next) {
      this.start = t;
      this.dur = 0.12 + this.r() * 0.08;
      this.depth = this.r() < 0.1 ? 0.55 + this.r() * 0.25 : 1;
    }
    if (this.start < 0) return 0;
    const p = (t - this.start) / this.dur;
    if (p >= 1) {
      this.start = -1;
      const r = this.r;
      if (!this.pendingDouble && r() < 0.12) {
        this.pendingDouble = true;
        this.next = t + 0.12 + r() * 0.12;
      } else {
        this.pendingDouble = false;
        const [lo, hi] = every;
        // people blink a bit less while listening attentively and more while talking
        const scale = listening ? 1.2 : speaking ? 0.85 : 1;
        const u = r() * r() * 0.6 + r() * 0.4; // skewed towards shorter gaps, still within [lo, hi]
        this.next = t + (lo + u * (hi - lo)) * scale;
      }
      return 0;
    }
    // close in the first 35%, open over the remaining 65%
    const v = p < 0.35 ? p / 0.35 : 1 - (p - 0.35) / 0.65;
    return Math.max(0, Math.min(1, v)) * this.depth;
  }
}

/**
 * Head and upper-body motion (radians). Smooth noise for idle sway, amplitude rising with speech, plus small
 * "beat" nods when the voice gets louder after a quieter stretch (the head marks stressed syllables).
 */
export class HeadMotion {
  constructor(seed = 7, random = Math.random) {
    this.r = random;
    this.nx = noise1(seed); this.ny = noise1(seed + 11); this.nz = noise1(seed + 23);
    this.nb = noise1(seed + 37);
    this.ampAvg = 0;
    this.beat = 0;
    this.beatDir = 1;
    this.lastBeat = -10;
    this.nod = 0;
    this.breath = 0;
  }

  /** Start one acknowledging nod (e.g. after the candidate finishes). */
  nodOnce() { this.nod = 1; }

  update(t, dt, { amp = 0, talking = false, scale = 1, nodSize = 1, nodRate = 0, lean = 0 } = {}) {
    // beat detection: loudness jumps above its running average
    this.ampAvg = smooth(this.ampAvg, amp, 3, dt);
    if (talking && amp - this.ampAvg > 0.22 && t - this.lastBeat > 0.45) {
      this.beat = 1;
      this.beatDir = this.r() < 0.75 ? 1 : -1;
      this.lastBeat = t;
    }
    this.beat = Math.max(0, this.beat - dt * 3.2);
    if (nodRate && t - this.lastBeat > 1 && this.r() < dt * 0.22 * nodRate) this.nod = Math.max(this.nod, 0.7);
    this.nod = Math.max(0, this.nod - dt * 1.4);

    const speech = talking ? 0.6 + amp * 0.8 : 0;
    const idle = 0.016 + speech * 0.014;
    const beatPitch = Math.sin((1 - this.beat) * Math.PI) * this.beat * 0.035 * this.beatDir;
    const nodPitch = Math.sin((1 - this.nod) * Math.PI * 2) * this.nod * 0.055 * nodSize;
    // breathing: ~14 breaths/min, depth slowly varying
    this.breath += dt * (0.23 + this.nb(t * 0.05) * 0.03) * Math.PI * 2;
    const breathDepth = 0.006 + (this.nb(t * 0.11) + 1) * 0.002;
    return {
      head: [
        (this.nx(t * 0.35) * idle + beatPitch) * scale + nodPitch + lean,
        this.ny(t * 0.28) * (idle * 1.6) * scale,
        this.nz(t * 0.22) * idle * 0.7 * scale,
      ],
      neck: [this.nx(t * 0.21 + 50) * 0.008 * scale, this.ny(t * 0.17 + 50) * 0.012 * scale, 0],
      spine: [Math.sin(this.breath) * breathDepth + lean * 0.4, this.nz(t * 0.09 + 90) * 0.006 * scale, 0],
    };
  }
}

/**
 * Micro-expressions: short, small additive offsets (browUp, smile) tied to the state.
 * Listening: an occasional interested brow lift or a slight warm smile (per personality `warmth`).
 * Speaking: a brow lift at the start of a phrase (voice onset after a pause).
 */
export class Micro {
  constructor(random = Math.random) {
    this.r = random;
    this.active = null; // {key, size, start, dur}
    this.next = 2;
    this.silentFor = 0;
  }

  update(t, dt, mode, { amp = 0, talking = false, warmth = 0.5, expressiveness = 1 } = {}) {
    const r = this.r;
    const onset = talking && amp > 0.35 && this.silentFor > 0.35;
    this.silentFor = talking && amp > 0.3 ? 0 : this.silentFor + dt;
    if (!this.active) {
      if (onset && r() < 0.5) {
        this.active = { key: "browUp", size: (0.1 + r() * 0.1) * expressiveness, start: t, dur: 0.5 + r() * 0.4 };
      } else if (t >= this.next && mode === "listening") {
        const key = r() < warmth ? "smile" : "browUp";
        this.active = { key, size: (key === "smile" ? 0.12 : 0.1) * (0.7 + r() * 0.6) * expressiveness, start: t,
          dur: 0.7 + r() * 0.5 };
        this.next = t + 3 + r() * 5;
      } else if (t >= this.next) {
        this.next = t + 2 + r() * 4;
      }
    }
    const out = { browUp: 0, smile: 0 };
    if (this.active) {
      const p = (t - this.active.start) / this.active.dur;
      if (p >= 1) this.active = null;
      else out[this.active.key] = Math.sin(p * Math.PI) * this.active.size; // ease in and out
    }
    return out;
  }
}
