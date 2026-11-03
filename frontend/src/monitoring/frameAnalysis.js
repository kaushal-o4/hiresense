// Per-frame measurements from MediaPipe Face Landmarker output and a tiny downscaled frame. Pure functions.
// Only geometry is used: number of faces, where the face is, approximate head direction and eye direction.
// Nothing here identifies a person, and expressions/emotions are never computed. None of it leaves the browser.

/** Mean and spread of brightness (0-255) of an RGBA pixel buffer. */
export function brightness(data) {
  let sum = 0;
  let sq = 0;
  const n = data.length / 4;
  for (let i = 0; i < data.length; i += 4) {
    const y = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    sum += y;
    sq += y * y;
  }
  const mean = sum / Math.max(1, n);
  return { mean, std: Math.sqrt(Math.max(0, sq / Math.max(1, n) - mean * mean)) };
}

/** Yaw/pitch in degrees from MediaPipe's 4x4 facial transformation matrix (column-major). */
export function headAngles(matrix) {
  if (!matrix || matrix.length < 16) return null;
  const m = matrix;
  const yaw = Math.asin(Math.max(-1, Math.min(1, -m[2]))) * (180 / Math.PI);
  const pitch = Math.atan2(m[6], m[10]) * (180 / Math.PI);
  return { yaw, pitch };
}

/** Rough yaw from landmarks when no matrix is available: nose position between the outer eye corners. */
export function yawFromLandmarks(lm) {
  const nose = lm[1];
  const l = lm[33];
  const r = lm[263];
  if (!nose || !l || !r || r.x === l.x) return null;
  const ratio = (nose.x - l.x) / (r.x - l.x);
  return (ratio - 0.5) * 90;
}

/** Horizontal / vertical eye direction from ARKit-style eye blendshapes (-1..1, approximate). */
export function gazeFromBlendshapes(categories) {
  if (!categories?.length) return null;
  const s = Object.fromEntries(categories.map((c) => [c.categoryName, c.score]));
  if (s.eyeLookOutLeft === undefined) return null;
  // subject's right: left eye looks "in", right eye looks "out"
  const x = ((s.eyeLookInLeft + s.eyeLookOutRight) - (s.eyeLookOutLeft + s.eyeLookInRight)) / 2;
  const y = ((s.eyeLookUpLeft + s.eyeLookUpRight) - (s.eyeLookDownLeft + s.eyeLookDownRight)) / 2;
  return { x, y };
}

export const ATTENTION_LIMITS = { yaw: 30, pitch: 25, gaze: 0.6 };
const EDGE = 0.02; // landmarks this close to the picture border = the face is cut off by the frame

/** Mouth opening (0-1) from the jawOpen blendshape; used only to tell whether the visible person is speaking. */
export function mouthOpen(categories) {
  const c = categories?.find((x) => x.categoryName === "jawOpen");
  return c ? c.score : null;
}

/**
 * FaceLandmarkerResult -> {faces, box, centered, edge, yaw, pitch, gaze, away, cause, mouth} (for the first face).
 * baseline: the candidate's own neutral {yaw, pitch, gaze:{x,y}} from calibration - deviations are measured from it,
 * because screen placement, posture and facial geometry differ between people. Without one, absolute limits apply.
 */
export function analyzeFaces(result, limits = ATTENTION_LIMITS, baseline = null) {
  const faces = result?.faceLandmarks?.length || 0;
  if (!faces) return { faces: 0 };
  const lm = result.faceLandmarks[0];
  let minX = 1, minY = 1, maxX = 0, maxY = 0;
  for (const p of lm) {
    if (p.x < minX) minX = p.x;
    if (p.x > maxX) maxX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.y > maxY) maxY = p.y;
  }
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const box = { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
  const angles = headAngles(result.facialTransformationMatrixes?.[0]?.data) || { yaw: yawFromLandmarks(lm), pitch: null };
  const cats = result.faceBlendshapes?.[0]?.categories;
  const gaze = gazeFromBlendshapes(cats);
  const b = baseline || { yaw: 0, pitch: 0, gaze: { x: 0, y: 0 } };
  const turned = (angles.yaw !== null && Math.abs(angles.yaw - b.yaw) > limits.yaw)
    || (angles.pitch !== null && Math.abs(angles.pitch - (b.pitch ?? 0)) > limits.pitch);
  const looking = gaze ? Math.abs(gaze.x - (b.gaze?.x ?? 0)) > limits.gaze : false;
  const edge = minX < EDGE ? "left" : maxX > 1 - EDGE ? "right" : minY < EDGE ? "top" : maxY > 1 - EDGE ? "bottom" : null;
  return {
    faces, box, centered: Math.abs(cx - 0.5) < 0.22 && Math.abs(cy - 0.5) < 0.25, edge,
    tooSmall: box.w < 0.12, yaw: angles.yaw, pitch: angles.pitch, gaze, away: turned || looking,
    cause: turned && looking ? "head+eyes" : turned ? "head" : looking ? "eyes" : null, mouth: mouthOpen(cats),
  };
}

