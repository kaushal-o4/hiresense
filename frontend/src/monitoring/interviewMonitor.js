// Runs the monitoring the candidate agreed to, and nothing else, for one interview. Stops completely on stop().
// Every detector reports through ONE EventReporter (standard event records, client ids, batching), and every
// candidate-facing reminder goes through one rate-limited warning function.
import { ConnectionTracker, SpeechAttribution } from "./audioMonitor";
import { EventReporter } from "./eventReporter";
import { FaceMonitor } from "./faceMonitor";
import { AttentionMeter, STATE, classifyFrame } from "./attentionMeter";
import { ATTENTION_LIMITS, Calibration, analyzeFaces, observe, observeMeta } from "./frameAnalysis";
import { ObjectMonitor, ObjectTracker } from "./objectMonitor";
import { PasteGuard } from "./pasteGuard";
import { ScreenGuard } from "./screenGuard";
import { FocusTracker, RepeatTracker, SignalTracker, thresholdsFrom } from "./signalTracker";

export const FOCUS_WARNING = "You have left the interview window. Please return to continue.";

export class InterviewMonitor {
  /**
   * features: consented {camera, face_presence, multiple_faces, attention, focus_changes, paste, screen, objects, audio}
   * policy: GET /api/monitoring/policy (thresholds, warning_cooldown_s, pause_on_face_absent_s) - optional
   * baseline: neutral head/eye position from the setup screen's calibration (else calibrated here)
   * onStatus({analysis: "starting"|"calibrating"|"running"|"unavailable"|"stopped"|"off", faces, light, gaze, online, fps})
   * onWarning({type, message} | {clear: type}); onPauseRequest(reason) when the admin pause rule applies.
   */
  constructor({ sessionId, features, t0, policy = null, baseline = null, onStatus, onWarning, onPauseRequest }) {
    this.features = features;
    this.t0 = t0;
    this.policy = policy;
    this.th = policy?.thresholds || {};
    this.onStatus = onStatus;
    this.onWarningRaw = onWarning;
    this.onPauseRequest = onPauseRequest;
    this.cooldownMs = (policy?.warning_cooldown_s ?? 30) * 1000;
    this.lastWarn = {};
    this.conn = new ConnectionTracker();
    this.reporter = new EventReporter(sessionId, { onConnection: (ok, reason) => this._connection(ok, reason) });
    this.tracker = new SignalTracker({
      face_absent: !!features.face_presence, camera_obstructed: !!features.face_presence, low_light: !!features.face_presence,
      face_partial: !!features.face_presence, multiple_faces: !!features.multiple_faces, attention_away: !!features.attention,
    }, thresholdsFrom(policy?.thresholds));
    this.repeats = features.attention ? new RepeatTracker({ count: this.th.gaze_repeat_count ?? 5, windowS: this.th.gaze_repeat_window_s ?? 120 }) : null;
    this.limits = { yaw: this.th.gaze_yaw_deg ?? ATTENTION_LIMITS.yaw, pitch: this.th.gaze_pitch_deg ?? ATTENTION_LIMITS.pitch,
      gaze: this.th.gaze_eye ?? ATTENTION_LIMITS.gaze };
    this.baseline = baseline;
    // Time-based "visual attention" estimate (attentionMeter.js); only with the consented gaze feature.
    this.meter = features.attention ? new AttentionMeter({
      windowMs: (this.th.attention_window_s ?? 30) * 1000, confirmMs: this.th.attention_confirm_ms ?? 1000,
      maxGapMs: this.th.attention_max_gap_ms ?? 2500 }) : null;
    this.attnTimer = null;
    this.attnTicks = 0;
    this.calibration = features.attention && !baseline ? new Calibration({ durationMs: this.th.calibration_ms ?? 5000 }) : null;
    this.speech = features.audio ? new SpeechAttribution({ minSpeechMs: this.th.audio_min_speech_ms ?? 4000 }) : null;
    this.focus = new FocusTracker(this.th.focus_record_ms ?? 500);
    this.objTracker = features.objects ? new ObjectTracker() : null;
    this.objects = null;
    this.paste = null;
    this.screen = null;
    this.face = null;
    this.lostAt = null;
    this.faceAbsentSince = null;
    this.pauseRequested = false;
    this.pausedAt = null;
    this.lastStatus = 0;
    this.status = { analysis: "off", online: true };
    this.started = false;
    this._vis = () => (document.hidden ? this.focus.away(this.now()) : this._back());
    this._blur = () => this.focus.away(this.now());
    this._focus = () => this._back();
    this._offline = () => this._connection(false, "offline");
    this._online = () => this._connection(true);
  }

