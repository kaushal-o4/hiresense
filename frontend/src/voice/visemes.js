// Lip-sync maths: viseme (mouth shape) parameters, timeline lookup and SVG mouth geometry.
// Pure functions only, so they can be unit-tested without a browser.

// open: jaw/lip opening 0..1 · wide: mouth width factor · round: lip rounding 0..1
// teeth: upper-teeth visibility 0..1 · tongue: tongue visibility 0..1 · press: lips pressed together 0..1
export const SHAPES = {
  sil: { open: 0.0, wide: 1.0, round: 0.0, teeth: 0.0, tongue: 0.0, press: 0.0 },
  PP: { open: 0.0, wide: 0.96, round: 0.05, teeth: 0.0, tongue: 0.0, press: 1.0 },
  FF: { open: 0.1, wide: 1.0, round: 0.0, teeth: 0.9, tongue: 0.0, press: 0.0 },
  TH: { open: 0.2, wide: 1.0, round: 0.0, teeth: 0.6, tongue: 0.9, press: 0.0 },
  DD: { open: 0.28, wide: 1.02, round: 0.0, teeth: 0.6, tongue: 0.55, press: 0.0 },
  KK: { open: 0.38, wide: 1.0, round: 0.0, teeth: 0.4, tongue: 0.2, press: 0.0 },
  CH: { open: 0.3, wide: 0.82, round: 0.55, teeth: 0.8, tongue: 0.2, press: 0.0 },
  SS: { open: 0.14, wide: 1.1, round: 0.0, teeth: 1.0, tongue: 0.0, press: 0.0 },
  RR: { open: 0.28, wide: 0.88, round: 0.45, teeth: 0.3, tongue: 0.3, press: 0.0 },
  AA: { open: 0.82, wide: 1.05, round: 0.0, teeth: 0.35, tongue: 0.1, press: 0.0 },
  E: { open: 0.5, wide: 1.12, round: 0.0, teeth: 0.45, tongue: 0.15, press: 0.0 },
  I: { open: 0.3, wide: 1.2, round: 0.0, teeth: 0.6, tongue: 0.1, press: 0.0 },
  O: { open: 0.6, wide: 0.8, round: 0.8, teeth: 0.15, tongue: 0.05, press: 0.0 },
  U: { open: 0.32, wide: 0.68, round: 1.0, teeth: 0.05, tongue: 0.0, press: 0.0 },
};
const KEYS = ["open", "wide", "round", "teeth", "tongue", "press"];

export function lerpShape(a, b, w) {
  const out = {};
  for (const k of KEYS) out[k] = a[k] + (b[k] - a[k]) * w;
  return out;
}

/** Index of the segment active at time t (binary search), or -1. Segments: [{t, d, v}] sorted by t. */
export function segmentAt(timeline, t) {
  let lo = 0;
  let hi = timeline.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const s = timeline[mid];
    if (t < s.t) hi = mid - 1;
    else if (t >= s.t + s.d) lo = mid + 1;
    else return mid;
  }
  return -1;
}

/** Target mouth shape at time t: the active viseme, blended into the next one near its end (coarticulation). */
export function mouthAt(timeline, t) {
  const i = segmentAt(timeline, t);
  if (i < 0) return { ...SHAPES.sil, viseme: "sil" };
  const seg = timeline[i];
  const cur = SHAPES[seg.v] || SHAPES.sil;
  const p = (t - seg.t) / seg.d;
  const next = timeline[i + 1];
  if (next && p > 0.6 && next.t - (seg.t + seg.d) < 0.03) {
    return { ...lerpShape(cur, SHAPES[next.v] || SHAPES.sil, ((p - 0.6) / 0.4) * 0.5), viseme: seg.v };
  }
  return { ...cur, viseme: seg.v };
}

/**
 * Viseme blend weights at time t for a 3D face with one blendshape per viseme, e.g. {AA: 0.7, E: 0.3}.
 * Same coarticulation rule as mouthAt(): the last 40% of a segment blends into the next viseme.
 */
