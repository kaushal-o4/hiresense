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

/** FaceLandmarkerResult -> {faces, box, centered, yaw, pitch, gaze, away} (for the first face). */
export function analyzeFaces(result, limits = ATTENTION_LIMITS) {
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
  const gaze = gazeFromBlendshapes(result.faceBlendshapes?.[0]?.categories);
  const turned = (angles.yaw !== null && Math.abs(angles.yaw) > limits.yaw)
    || (angles.pitch !== null && Math.abs(angles.pitch) > limits.pitch);
  const looking = gaze ? Math.abs(gaze.x) > limits.gaze : false;
  return {
    faces, box, centered: Math.abs(cx - 0.5) < 0.22 && Math.abs(cy - 0.5) < 0.25,
    tooSmall: box.w < 0.12, yaw: angles.yaw, pitch: angles.pitch, gaze, away: turned || looking,
  };
}

export const LIGHT = { obstructedMean: 18, obstructedStd: 6, lowMean: 45 };

/** Conditions for SignalTracker. attention is judged only when exactly one face is visible. */
export function observe(faces, light, { attention = false } = {}) {
  const obstructed = light ? (light.mean < LIGHT.obstructedMean || light.std < LIGHT.obstructedStd) : false;
  return {
    camera_obstructed: obstructed,
    low_light: light ? !obstructed && light.mean < LIGHT.lowMean : null,
    face_absent: obstructed ? null : faces.faces === 0,
    multiple_faces: faces.faces >= 2,
    attention_away: attention && faces.faces === 1 ? faces.away : null,
  };
}

/** Setup-screen guidance from one analysed frame (simple, appearance-neutral wording). */
export function setupGuidance(faces, light) {
  if (light && (light.mean < LIGHT.obstructedMean || light.std < LIGHT.obstructedStd)) {
    return { ok: false, text: "The camera image is very dark or blocked. Check that nothing covers the camera." };
  }
  if (light && light.mean < LIGHT.lowMean) return { ok: false, text: "The room looks dark. Please add some light in front of you if you can." };
  if (!faces.faces) return { ok: false, text: "Please position your face near the center of the camera and ensure that the room is sufficiently lit." };
  if (faces.faces > 1) return { ok: false, text: "More than one face appears to be visible." };
  if (faces.tooSmall) return { ok: false, text: "You seem far from the camera. Please move a little closer." };
  if (!faces.centered) return { ok: false, text: "Please move so your face is near the center of the picture." };
  return { ok: true, text: "Your face is visible and the lighting looks fine." };
}