  now() { return performance.now() - this.t0; }

  /** All candidate reminders: the same reminder is not repeated within the configured cooldown. */
  onWarning(w) {
    if (!w) return;
    if (!w.clear) {
      const t = performance.now();
      if (this.lastWarn[w.type] && t - this.lastWarn[w.type] < this.cooldownMs) return;
      this.lastWarn[w.type] = t;
    }
    this.onWarningRaw?.(w);
  }

  _setStatus(patch) {
    this.status = { ...this.status, ...patch };
    this.onStatus?.(this.status);
  }

  _back() {
    const ev = this.focus.back(this.now());
    if (ev) {
      this.reporter.add(ev);
      this.onWarning({ type: "focus_change", message: FOCUS_WARNING });
      clearTimeout(this.focusClear); // a one-off notice: it clears itself instead of covering other reminders
      this.focusClear = setTimeout(() => this.onWarningRaw?.({ clear: "focus_change" }), 8000);
    }
  }

  _connection(ok, reason) {
    if (!ok) {
      this.conn.down(this.now(), reason);
      if (this.status.online) this._setStatus({ online: false });
      return;
    }
    const ev = this.conn.up(this.now());
    if (ev) this.reporter.add(ev);
    if (!this.status.online) this._setStatus({ online: true });
  }

  _apply(out) {
    out.events.forEach((e) => {
      this.reporter.add(e);
      if (e.event_type === "attention_away" && this.repeats) this.reporter.add(this.repeats.add(e));
    });
    out.warnings.forEach((w) => this.onWarning(w));
    out.cleared.forEach((type) => this.onWarning({ clear: type }));
  }

  async start(video) {
    if (this.started) return; // never two monitoring loops for one interview
    this.started = true;
    const anyFeature = Object.values(this.features).some(Boolean);
    if (anyFeature) {
      window.addEventListener("offline", this._offline);
      window.addEventListener("online", this._online);
    }
    if (this.features.focus_changes) {
      document.addEventListener("visibilitychange", this._vis);
      window.addEventListener("blur", this._blur);
      window.addEventListener("focus", this._focus);
    }
    const report = (e) => this.reporter.add(e);
    if (this.features.paste) {
      this.paste = new PasteGuard({ now: () => this.now(), onEvent: report, onWarning: (w) => this.onWarning(w) });
      this.paste.attach(document);
    }
    if (this.features.screen) {
      // fullscreen itself was requested by the setup screen's Start click (browsers require a user gesture)
      this.screen = new ScreenGuard({ now: () => this.now(), onEvent: report, onWarning: (w) => this.onWarning(w) });
      this.screen.start();
    }
    if (this.features.camera && this.features.objects && video) this._startObjects(video);
    const cameraFeatures = this.features.face_presence || this.features.multiple_faces || this.features.attention || this.features.audio;
    if (!this.features.camera || !cameraFeatures || !video) { this._setStatus({ analysis: "off" }); return; }
    this._setStatus({ analysis: "starting", recalibrate: this.meter ? () => this.recalibrate() : null });
    if (this.meter) this.attnTimer = setInterval(() => this._attentionTick(), 1000);
    this.face = new FaceMonitor({
      fps: this.th.frame_rate ?? 2, // plenty for multi-second grace periods, and leaves CPU for the voice and AI models
      onFrame: ({ result, light, t }) => this._frame(result, light, t),
      onError: () => {
        this.reporter.add({ event_type: "monitoring_interrupted", t_ms: Math.round(this.now()) });
        this._setStatus({ analysis: "unavailable" });
        this.meter?.add(this.now(), STATE.UNAVAILABLE);
      },
    });
    try {
      await this.face.start(video);
    } catch {
      this.face = null;
      this.reporter.add({ event_type: "monitoring_unavailable", t_ms: Math.round(this.now()) });
      this._setStatus({ analysis: "unavailable" });
      this.meter?.add(this.now(), STATE.UNAVAILABLE);
    }
  }