export function visemeWeightsAt(timeline, t) {
  const i = segmentAt(timeline, t);
  if (i < 0) return { sil: 1 };
  const seg = timeline[i];
  const p = (t - seg.t) / seg.d;
  const next = timeline[i + 1];
  if (next && p > 0.6 && next.t - (seg.t + seg.d) < 0.03 && next.v !== seg.v) {
    const w = ((p - 0.6) / 0.4) * 0.5;
    return { [seg.v]: 1 - w, [next.v]: w };
  }
  return { [seg.v]: 1 };
}

/** Rough visemes from plain text, used only when the browser's own voice is the fallback (no phoneme timing). */
const LETTER_VISEME = { a: "AA", e: "E", i: "I", o: "O", u: "U", y: "I", b: "PP", p: "PP", m: "PP", f: "FF", v: "FF",
  t: "DD", d: "DD", n: "DD", l: "DD", k: "KK", g: "KK", c: "KK", q: "KK", h: "KK", x: "KK", s: "SS", z: "SS",
  j: "CH", r: "RR", w: "U" };
export function approximateVisemes(word, start, rate = 1) {
  const letters = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!letters) return [];
  const per = 0.07 / rate;
  const out = [];
  for (let i = 0; i < letters.length; i++) {
    const v = letters.slice(i, i + 2) === "th" ? "TH" : letters.slice(i, i + 2) === "sh" || letters.slice(i, i + 2) === "ch" ? "CH" : LETTER_VISEME[letters[i]] || "E";
    if (v === "TH" || v === "CH") i++;
    const prev = out[out.length - 1];
    if (prev && prev.v === v) prev.d += per;
    else out.push({ t: start + out.reduce((a, s) => a + s.d, 0), d: per, v });
  }
  return out;
}

/** Map an audio RMS level to a 0..1 openness factor so the mouth closes when the audio is quiet. */
export function amplitudeFactor(rms) {
  const x = Math.min(1, Math.max(0, (rms - 0.004) / 0.05));
  return 0.25 + 0.75 * x * x * (3 - 2 * x);
}

const f = (n) => n.toFixed(1);

/** SVG geometry for the mouth centred at (cx, cy). Returns path strings plus teeth/tongue boxes. */
export function mouthGeometry(m, cx = 200, cy = 304, smile = 0) {
  const halfW = 25 * m.wide * (1 - 0.28 * m.round);
  const gap = m.open * 21 * (1 - m.press);
  const top = gap * 0.42;
  const bottom = gap * 0.58;
  const lipT = 7 * (1 - 0.45 * m.press);
  const lipB = 8.6 * (1 - 0.4 * m.press);
  const k = 0.55 + 0.4 * m.round;
  const cyC = cy - smile * 2.6; // corners lift with a smile
  const L = `${f(cx - halfW)} ${f(cyC)}`;
  const R = `${f(cx + halfW)} ${f(cyC)}`;
  const innerTop = `C ${f(cx + halfW * k)} ${f(cy - top)} ${f(cx - halfW * k)} ${f(cy - top)} ${L}`;
  const innerBottomLR = `C ${f(cx - halfW * k)} ${f(cy + bottom)} ${f(cx + halfW * k)} ${f(cy + bottom)} ${R}`;
  const bow = cy - top - lipT;
  const upper = `M ${L} C ${f(cx - halfW * 0.55)} ${f(bow + 1)} ${f(cx - 6)} ${f(bow - 1.6)} ${f(cx)} ${f(bow + 1.4)} ` +
    `C ${f(cx + 6)} ${f(bow - 1.6)} ${f(cx + halfW * 0.55)} ${f(bow + 1)} ${R} ${innerTop} Z`;
  const lower = `M ${L} ${innerBottomLR} C ${f(cx + halfW * 0.62)} ${f(cy + bottom + lipB)} ` +
    `${f(cx - halfW * 0.62)} ${f(cy + bottom + lipB)} ${L} Z`;
  const inner = `M ${L} ${innerBottomLR} ${innerTop} Z`;
  return {
    upper, lower, inner, gap,
    teeth: { x: cx - halfW * 0.72, y: cy - top - 1, w: halfW * 1.44, h: Math.min(gap, 2 + 6 * m.teeth) * (m.teeth > 0.05 ? 1 : 0) },
    tongue: { cx, cy: cy + bottom - 2 - m.tongue * gap * 0.3, rx: halfW * 0.55, ry: Math.max(0, gap * 0.28 * (0.4 + m.tongue)) },
    jawDrop: gap * 0.45,
  };
}
