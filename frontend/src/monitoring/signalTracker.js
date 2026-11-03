// Turns per-frame camera observations into neutral warnings and integrity events. Pure (no browser APIs) so the
// thresholds and false-positive handling can be unit-tested.
//
// Why so cautious: missing faces, second faces and "looking away" are often caused by lighting, camera position,
// glasses, disability, movement or simply thinking. So a condition must persist (grace period) before the student
// sees a warning, must last a minimum time before it is recorded, short dropouts do not end it (hysteresis), and
// each event carries a confidence = the share of analysed frames that actually showed the condition.

export const DEFAULT_THRESHOLDS = {
  // warnMs: persistent for this long before a warning is shown. minRecordMs: shorter episodes are not recorded.
  // endMs: the condition must be absent this long before the episode ends (brief detector dropouts are ignored).
  face_absent: { warnMs: 5000, minRecordMs: 4000, endMs: 1500 },
  multiple_faces: { warnMs: 3000, minRecordMs: 3000, endMs: 2000 },
  attention_away: { warnMs: 10000, minRecordMs: 8000, endMs: 1500 },
  low_light: { warnMs: 4000, minRecordMs: 10000, endMs: 3000 },
  camera_obstructed: { warnMs: 3000, minRecordMs: 4000, endMs: 1500 },
  face_partial: { warnMs: 8000, minRecordMs: 10000, endMs: 2000 },
};

/** Thresholds from the admin security settings (GET /api/monitoring/policy -> thresholds); missing values = defaults. */
export function thresholdsFrom(t) {
  if (!t) return DEFAULT_THRESHOLDS;
  const d = DEFAULT_THRESHOLDS;
  return {
    ...d,
    face_absent: { ...d.face_absent, warnMs: t.face_absent_warn_ms ?? d.face_absent.warnMs, minRecordMs: t.face_absent_record_ms ?? d.face_absent.minRecordMs },
    multiple_faces: { ...d.multiple_faces, warnMs: t.multiple_faces_warn_ms ?? d.multiple_faces.warnMs, minRecordMs: t.multiple_faces_record_ms ?? d.multiple_faces.minRecordMs },
    attention_away: { ...d.attention_away, warnMs: t.gaze_warn_ms ?? d.attention_away.warnMs, minRecordMs: t.gaze_record_ms ?? d.attention_away.minRecordMs },
  };
}

export const WARNINGS = {
  face_absent: "We cannot clearly detect your face. Please adjust your position or camera.",
  multiple_faces: "More than one face appears in the camera frame. Please ensure your interview setup follows the stated interview rules.",
  attention_away: "Please keep your attention on the interview screen. Brief natural movements are acceptable.",
  face_partial: "Part of your face is outside the camera frame. Please move toward the center.",
  low_light: "Camera visibility is temporarily low. Please check your lighting.",
  camera_obstructed: "The camera view seems blocked or very dark. Please check your camera.",
};

const MIN_WARN_AGREEMENT = 0.7; // share of frames in the episode so far that must agree before warning

export class SignalTracker {
  /** enabled: {face_absent, multiple_faces, attention_away, low_light, camera_obstructed} -> bool */
  constructor(enabled, thresholds = DEFAULT_THRESHOLDS) {
    this.enabled = enabled;
    this.th = thresholds;
    this.ep = {}; // condition -> {start, lastTrue, frames, trueFrames, warned}
  }

