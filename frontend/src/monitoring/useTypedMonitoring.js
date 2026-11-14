// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/monitoring/useTypedMonitoring.js
//
// FILE PURPOSE:
// React hook that runs consent-based monitoring on the typed (text) interview page.
//
// WHAT THIS FILE DOES:
// 1. Waits until the setup screen calls begin with the consented features.
// 2. Starts the camera and an InterviewMonitor.
// 3. Keeps status, warnings and camera state for the page.
// 4. Stops monitoring, and on withdrawal calls POST /student/interviews/{id}/monitoring/withdraw.
//
// HOW THIS FILE WORKS:
// Uses refs for the camera, monitor and policy, and React state for UI values; reuses the same
// detectors as the voice room.
//
// IMPORTANT FUNCTIONS:
//    - useTypedMonitoring()
//        Hook returning monitoring state and begin/stop controls.
//
// INPUT:
// Interview session id; setup choices.
//
// OUTPUT:
// Monitoring state for InterviewSession.jsx.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: apiClient.js, monitoring/interviewMonitor.js, monitoring/mediaSession.js
//    Used by: pages/student/InterviewSession.jsx
//
// IMPORTANT DEPENDENCIES:
//    react
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
import { useCallback, useEffect, useRef, useState } from "react";
import { post } from "../apiClient";
import { InterviewMonitor } from "./interviewMonitor";
import { CameraSession } from "./mediaSession";

/**
 * Consent-gated monitoring for the typed interview page (the voice room has its own copy of this wiring).
 * Same detectors, same event engine (InterviewMonitor -> EventReporter), same server checks; only what the
 * candidate ticked at setup runs. Nothing starts before `begin` is called by the setup screen.
 */
export function useTypedMonitoring(sessionId) {
  const camera = useRef(null);
  if (!camera.current) camera.current = new CameraSession();
  const monitor = useRef(null);
  const video = useRef(null);
  const stream = useRef(null);
  const t0 = useRef(performance.now());
  const policy = useRef(null);
  const baseline = useRef(null);
  const [features, setFeatures] = useState(null); // null = setup not done yet
  const [status, setStatus] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [camOn, setCamOn] = useState(false);
  const [camLost, setCamLost] = useState(false);

  const warning = warnings.find((w) => w.type === "fullscreen_exit") || warnings[warnings.length - 1] || null;
  const onWarning = useCallback((w) => setWarnings((list) => (w.clear ? list.filter((x) => x.type !== w.clear)
    : [...list.filter((x) => x.type !== w.type), w])), []);

  const stop = useCallback(async ({ withdraw = false } = {}) => {
    const m = monitor.current;
    monitor.current = null;
    camera.current.stop();
    stream.current = null;
    setCamOn(false);
    setWarnings([]);
    if (m) await m.stop(); // pending events are sent
    if (withdraw) {
      setFeatures((f) => (f ? { ...f, withdrawn: true } : f));
      try { await post(`/student/interviews/${sessionId}/monitoring/withdraw?t_ms=${Math.round(performance.now() - t0.current)}`); } catch { /* best effort */ }
    }
  }, [sessionId]);

  // called by InterviewSetup after the consent was stored
  const begin = useCallback(({ features: f, policy: pol, baseline: b, elapsedMs = 0 }) => {
    t0.current = performance.now() - elapsedMs; // the server's interview clock continues across reloads
    policy.current = pol || null;
    baseline.current = b || null;
    if (f.camera && camera.current.active) {
      stream.current = camera.current.stream;
      camera.current.onLost = (reason) => {
        monitor.current?.cameraLost(reason);
        if (reason === "ended" || reason.startsWith("permission:camera")) {
          setCamOn(false);
          setCamLost(true);
          setWarnings((l) => [...l.filter((x) => x.type !== "camera"), { type: "camera",
            message: "The camera stopped (disconnected or permission changed). Your interview continues; camera monitoring is paused." }]);
        }
      };
      setCamOn(true);
    }
    setFeatures(f);
  }, []);

  // start the consented detectors once the self-view shows the stream
  useEffect(() => {
    if (!features || features.withdrawn || monitor.current) return;
    if (camOn && video.current) video.current.srcObject = stream.current;
    const needsVideo = features.camera;
    if (needsVideo && !(camOn && video.current)) return;
    if (!needsVideo && !features.focus_changes && !features.paste && !features.screen) return;
    const m = new InterviewMonitor({ sessionId, features, t0: t0.current, policy: policy.current, baseline: baseline.current,
      onStatus: setStatus, onWarning });
    monitor.current = m;
    m.start(needsVideo ? video.current : null);
  }, [features, camOn, sessionId, onWarning]);

  useEffect(() => () => { monitor.current?.stop(); monitor.current = null; camera.current?.stop(); }, []);

  return { camera: camera.current, video, features, status, warning, camOn, camLost, begin, stop,
    dismiss: () => setWarnings((l) => l.slice(0, -1)) };
}
