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

const MODEL = "/models/efficientdet_lite0.tflite";
const OPTIONS = { maxResults: 5, scoreThreshold: 0.35, categoryAllowlist: Object.keys(OBJECT_CLASSES) };
const FRAME_WIDTH = 320; // the model's input size: smaller frames are cheaper to copy to the worker

// Each detection takes ~70-85 ms (measured in the browser E2E). On the page's own thread that froze the 3D interviewer
// for 4-5 frames every second, so it runs in a Web Worker (public/mediapipe/object-worker.js). Browsers without
// workers + ImageBitmap use the same detector on the page thread.
function workerDetector() {
  return new Promise((resolve, reject) => {
    const w = new Worker("/mediapipe/object-worker.js");
    const pending = new Map();
    let next = 0;
    w.onmessage = ({ data: m }) => {
      if (m.type === "ready") {
        resolve({
          async detect(video, t) {
            const h = Math.round(FRAME_WIDTH * (video.videoHeight / video.videoWidth));
            const frame = await createImageBitmap(video, { resizeWidth: FRAME_WIDTH, resizeHeight: h, resizeQuality: "low" });
            const id = ++next;
            return new Promise((res, rej) => {
              const timer = setTimeout(() => { pending.delete(id); rej(new Error("object detection timed out")); }, 5000);
              pending.set(id, { res: (r) => { clearTimeout(timer); res(r); }, rej: (er) => { clearTimeout(timer); rej(er); } });
              w.postMessage({ type: "detect", id, frame, t }, [frame]);
            });
          },
        });
      } else if (m.type === "error") {
        w.terminate();
        reject(new Error(m.message));
      } else if (m.type === "result") {
        const p = pending.get(m.id);
        pending.delete(m.id);
        if (m.error) p?.rej(new Error(m.error));
        else p?.res({ detections: m.detections });
      }
    };
    w.onerror = (e) => { w.terminate(); reject(new Error(e.message || "object detection worker failed")); };
    w.postMessage({ type: "init", model: MODEL, options: OPTIONS });
  });
}

async function pageDetector() {
  const { FilesetResolver, ObjectDetector } = await import("@mediapipe/tasks-vision");
  const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
  const make = (delegate) => ObjectDetector.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: MODEL, delegate }, runningMode: "VIDEO", ...OPTIONS,
  });
  let d;
  try { d = await make("GPU"); } catch { d = await make("CPU"); }
  return { detect: async (video, t) => d.detectForVideo(video, t) };
}

let detectorPromise = null;

/** -> {detect(video, t): Promise<ObjectDetectorResult>} */
async function loadDetector() {
  if (!detectorPromise) {
    detectorPromise = (typeof Worker !== "undefined" && typeof createImageBitmap === "function"
      ? workerDetector().catch(() => pageDetector())
      : pageDetector());
    detectorPromise.catch(() => { detectorPromise = null; });
  }
  return detectorPromise;
}

/**
 * Load the detector and run one warm-up detection during the setup check. Measured in the browser E2E: loading
 * and the first detection (GPU shader compile) blocked the page for ~5 s right when the interview started, which
 * delayed the interviewer's first audio from ~1 s to ~6 s. Done here, the interview start stays instant.
 */
export async function preloadObjectDetector(video) {
  try {
    const d = await loadDetector();
    if (video && video.readyState < 2) { // camera just started: wait (max 3 s) for the first frame
      await new Promise((resolve) => {
        const t = setTimeout(resolve, 3000);
        video.addEventListener("loadeddata", () => { clearTimeout(t); resolve(); }, { once: true });
      });
    }
    if (video?.readyState >= 2 && video.videoWidth) await d.detect(video, performance.now());
    return true;
  } catch {
    return false;
  }
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
    const run = (this.run = (this.run || 0) + 1); // a stop() + start() must not leave the old loop running
    const tick = async () => {
      if (!this.running || run !== this.run) return;
      await this._analyse(); // one detection at a time: the next starts a full interval after this one ends
      if (this.running && run === this.run) this.timer = setTimeout(tick, this.interval);
    };
    tick();
  }

  async _analyse() {
    const v = this.video;
    if (!v || v.readyState < 2 || !v.videoWidth) return;
    const t = performance.now();
    try {
      const result = await this.detector.detect(v, t);
      if (!this.running) return;
      const objects = observeObjects(result);
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
