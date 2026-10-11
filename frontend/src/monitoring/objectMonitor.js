// On-device detection of a phone or book/notes in the camera view, using MediaPipe Object Detector with
// EfficientDet-Lite0 (Apache-2.0, COCO classes). The model and WebAssembly runtime are served by this app
// (public/models, public/mediapipe) - frames never leave the browser and nothing about the person is analysed.
// Object detection is approximate (a dark wallet can look like a phone, a book on a shelf behind you counts), so an
// object must be seen in most frames for several seconds before anything is shown or recorded, and the server caps
// the severity: a reviewer decides what it means.
import { SignalTracker } from "./signalTracker";

// COCO label -> our condition. Laptops/monitors are not flagged: the interview itself runs on one.
export const OBJECT_CLASSES = { "cell phone": "phone_in_view", book: "notes_in_view" };
// Per-frame score limits, checked on real photos (scratch test, Oct 2026): a phone held clearly in front of the
// camera scored 0.41-0.74 and a book on a desk 0.57, while face portraits produced no detections at all. The
// limits are kept lowish because one frame proves little anyway: the tracker below only reports an object that
// is seen in most frames for several seconds.
export const OBJECT_MIN_SCORE = { phone_in_view: 0.35, notes_in_view: 0.45 };

// At ~1 analysed frame per second. warnMs/minRecordMs/endMs as in signalTracker.DEFAULT_THRESHOLDS.
export const OBJECT_THRESHOLDS = {
  phone_in_view: { warnMs: 3000, minRecordMs: 3000, endMs: 3000 },
  notes_in_view: { warnMs: 5000, minRecordMs: 5000, endMs: 3000 },
};

export const OBJECT_WARNINGS = {
  phone_in_view: "A phone appears to be visible. Please put it away for the interview.",
  notes_in_view: "A book or notes appear to be visible. Please keep study material out of view during the interview.",
};

/** ObjectDetectorResult -> {phone_in_view: bool, notes_in_view: bool} (only confident detections count). */
export function observeObjects(result, minScore = OBJECT_MIN_SCORE) {
  const out = { phone_in_view: false, notes_in_view: false };
  for (const d of result?.detections || []) {
    for (const c of d.categories || []) {
      const cond = OBJECT_CLASSES[c.categoryName];
      if (cond && c.score >= minScore[cond]) out[cond] = true;
    }
  }
  return out;
}

/** SignalTracker preconfigured for objects; its warnings carry the object messages. */
export class ObjectTracker {
  constructor(enabled = { phone_in_view: true, notes_in_view: true }) {
    this.inner = new SignalTracker(enabled, OBJECT_THRESHOLDS);
  }

  _msg(out) {
    out.warnings = out.warnings.map((w) => ({ ...w, message: OBJECT_WARNINGS[w.type] }));
    return out;
  }

  update(tMs, obs) { return this._msg(this.inner.update(tMs, obs)); }

  flush() { return this._msg(this.inner.flush()); }
}

let detectorPromise = null;

async function loadDetector() {
  if (!detectorPromise) {
    detectorPromise = (async () => {
      const { FilesetResolver, ObjectDetector } = await import("@mediapipe/tasks-vision");
      const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
      const make = (delegate) => ObjectDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: "/models/efficientdet_lite0.tflite", delegate },
        runningMode: "VIDEO", maxResults: 5, scoreThreshold: 0.35, categoryAllowlist: Object.keys(OBJECT_CLASSES),
      });
      try { return await make("GPU"); } catch { return make("CPU"); }
    })();
    detectorPromise.catch(() => { detectorPromise = null; });
  }
  return detectorPromise;
}

/** Runs the detector on a <video> about once a second and reports {objects, t} per analysed frame. */
export class ObjectMonitor {
  constructor({ fps = 1, onFrame, onError } = {}) {
    this.interval = 1000 / fps;
    this.onFrame = onFrame;
    this.onError = onError;
    this.timer = null;
    this.failures = 0;
  }

  async start(video) {
    this.stop();
    this.video = video;
    this.detector = await loadDetector();
    this.running = true;
    const tick = () => {
      if (!this.running) return;
      this._analyse();
      this.timer = setTimeout(tick, this.interval);
    };
    tick();
  }

  _analyse() {
    const v = this.video;
    if (!v || v.readyState < 2 || !v.videoWidth) return;
    const t = performance.now();
    try {
      const objects = observeObjects(this.detector.detectForVideo(v, t));
      this.failures = 0;
      this.onFrame?.({ objects, t });
    } catch (e) {
      this.failures += 1;
      if (this.failures === 10) this.onError?.(`Object detection stopped working (${e.message || e}).`);
    }
  }

  stop() {
    this.running = false;
    clearTimeout(this.timer);
    this.timer = null;
    this.video = null;
  }
}
