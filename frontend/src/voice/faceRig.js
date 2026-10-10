// Face-rig adapter: one vocabulary for every avatar model. Pure (no three.js), so it is unit-tested.
//
// The renderer always speaks "canonical" channel names:
//   * ARKit's 52 blendshape names in camelCase (eyeBlinkLeft, jawOpen, mouthSmileLeft, ...)
//   * "viseme:<id>" for the 15 Oculus visemes our lip sync produces (viseme:PP, viseme:AA, ...)
// buildRig() maps them onto whatever a model actually contains:
//   * Microsoft Rocketbox  - "AA_VI_01_PP" visemes + "AK_09_EyeBlinkLeft" ARKit shapes
//   * ARKit-52 models      - e.g. a MetaHuman baked by avatar-src/convert_metahuman.py ("eyeBlinkLeft", "jawOpen")
//   * other common spellings: "EyeBlink_L", "blendShape1.eyeBlinkLeft", "viseme_PP"
// A model without viseme shapes still gets real phoneme lip sync: VISEME_ARKIT spells every viseme as a mix of
// ARKit mouth shapes.

export const VISEMES = ["sil", "PP", "FF", "TH", "DD", "KK", "CH", "SS", "NN", "RR", "AA", "E", "I", "O", "U"];

export const ARKIT = [
  "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft", "browOuterUpRight",
  "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
  "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft", "eyeLookDownRight", "eyeLookInLeft", "eyeLookInRight",
  "eyeLookOutLeft", "eyeLookOutRight", "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight",
  "eyeWideLeft", "eyeWideRight",
  "jawForward", "jawLeft", "jawOpen", "jawRight",
  "mouthClose", "mouthDimpleLeft", "mouthDimpleRight", "mouthFrownLeft", "mouthFrownRight", "mouthFunnel",
  "mouthLeft", "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft", "mouthPressRight", "mouthPucker",
  "mouthRight", "mouthRollLower", "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper", "mouthSmileLeft",
  "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight", "mouthUpperUpLeft", "mouthUpperUpRight",
  "noseSneerLeft", "noseSneerRight", "tongueOut",
];
const ARKIT_BY_KEY = Object.fromEntries(ARKIT.map((n) => [n.toLowerCase(), n]));

// Each viseme as ARKit mouth shapes, for models that have no viseme blendshapes. Tuned so that closures
// (PP/FF) really close and rounded vowels (O/U) really round; the jaw carries most of the opening.
export const VISEME_ARKIT = {
  sil: {},
  PP: { mouthPressLeft: 0.55, mouthPressRight: 0.55, mouthRollLower: 0.3, mouthRollUpper: 0.2, mouthClose: 0.1 },
  FF: { jawOpen: 0.08, mouthRollLower: 0.55, mouthUpperUpLeft: 0.22, mouthUpperUpRight: 0.22, mouthShrugUpper: 0.1 },
  TH: { jawOpen: 0.16, tongueOut: 0.35, mouthUpperUpLeft: 0.1, mouthUpperUpRight: 0.1 },
  DD: { jawOpen: 0.22, mouthStretchLeft: 0.1, mouthStretchRight: 0.1, mouthUpperUpLeft: 0.12, mouthUpperUpRight: 0.12 },
  KK: { jawOpen: 0.3, mouthStretchLeft: 0.15, mouthStretchRight: 0.15 },
  CH: { jawOpen: 0.16, mouthFunnel: 0.5, mouthUpperUpLeft: 0.2, mouthUpperUpRight: 0.2 },
  SS: { jawOpen: 0.07, mouthStretchLeft: 0.32, mouthStretchRight: 0.32, mouthUpperUpLeft: 0.15, mouthUpperUpRight: 0.15 },
  NN: { jawOpen: 0.15, mouthStretchLeft: 0.1, mouthStretchRight: 0.1 },
  RR: { jawOpen: 0.17, mouthFunnel: 0.35, mouthPucker: 0.2 },
  AA: { jawOpen: 0.58, mouthLowerDownLeft: 0.25, mouthLowerDownRight: 0.25 },
  E: { jawOpen: 0.34, mouthStretchLeft: 0.28, mouthStretchRight: 0.28, mouthLowerDownLeft: 0.15, mouthLowerDownRight: 0.15 },
  I: { jawOpen: 0.2, mouthStretchLeft: 0.38, mouthStretchRight: 0.38, mouthSmileLeft: 0.12, mouthSmileRight: 0.12 },
  O: { jawOpen: 0.38, mouthFunnel: 0.6, mouthPucker: 0.2 },
  U: { jawOpen: 0.14, mouthPucker: 0.72, mouthFunnel: 0.3 },
};

