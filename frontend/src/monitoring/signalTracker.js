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
};

export const WARNINGS = {
  face_absent: "Your face is not clearly visible. Please adjust your camera.",
  multiple_faces: "More than one face appears to be visible. Please ensure your interview setup meets the assessment requirements.",
  attention_away: "Your attention appears to have shifted away from the screen. Please return when you are ready.",
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
  update(tMs, obs) {
    const out = { events: [], warnings: [], cleared: [] };
    for (const type of Object.keys(this.th)) {
      if (!this.enabled[type]) continue;
      const v = obs[type];
      if (v === null || v === undefined) continue;
      const th = this.th[type];
      let e = this.ep[type];
      if (v) {
        if (!e) e = this.ep[type] = { start: tMs, lastTrue: tMs, frames: 0, trueFrames: 0, warned: false };
        e.frames += 1;
        e.trueFrames += 1;
        e.lastTrue = tMs;
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
      out.events.push({ event_type: type, t_ms: Math.round(e.start), duration_ms: Math.round(duration),
        confidence: Math.round((e.trueFrames / Math.max(1, e.frames)) * 1000) / 1000 });
    }
  }

  /** End every open episode (interview finished, monitoring stopped). */
  flush() {
    const out = { events: [], warnings: [], cleared: [] };
    Object.keys(this.ep).forEach((type) => this._end(type, out));
    return out;
  }
}

/** Browser focus (tab hidden / window blurred). Returns an event when focus comes back. */
export class FocusTracker {
  constructor() { this.awaySince = null; }

  away(tMs) { if (this.awaySince === null) this.awaySince = tMs; }

  back(tMs) {
    if (this.awaySince === null) return null;
    const ev = { event_type: "focus_change", t_ms: Math.round(this.awaySince), duration_ms: Math.round(tMs - this.awaySince) };
    this.awaySince = null;
    return ev.duration_ms >= 500 ? ev : null; // sub-second blurs (permission prompts, clicks) are not recorded
  }
}