const median = (xs) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null;
};

/**
 * Neutral viewing position of THIS candidate: median head yaw/pitch and eye direction over the calibration period,
 * from frames with exactly one face. Medians ignore the odd glance. Needs a minimum number of usable frames.
 */
export class Calibration {
  constructor({ durationMs = 5000, minFrames = 6 } = {}) {
    this.durationMs = durationMs;
    this.minFrames = minFrames;
    this.samples = [];
    this.startedAt = null;
  }

  /** One analysed frame; returns {done, progress (0-1), baseline | null}. */
  add(tMs, faces) {
    if (this.startedAt === null) this.startedAt = tMs;
    if (faces?.faces === 1 && faces.yaw !== null && faces.yaw !== undefined) {
      this.samples.push({ yaw: faces.yaw, pitch: faces.pitch ?? 0, gx: faces.gaze?.x ?? 0, gy: faces.gaze?.y ?? 0 });
    }
    const progress = Math.min(1, (tMs - this.startedAt) / this.durationMs);
    if (progress < 1) return { done: false, progress, baseline: null };
    return { done: true, progress: 1, baseline: this.baseline() };
  }

  baseline() {
    if (this.samples.length < this.minFrames) return null; // not enough usable frames: absolute limits are used
    const m = (k) => median(this.samples.map((s) => s[k]));
    return { yaw: m("yaw"), pitch: m("pitch"), gaze: { x: m("gx"), y: m("gy") }, frames: this.samples.length };
  }
}

export const LIGHT = { obstructedMean: 18, obstructedStd: 6, lowMean: 45 };

/**
 * Conditions for SignalTracker. attention is judged only when exactly one face is visible and the light is good
 * enough: eye/head estimates in a dark picture are unreliable, so low light is noted instead of guessing gaze.
 */
export function observe(faces, light, { attention = false } = {}) {
  const obstructed = light ? (light.mean < LIGHT.obstructedMean || light.std < LIGHT.obstructedStd) : false;
  const dim = light ? !obstructed && light.mean < LIGHT.lowMean : null;
  return {
    camera_obstructed: obstructed,
    low_light: dim,
    face_absent: obstructed ? null : faces.faces === 0,
    face_partial: obstructed || faces.faces !== 1 ? null : !!faces.edge,
    multiple_faces: faces.faces >= 2,
    attention_away: attention && faces.faces === 1 && !dim ? faces.away : null,
  };
}

/** Facts that go with the conditions above (kept per episode by SignalTracker: max faces, gaze cause, edge). */
export function observeMeta(faces) {
  return { multiple_faces: faces.faces >= 2 ? faces.faces : null, attention_away: faces.cause || null,
    face_partial: faces.edge || null };
}

/** Setup-screen guidance from one analysed frame (simple, appearance-neutral wording). */
export function setupGuidance(faces, light) {
  if (light && (light.mean < LIGHT.obstructedMean || light.std < LIGHT.obstructedStd)) {
    return { ok: false, text: "The camera image is very dark or blocked. Check that nothing covers the camera." };
  }
  if (light && light.mean < LIGHT.lowMean) return { ok: false, text: "The room looks dark. Please add some light in front of you if you can." };
  if (!faces.faces) return { ok: false, text: "Please position your face near the center of the camera and ensure that the room is sufficiently lit." };
  if (faces.faces > 1) return { ok: false, text: "More than one face appears to be visible." };
  if (faces.edge) return { ok: false, text: "Part of your face is outside the picture. Please move toward the center." };
  if (faces.tooSmall) return { ok: false, text: "You seem far from the camera. Please move a little closer." };
  if (!faces.centered) return { ok: false, text: "Please move so your face is near the center of the picture." };
  return { ok: true, text: "Your face is visible and the lighting looks fine." };
}
