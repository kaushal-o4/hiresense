// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/monitoring/mediaSession.js
//
// FILE PURPOSE:
// Handles the camera for the interview and the pre-interview device checks.
//
// WHAT THIS FILE DOES:
// 1. CameraSession opens one camera stream only when the candidate asks, and watches for
//    disconnects.
// 2. testMicrophone() measures microphone level for a short test.
// 3. checkNetwork() calls /api/health to check the connection.
// 4. browserSupport() checks required browser features.
// 5. cameraErrorMessage() gives friendly error messages.
//
// HOW THIS FILE WORKS:
// Uses navigator.mediaDevices.getUserMedia; stop() releases all camera tracks.
//
// IMPORTANT FUNCTIONS:
//    - CameraSession()
//        Opens/stops the camera stream.
//    - testMicrophone()
//        Short microphone level test.
//    - checkNetwork()
//        Health check of the backend.
//    - browserSupport()
//        Feature support check.
//    Other helper functions: cameraErrorMessage
//
// INPUT:
// Browser media permissions.
//
// OUTPUT:
// A camera stream and device check results.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js
//    Used by: monitoring/useTypedMonitoring.js, pages/student/InterviewSetup.jsx,
//    pages/student/LiveVoiceInterview.jsx
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
// Camera handling for the interview: one stream at a time, opened only after the candidate asks for it, watched
// for disconnection and revoked permissions, and fully stopped at the end (or when monitoring is withdrawn).
// The microphone stays with MicRecorder, which opens it only while it is the candidate's turn.

import { apiUrl } from "../apiClient";

export function cameraErrorMessage(e) {
  if (e?.name === "NotAllowedError" || e?.name === "SecurityError") return "Camera permission was denied.";
  if (e?.name === "NotFoundError" || e?.name === "OverconstrainedError") return "No camera was found.";
  if (e?.name === "NotReadableError") return "The camera is being used by another app, or could not be started.";
  return `The camera could not be started (${e?.name || "error"}).`;
}

export class CameraSession {
  constructor() {
    this.stream = null;
    this.permStatus = { camera: null, microphone: null };
  }

  get active() {
    return !!this.stream && this.stream.getVideoTracks().some((t) => t.readyState === "live");
  }

  /** onLost(reason): "ended" (unplugged / stopped by the browser), "muted", "unmuted", "permission:<name>". */
  async start({ onLost } = {}) {
    if (this.active) return this.stream; // never open a second stream
    if (!navigator.mediaDevices?.getUserMedia) {
      const err = new Error("This browser cannot access a camera.");
      err.name = "NotSupportedError";
      throw err;
    }
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" }, audio: false,
    });
    this.onLost = onLost;
    for (const t of this.stream.getVideoTracks()) {
      t.onended = () => this.onLost?.("ended");
      t.onmute = () => this.onLost?.("muted");
      t.onunmute = () => this.onLost?.("unmuted");
    }
    this._watchPermissions();
    return this.stream;
  }

  async _watchPermissions() {
    if (!navigator.permissions?.query) return;
    for (const name of ["camera", "microphone"]) {
      try {
        const st = await navigator.permissions.query({ name });
        st.onchange = () => { if (st.state === "denied") this.onLost?.(`permission:${name}`); };
        this.permStatus[name] = st;
      } catch { /* not supported for this name in this browser */ }
    }
  }

  stop() {
    this.stream?.getTracks().forEach((t) => { t.onended = null; t.onmute = null; t.onunmute = null; t.stop(); });
    this.stream = null;
    for (const st of Object.values(this.permStatus)) if (st) st.onchange = null;
    this.onLost = null;
  }
}

/** Opens the microphone for ~1.5 s to check it works and picks up sound, then releases it. */
export async function testMicrophone(onLevel, ms = 1500) {
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch (e) {
    return { ok: false, error: e.name === "NotAllowedError" ? "Microphone permission was denied." : "No working microphone was found." };
  }
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const ctx = new Ctx();
  const an = ctx.createAnalyser();
  an.fftSize = 512;
  ctx.createMediaStreamSource(stream).connect(an);
  const buf = new Float32Array(512);
  let peak = 0;
  const t0 = performance.now();
  await new Promise((resolve) => {
    const step = () => {
      an.getFloatTimeDomainData(buf);
      let s = 0;
      for (const v of buf) s += v * v;
      const level = Math.sqrt(s / buf.length);
      peak = Math.max(peak, level);
      onLevel?.(level);
      if (performance.now() - t0 < ms) requestAnimationFrame(step); else resolve();
    };
    step();
  });
  stream.getTracks().forEach((t) => t.stop());
  ctx.close();
  return { ok: true, peak, heard: peak > 0.01 };
}

/** Round trip to this app's server (the AI, voice and transcription run there). */
export async function checkNetwork() {
  const t = performance.now();
  try {
    const r = await fetch(apiUrl("/api/health"), { cache: "no-store", credentials: "include" });
    return { ok: r.ok, ms: Math.round(performance.now() - t) };
  } catch {
    return { ok: false, ms: null };
  }
}

/**
 * What this browser supports for the interview and its monitoring. Each entry: {ok, label, detail}. `required`
 * entries block the start (camera access when the camera is required); the rest only limit optional checks.
 */
export function browserSupport(win = window) {
  const nav = win.navigator || {};
  const doc = win.document || {};
  const has = (x) => !!x;
  return {
    media: { ok: has(nav.mediaDevices?.getUserMedia), label: "Camera and microphone access", required: true },
    wasm: { ok: typeof win.WebAssembly === "object", label: "On-device face analysis (WebAssembly)" },
    audio: { ok: has(win.AudioContext || win.webkitAudioContext) && has(win.AudioWorkletNode), label: "Microphone level analysis" },
    visibility: { ok: "hidden" in doc && "onvisibilitychange" in doc, label: "Tab focus changes (Page Visibility)" },
    fullscreen: { ok: has(doc.documentElement?.requestFullscreen), label: "Full screen" },
    secure: { ok: win.isSecureContext !== false, label: "Secure connection (needed for camera access)", required: true },
  };
}