// ARKit channels that shape the mouth: while speaking, the lip-sync layer owns them.
export const MOUTH_CHANNELS = new Set(ARKIT.filter((n) => /^(mouth|jaw|tongue|cheekPuff)/.test(n)));

/** Canonical name for one morph-target name, or null if it is not a channel we drive. */
export function canonicalName(raw) {
  let n = String(raw).split(".").pop(); // "blendShape1.eyeBlinkLeft"
  const vis = n.match(/^(?:AA_VI_\d\d_|viseme_)(\w+)$/i); // Rocketbox / Ready Player Me style visemes
  if (vis) {
    const id = VISEMES.find((v) => v.toLowerCase() === vis[1].toLowerCase());
    return id ? `viseme:${id}` : null;
  }
  n = n.replace(/^AK_\d\d_/, ""); // Rocketbox ARKit prefix
  n = n.replace(/[_.]?L$/, "Left").replace(/[_.]?R$/, "Right"); // "EyeBlink_L" -> "EyeBlinkLeft"
  return ARKIT_BY_KEY[n.replace(/[_\s]/g, "").toLowerCase()] || null;
}

/**
 * Inspect a model's morph-target names (morphTargetDictionary keys of its face meshes).
 * Returns { kind, names: canonical -> actual morph name, hasVisemes, has(c) }.
 */
export function buildRig(morphNames) {
  const names = {};
  for (const raw of morphNames) {
    const c = canonicalName(raw);
    if (c && !(c in names)) names[c] = raw;
  }
  const visemeCount = VISEMES.filter((v) => `viseme:${v}` in names).length;
  const arkitCount = ARKIT.filter((a) => a in names).length;
  const rocketbox = morphNames.some((n) => /^AA_VI_\d\d_/.test(n));
  return {
    kind: rocketbox ? "rocketbox" : arkitCount >= 40 ? "arkit" : arkitCount || visemeCount ? "partial" : "none",
    names,
    visemeCount,
    arkitCount,
    hasVisemes: visemeCount >= 10, // otherwise visemes are spelled with ARKit shapes
    has: (c) => c in names,
  };
}

const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

/**
 * Compose every animation layer into final channel weights. Layers in priority order:
 *   1. lip sync (visemes from the audio actually playing)  - owns the mouth while speaking
 *   2. speech-coupled motion (cheeks follow the jaw, brows lift with vocal emphasis)
 *   3. expression (smile, brows, squint, scepticism) - mouth parts yield to lip sync
 *   4. eyes (gaze, blinks, eyelids following the gaze)
 *   5. idle micro-motion
 * A lower layer can never override a higher one on the channels the higher one owns.
 *
 * f = { visemes: {id: w}, amp, talking, expr: {smile, browUp, browDown, squint, skeptic, press},
 *       gaze: {x, y}, blink, micro: {browUp, smile} }
 */