  /**
   * One analysed frame. obs[condition] is true / false, or null when it cannot be judged in this frame (e.g.
   * attention when no single face is visible) - null frames neither extend nor end an episode.
   * Returns {events: [...], warnings: [{type, message}], cleared: [type]}.
   */
  update(tMs, obs, meta = {}) {
    const out = { events: [], warnings: [], cleared: [] };
    for (const type of Object.keys(this.th)) {
      if (!this.enabled[type]) continue;
      const v = obs[type];
      if (v === null || v === undefined) continue;
      const th = this.th[type];
      let e = this.ep[type];
      if (v) {
        if (!e) e = this.ep[type] = { start: tMs, lastTrue: tMs, frames: 0, trueFrames: 0, warned: false, meta: {} };
        e.frames += 1;
        e.trueFrames += 1;
        e.lastTrue = tMs;
        this._meta(type, e, meta[type]);
        if (!e.warned && tMs - e.start >= th.warnMs && e.trueFrames / e.frames >= MIN_WARN_AGREEMENT) {
          e.warned = true;
          out.warnings.push({ type, message: WARNINGS[type] });
        }
      } else if (e) {
        e.frames += 1;
        if (tMs - e.lastTrue >= th.endMs) this._end(type, out);
      }
    }
    return out;
  }

  _end(type, out) {
    const e = this.ep[type];
    delete this.ep[type];
    const duration = e.lastTrue - e.start;
    if (e.warned) out.cleared.push(type);
    if (duration >= this.th[type].minRecordMs) {
      const ev = { event_type: type, t_ms: Math.round(e.start), duration_ms: Math.round(duration),
        confidence: Math.round((e.trueFrames / Math.max(1, e.frames)) * 1000) / 1000 };
      const details = this._details(type, e.meta);
      if (details) ev.details = details;
      out.events.push(ev);
    }
  }

  // per-episode facts: the largest number of faces seen, what turned away (head / eyes), which edge cut the face
  _meta(type, e, v) {
    if (v === null || v === undefined) return;
    if (type === "multiple_faces") e.meta.max_faces = Math.max(e.meta.max_faces || 0, v);
    else if (type === "attention_away") (e.meta.causes ||= new Set()).add(v);
    else if (type === "face_partial") e.meta.edge ||= v;
  }

  _details(type, m) {
    if (type === "multiple_faces" && m.max_faces) return { max_faces: m.max_faces };
    if (type === "face_partial" && m.edge) return { edge: m.edge };
    if (type === "attention_away" && m.causes?.size) {
      const c = m.causes;
      return { cause: c.has("head+eyes") || (c.has("head") && c.has("eyes")) ? "head+eyes" : c.has("head") ? "head" : "eyes" };
    }
    return null;
  }

  /** End every open episode (interview finished, monitoring stopped). */
  flush() {
    const out = { events: [], warnings: [], cleared: [] };
    Object.keys(this.ep).forEach((type) => this._end(type, out));
    return out;
  }
}

/**
 * Repeated gaze deviations: each recorded "attention_away" episode is counted; `count` of them inside `windowS`
 * seconds produce ONE "attention_repeated" event, then counting starts again (no event per frame or per glance).
 */
export class RepeatTracker {
  constructor({ count = 5, windowS = 120 } = {}) {
    this.count = count;
    this.windowMs = windowS * 1000;
    this.times = [];
  }

  /** An attention_away event was recorded; returns an attention_repeated event or null. */
  add(ev) {
    const t = ev.t_ms;
    this.times = this.times.filter((x) => t - x <= this.windowMs);
    this.times.push(t);
    if (this.times.length < this.count) return null;
    const out = { event_type: "attention_repeated", t_ms: Math.round(this.times[0]),
      duration_ms: Math.round(t + (ev.duration_ms || 0) - this.times[0]), confidence: 1,
      details: { count: this.times.length, window_s: Math.round(this.windowMs / 1000) } };
    this.times = [];
    return out;
  }
}

/** Browser focus (tab hidden / window blurred). Returns an event when focus comes back. */
export class FocusTracker {
  constructor(minMs = 500) { this.awaySince = null; this.minMs = minMs; }

  away(tMs) { if (this.awaySince === null) this.awaySince = tMs; }

  back(tMs) {
    if (this.awaySince === null) return null;
    const ev = { event_type: "focus_change", t_ms: Math.round(this.awaySince), duration_ms: Math.round(tMs - this.awaySince) };
    this.awaySince = null;
    return ev.duration_ms >= this.minMs ? ev : null; // sub-second blurs (permission prompts, clicks) are not recorded
  }
}