  /** The candidate moved or the light changed: measure the neutral position again (these frames are not counted). */
  recalibrate() {
    if (!this.features.attention || this.calibration) return;
    this.baseline = null;
    this.calibration = new Calibration({ durationMs: this.th.calibration_ms ?? 5000 });
  }

  // Once a second: keeps the live figure honest when camera frames stop, and sends the totals every 10 s.
  _attentionTick() {
    const t = this.now();
    if (this.status.analysis === "unavailable") this.meter.add(t, STATE.UNAVAILABLE);
    this._setAttention(t);
    if (++this.attnTicks % 10 === 0) this._sendAttention();
  }

  _setAttention(t) {
    const a = this.meter.rolling(t);
    const prev = this.status.attention;
    if (prev && prev.pct === a.pct && prev.collecting === a.collecting && prev.state === a.state && prev.coveragePct === a.coveragePct
      && prev.calibrated === !!this.baseline && prev.calibrating === !!this.calibration) return; // nothing to re-render
    this._setStatus({ attention: { ...a, calibrated: !!this.baseline, calibrating: !!this.calibration } });
  }

  _sendAttention() {
    if (this.meter) return this.reporter.sendAttention({ ...this.meter.snapshot(), calibrated: !!this.baseline });
  }

  _frame(result, light, t) {
    const tMs = t - this.t0;
    const faces = analyzeFaces(result, this.limits, this.baseline);
    let gaze = this.features.attention ? (this.baseline ? "active" : "uncalibrated") : "off";
    if (this.calibration) {
      const c = this.calibration.add(tMs, faces);
      gaze = "calibrating";
      if (c.done) {
        this.baseline = c.baseline; // null: too few usable frames - absolute limits are used instead
        this.calibration = null;
        gaze = this.baseline ? "active" : "uncalibrated";
      }
    }
    const obs = observe(faces, light, { attention: !!this.features.attention && gaze !== "calibrating" });
    if (this.meter) {
      this.meter.add(tMs, classifyFrame({ faces, obstructed: !!obs.camera_obstructed, dim: !!obs.low_light,
        calibrating: gaze === "calibrating" }));
    }
    if (import.meta.env?.DEV) { // test hook for tests_e2e (dev server only): what the monitor currently sees
      window.__hsMonitor = { baseline: this.baseline, gaze, yaw: faces.yaw, pitch: faces.pitch, faces: faces.faces,
        edge: faces.edge, away: faces.away, light, obs, fps: this.face?.fps };
    }
    this._apply(this.tracker.update(tMs, obs, observeMeta(faces)));
    this.speech?.face(tMs, faces.faces, faces.mouth);
    if (this.meter && t - this.lastStatus > 500) this._setAttention(tMs);
    this._pauseRule(tMs, obs.face_absent);
    if (t - this.lastStatus > 500) { // UI status twice a second is plenty
      this.lastStatus = t;
      this._setStatus({ analysis: "running", faces: faces.faces, centered: faces.centered, edge: faces.edge, light, gaze,
        fps: this.face?.fps });
    }
  }