export function composeFace(rig, f) {
  const out = {};
  const add = (c, v) => { if (v) out[c] = (out[c] || 0) + v; };
  const vis = f.visemes || {};
  const talking = !!f.talking;

  // ---- 1. lip sync
  let mouthActivity = 0;
  if (rig.hasVisemes) {
    for (const id of VISEMES) {
      const w = vis[id] || 0;
      if (w) out[`viseme:${id}`] = w;
      if (id !== "sil") mouthActivity += w;
    }
  } else {
    for (const [id, w] of Object.entries(vis)) {
      if (!w) continue;
      if (id !== "sil") mouthActivity += w;
      for (const [c, v] of Object.entries(VISEME_ARKIT[id] || {})) add(c, v * w);
    }
  }
  mouthActivity = clamp01(mouthActivity);
  const lip = { ...out }; // what lip sync asked for

  // ---- 2. speech-coupled motion
  const jaw = rig.hasVisemes ? mouthActivity * 0.5 : (lip.jawOpen || 0);
  const amp = talking ? (f.amp || 0) : 0;

  // ---- 3. expression (mouth parts attenuated while the lips are busy)
  const e = f.expr || {};
  const m = f.micro || {};
  const yieldMouth = 1 - 0.55 * mouthActivity;
  const smile = clamp01(((e.smile || 0) + (m.smile || 0)) * yieldMouth);
  const mouthExpr = {
    mouthSmileLeft: smile, mouthSmileRight: smile * 0.92, // a perfectly symmetric smile reads as fake
    mouthDimpleLeft: smile * 0.25, mouthDimpleRight: smile * 0.2,
    mouthPressLeft: talking ? 0 : (e.press || 0), mouthPressRight: talking ? 0 : (e.press || 0) * 0.9,
  };
  for (const [c, v] of Object.entries(mouthExpr)) {
    // the lip-sync value wins; expression only fills in what lip sync left unused
    out[c] = Math.max(lip[c] || 0, v * (1 - (lip[c] || 0)));
  }
  add("cheekSquintLeft", smile * 0.45 + jaw * 0.08);
  add("cheekSquintRight", smile * 0.42 + jaw * 0.08);
  const browUp = (e.browUp || 0) + (m.browUp || 0) + amp * 0.22;
  const sk = e.skeptic || 0;
  add("browInnerUp", browUp);
  add("browOuterUpLeft", browUp * 0.6 + sk * 0.7);
  add("browOuterUpRight", browUp * 0.6 * (1 - sk));
  add("browDownLeft", (e.browDown || 0) * (1 - sk));
  add("browDownRight", (e.browDown || 0) * 0.4 + sk * 0.45);
  add("noseSneerLeft", (e.browDown || 0) * 0.12); // a frown pulls the nose a little
  add("noseSneerRight", (e.browDown || 0) * 0.12);

  // ---- 4. eyes
  const g = f.gaze || { x: 0, y: 0 };
  const blink = clamp01(f.blink || 0);
  const down = Math.max(0, -g.y);
  const up = Math.max(0, g.y);
  add("eyeLookOutLeft", Math.max(0, g.x)); add("eyeLookInRight", Math.max(0, g.x));
  add("eyeLookInLeft", Math.max(0, -g.x)); add("eyeLookOutRight", Math.max(0, -g.x));
  add("eyeLookUpLeft", up); add("eyeLookUpRight", up);
  add("eyeLookDownLeft", down); add("eyeLookDownRight", down);
  const squint = (e.squint || 0) + smile * 0.25; // a real smile narrows the eyes (Duchenne)
  // upper lids follow the eyes: they drop when looking down and the blink always wins over the squint
  const lidL = Math.max(blink, squint * 0.35 + down * 0.35);
  const lidR = Math.max(blink, (squint + sk * 0.2) * 0.35 + down * 0.35);
  add("eyeBlinkLeft", lidL); add("eyeBlinkRight", lidR);
  add("eyeSquintLeft", squint * (1 - blink)); add("eyeSquintRight", (squint + sk * 0.2) * (1 - blink));
  add("eyeWideLeft", up * 0.25 * (1 - blink)); add("eyeWideRight", up * 0.25 * (1 - blink));

  for (const c of Object.keys(out)) out[c] = clamp01(out[c]);
  return { weights: out, mouthActivity };
}
