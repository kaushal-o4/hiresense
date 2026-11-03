// Possible additional voice during the candidate's answer - on-device, approximate, pure (unit-tested).
//
// Only the audio levels of the microphone stream that is ALREADY open for the answer are used (MicRecorder's
// per-chunk level); nothing is recorded or sent for this check. The interviewer's voice is excluded by design: the
// microphone is closed while the interviewer speaks, and echo cancellation removes speaker playback.
//
// One microphone cannot tell voices apart reliably, so the check is audio-visual: sustained voiced audio while the
// single visible face's mouth does not appear to move (MediaPipe jawOpen blendshape, sampled with the face analysis)
// suggests the voice may come from someone else. When attribution is impossible (no face / several faces / too few
// face frames) nothing is reported - an unattributable voice is not evidence of anything. Accent, speech style,
// emotion or disability are never analysed; the server keeps this event at "low" at most.

export const AUDIO_DEFAULTS = {
  level: 0.02, // RMS above this = voiced (MicRecorder's own speech threshold is 0.012; a bit higher ignores hiss)
  minSpeechMs: 4000, // voiced audio needed in one episode before attribution is judged
  minFaceFrames: 6, // face frames (during voiced audio) needed to judge the mouth
  moving: 0.06, // jawOpen above this, or a change of more than `delta` between frames, = mouth moving
  delta: 0.03,
  maxMovingShare: 0.2, // if the mouth moved in fewer than 20% of voiced frames -> possible additional voice
  gapMs: 1500, // silence this long ends a voiced stretch
};

export class SpeechAttribution {
  constructor(opts = {}) {
    this.o = { ...AUDIO_DEFAULTS, ...opts };
    this.active = false;
    this._reset();
  }

  _reset() {
    this.voicedMs = 0;
    this.start = null;
    this.lastVoiceT = null;
    this.frames = 0;
    this.movingFrames = 0;
    this.prevMouth = null;
  }

  /** The microphone opened for an answer. */
  begin() { this.active = true; this._reset(); }

  /** Microphone chunk: RMS level, chunk length and interview-relative time (ms). */
  audio(level, dtMs, tMs) {
    if (!this.active) return null;
    if (level > this.o.level) {
      if (this.start === null) this.start = tMs;
      this.voicedMs += dtMs;
      this.lastVoiceT = tMs;
    } else if (this.lastVoiceT !== null && tMs - this.lastVoiceT > this.o.gapMs) {
      return this._judge(); // a voiced stretch ended
    }
    return null;
  }

  /** Face frame: number of faces and the first face's mouth opening (null if unknown). */
  face(tMs, faces, mouth) {
    if (!this.active || this.lastVoiceT === null || tMs - this.lastVoiceT > 300) return; // only while voice is heard
    if (faces !== 1 || mouth === null || mouth === undefined) return; // cannot attribute: not counted
    this.frames += 1;
    const moved = mouth > this.o.moving || (this.prevMouth !== null && Math.abs(mouth - this.prevMouth) > this.o.delta);
    if (moved) this.movingFrames += 1;
    this.prevMouth = mouth;
  }

  _judge() {
    const enough = this.voicedMs >= this.o.minSpeechMs && this.frames >= this.o.minFaceFrames;
    const share = this.frames ? this.movingFrames / this.frames : 1;
    const ev = enough && share < this.o.maxMovingShare
      ? { event_type: "background_speech", t_ms: Math.round(this.start), duration_ms: Math.round(this.lastVoiceT - this.start),
        confidence: Math.round((1 - share) * 1000) / 1000 }
      : null;
    this._reset();
    return ev;
  }

  /** The answer ended (microphone closed): judge the last stretch. */
  end() {
    if (!this.active) return null;
    const ev = this.lastVoiceT !== null ? this._judge() : null;
    this.active = false;
    return ev;
  }
}

/** Network interruptions: one event per outage with its duration (outages under minMs are not recorded). */
export class ConnectionTracker {
  constructor(minMs = 2000) { this.downAt = null; this.reason = null; this.minMs = minMs; }

  get online() { return this.downAt === null; }

  down(tMs, reason = "offline") { if (this.downAt === null) { this.downAt = tMs; this.reason = reason; } }

  up(tMs) {
    if (this.downAt === null) return null;
    const ev = { event_type: "network_interruption", t_ms: Math.round(this.downAt), duration_ms: Math.round(tMs - this.downAt),
      details: { reason: this.reason } };
    this.downAt = null;
    return ev.duration_ms >= this.minMs ? ev : null;
  }
}
