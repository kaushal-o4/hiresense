// Runs the monitoring the candidate agreed to, and nothing else, for one interview. Stops completely on stop().
import { EventReporter } from "./eventReporter";
import { FaceMonitor } from "./faceMonitor";
import { observe } from "./frameAnalysis";
import { FocusTracker, SignalTracker } from "./signalTracker";

export class InterviewMonitor {
  /**
   * features: consented {camera, face_presence, multiple_faces, attention, focus_changes}
   * onStatus({analysis: "starting"|"running"|"unavailable"|"stopped", faces, light}), onWarning({type, message} | {clear: type})
   */
  constructor({ sessionId, features, t0, onStatus, onWarning }) {
    this.features = features;
    this.t0 = t0;
    this.onStatus = onStatus;
    this.onWarning = onWarning;
    this.reporter = new EventReporter(sessionId);
    this.tracker = new SignalTracker({
      face_absent: !!features.face_presence, camera_obstructed: !!features.face_presence, low_light: !!features.face_presence,
      multiple_faces: !!features.multiple_faces, attention_away: !!features.attention,
    });
    this.focus = new FocusTracker();
    this.face = null;
    this.lostAt = null;
    this.lastStatus = 0;
    this._vis = () => (document.hidden ? this.focus.away(this.now()) : this._back());
    this._blur = () => this.focus.away(this.now());
    this._focus = () => this._back();
  }

  now() { return performance.now() - this.t0; }

  _back() { this.reporter.add(this.focus.back(this.now())); }

  _apply(out) {
    out.events.forEach((e) => this.reporter.add(e));
    out.warnings.forEach((w) => this.onWarning?.(w));
    out.cleared.forEach((type) => this.onWarning?.({ clear: type }));
  }

  async start(video) {
    if (this.features.focus_changes) {
      document.addEventListener("visibilitychange", this._vis);
      window.addEventListener("blur", this._blur);
      window.addEventListener("focus", this._focus);
    }
    const cameraFeatures = this.features.face_presence || this.features.multiple_faces || this.features.attention;
    if (!this.features.camera || !cameraFeatures || !video) { this.onStatus?.({ analysis: "off" }); return; }
    this.onStatus?.({ analysis: "starting" });
    this.face = new FaceMonitor({
      fps: 4,
      onFrame: ({ faces, light, t }) => {
        this._apply(this.tracker.update(t - this.t0, observe(faces, light, { attention: !!this.features.attention })));
        if (t - this.lastStatus > 500) { // UI status twice a second is plenty
          this.lastStatus = t;
          this.onStatus?.({ analysis: "running", faces: faces.faces, centered: faces.centered, light });
        }
      },
      onError: () => {
        this.reporter.add({ event_type: "monitoring_interrupted", t_ms: Math.round(this.now()) });
        this.onStatus?.({ analysis: "unavailable" });
      },
    });
    try {
      await this.face.start(video);
    } catch {
      this.face = null;
      this.reporter.add({ event_type: "monitoring_unavailable", t_ms: Math.round(this.now()) });
      this.onStatus?.({ analysis: "unavailable" });
    }
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
    this.face?.stop();
    this.face = null;
    document.removeEventListener("visibilitychange", this._vis);
    window.removeEventListener("blur", this._blur);
    window.removeEventListener("focus", this._focus);
    this._apply(this.tracker.flush());
    this._back();
    this.onStatus?.({ analysis: "stopped" });
    await this.reporter.close();
  }
}
