// On-device face analysis with MediaPipe Face Landmarker (Apache-2.0). The WebAssembly runtime and the model are
// served by this app (public/mediapipe, public/models) - no third-party request, and frames never leave the
// browser. Runs a few times per second on a <video> element showing the camera.
import { analyzeFaces, brightness } from "./frameAnalysis";

let landmarkerPromise = null;

async function loadLandmarker() {
  if (!landmarkerPromise) {
    landmarkerPromise = (async () => {
      const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
      const make = (delegate) => FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: "/models/face_landmarker.task", delegate },
        runningMode: "VIDEO", numFaces: 3, outputFaceBlendshapes: true, outputFacialTransformationMatrixes: true,
        minFaceDetectionConfidence: 0.5, minFacePresenceConfidence: 0.5, minTrackingConfidence: 0.5,
      });
      try { return await make("GPU"); } catch { return make("CPU"); }
    })();
    landmarkerPromise.catch(() => { landmarkerPromise = null; });
  }
  return landmarkerPromise;
}

export class FaceMonitor {
  /** onFrame({faces, light, t}) every analysed frame; onError(message) if analysis stops working. */
  constructor({ fps = 4, onFrame, onError } = {}) {
    this.base = 1000 / fps;
    this.interval = this.base; // adaptive: grows (up to 3x) when analysis is slow on this device, so the AI
    this.cost = 0; // interviewer, voice and page stay responsive; shrinks back when the device has room again
    this.onFrame = onFrame;
    this.onError = onError;
    this.timer = null;
    this.video = null;
    this.canvas = document.createElement("canvas");
    this.canvas.width = 64;
    this.canvas.height = 48;
    this.ctx2d = this.canvas.getContext("2d", { willReadFrequently: true });
    this.failures = 0;
  }

  async start(video) {
    this.stop();
    this.video = video;
    this.landmarker = await loadLandmarker();
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
    let light = null;
    try {
      this.ctx2d.drawImage(v, 0, 0, 64, 48);
      light = brightness(this.ctx2d.getImageData(0, 0, 64, 48).data);
    } catch { /* frame not ready */ }
    try {
      const result = this.landmarker.detectForVideo(v, t);
      this.failures = 0;
      this._adapt(performance.now() - t);
      this.onFrame?.({ result, faces: analyzeFaces(result), light, t });
    } catch (e) {
      this.failures += 1;
      if (this.failures === 10) this.onError?.(`Face analysis stopped working (${e.message || e}).`);
    }
  }

  _adapt(ms) {
    this.cost = this.cost ? this.cost * 0.8 + ms * 0.2 : ms;
    if (this.cost > this.interval * 0.4) this.interval = Math.min(this.base * 3, this.interval * 1.5);
    else if (this.cost < this.interval * 0.15 && this.interval > this.base) this.interval = Math.max(this.base, this.interval / 1.25);
  }

  get fps() { return Math.round((1000 / this.interval) * 10) / 10; }

  stop() {
    this.running = false;
    clearTimeout(this.timer);
    this.timer = null;
    this.video = null;
  }
}

/** Can on-device analysis run here? Loads the model (cached afterwards). */
export async function faceAnalysisAvailable() {
  try {
    await loadLandmarker();
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message || String(e) };
  }
}
