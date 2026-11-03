// Phone / notes detection (MediaPipe Object Detector, EfficientDet-Lite0) in a Web Worker, so the ~70-85 ms each
// detection takes no longer freezes the page (it dropped 4-5 frames of the 3D interviewer every second).
// A classic worker on purpose: MediaPipe's WebAssembly loader sets a global that module workers never see.
// vision_bundle.js is a copy of node_modules/@mediapipe/tasks-vision/vision_bundle.js - update it together with
// ./wasm when the package is upgraded. Used by src/monitoring/objectMonitor.js.
/* global Vision */
importScripts("/mediapipe/vision_bundle.js");

let detector = null;

self.onmessage = async (e) => {
  const m = e.data;
  if (m.type === "init") {
    try {
      const fileset = await Vision.FilesetResolver.forVisionTasks("/mediapipe/wasm");
      const make = (delegate) => Vision.ObjectDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: m.model, delegate }, runningMode: "VIDEO", ...m.options,
      });
      try { detector = await make("GPU"); } catch { detector = await make("CPU"); }
      self.postMessage({ type: "ready" });
    } catch (err) {
      self.postMessage({ type: "error", message: String((err && err.message) || err) });
    }
    return;
  }
  if (m.type === "detect") {
    try {
      const r = detector.detectForVideo(m.frame, m.t);
      self.postMessage({ type: "result", id: m.id, detections: r.detections });
    } catch (err) {
      self.postMessage({ type: "result", id: m.id, error: String((err && err.message) || err) });
    } finally {
      m.frame.close();
    }
  }
};