  // Admin rule (off by default): pause the interview when no face has been visible for N seconds. The candidate
  // resumes it; nothing is ended or failed automatically.
  _pauseRule(tMs, absent) {
    const limit = (this.policy?.pause_on_face_absent_s || 0) * 1000;
    if (!limit || !this.features.face_presence) return;
    if (absent === true) {
      if (this.faceAbsentSince === null) this.faceAbsentSince = tMs;
      if (!this.pauseRequested && tMs - this.faceAbsentSince >= limit) {
        this.pauseRequested = true;
        this.onPauseRequest?.("face_absent");
      }
    } else if (absent === false) {
      this.faceAbsentSince = null;
      this.pauseRequested = false;
    }
  }

  /** Phone / notes detection: 1 frame per second at most (the voice models need the CPU more). */
  _startObjects(video) {
    this.objects = new ObjectMonitor({
      fps: 1,
      onFrame: ({ objects, t }) => this._apply(this.objTracker.update(t - this.t0, objects)),
      onError: () => { this.objects?.stop(); this.objects = null; }, // face monitoring carries on
    });
    this.objects.start(video).catch(() => { this.objects = null; }); // model unavailable: just skip this check
  }

  // ---- microphone (the stream MicRecorder opens for each answer; nothing is recorded for these checks)
  audioStart() { this.speech?.begin(); }

  audioLevel(level, dtMs) { this.reporter.add(this.speech?.audio(level, dtMs, this.now()) || null); }

  audioStop() { this.reporter.add(this.speech?.end() || null); }

  /** The microphone failed during the interview: reason "ended" | "not_found" | "not_readable". */
  micLost(reason) {
    this.reporter.add({ event_type: "microphone_disconnected", t_ms: Math.round(this.now()), details: { reason } });
  }

  /** The interview was paused (reason "manual" | "face_absent"); resumed() records how long. */
  paused(reason) {
    if (this.pausedAt !== null) return;
    this.pausedAt = this.now();
    this.pauseReason = reason;
    this.meter?.setPaused(this.pausedAt, true);
  }

  resumed() {
    if (this.pausedAt === null) return;
    this.meter?.setPaused(this.now(), false);
    this.reporter.add({ event_type: "interview_paused", t_ms: Math.round(this.pausedAt),
      duration_ms: Math.round(this.now() - this.pausedAt), details: { reason: this.pauseReason } });
    this.pausedAt = null;
  }

  /** From CameraSession: the camera stream was interrupted or a permission was revoked. */
  cameraLost(reason) {
    const t = Math.round(this.now());
    if (reason === "muted") { this.lostAt = t; return; }
    if (reason === "unmuted" && this.lostAt !== null) {
      this.reporter.add({ event_type: "camera_interrupted", t_ms: this.lostAt, duration_ms: t - this.lostAt });
      this.lostAt = null;
      return;
    }
    if (reason === "ended") this.reporter.add({ event_type: "camera_interrupted", t_ms: t });
    if (reason.startsWith("permission:")) this.reporter.add({ event_type: "permission_revoked", t_ms: t });
  }

  async stop() {
    clearTimeout(this.focusClear);
    clearInterval(this.attnTimer);
    this.face?.stop();
    this.face = null;
    this.objects?.stop();
    this.objects = null;
    if (this.objTracker) this._apply(this.objTracker.flush());
    this.paste?.detach();
    this.paste = null;
    await this.screen?.stop(); // records an open "left full screen" episode and leaves full screen
    this.screen = null;
    document.removeEventListener("visibilitychange", this._vis);
    window.removeEventListener("blur", this._blur);
    window.removeEventListener("focus", this._focus);
    window.removeEventListener("offline", this._offline);
    window.removeEventListener("online", this._online);
    this._apply(this.tracker.flush());
    this.audioStop();
    this.resumed();
    const ev = this.focus.back(this.now());
    if (ev) this.reporter.add(ev);
    if (!this.conn.online) this.reporter.add(this.conn.up(this.now()));
    this._setStatus({ analysis: "stopped" });
    if (this.meter) {
      this.meter.finish(this.now());
      await this._sendAttention(); // the final totals; an earlier failure is covered because totals are cumulative
    }
    await this.reporter.close();
  }
}
