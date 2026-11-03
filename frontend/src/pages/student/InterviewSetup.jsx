import { useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, Circle, Eye, Globe, Mic, Play, ShieldCheck, Wifi, XCircle } from "lucide-react";
import { get, post } from "../../api";
import { Button, Notice, Spinner } from "../../components/ui";
import { FaceMonitor } from "../../monitoring/faceMonitor";
import { preloadObjectDetector } from "../../monitoring/objectMonitor";
import { Calibration, setupGuidance } from "../../monitoring/frameAnalysis";
import { browserSupport, cameraErrorMessage, checkNetwork, testMicrophone } from "../../monitoring/mediaSession";

const FEATURE_ORDER = ["camera", "face_presence", "multiple_faces", "attention", "objects", "audio", "focus_changes", "screen", "paste"];
const NONE = { camera: false, face_presence: false, multiple_faces: false, attention: false, focus_changes: false,
  paste: false, screen: false, objects: false, audio: false };
const CAMERA_FEATURES = ["face_presence", "multiple_faces", "attention", "objects", "audio"]; // need the camera
const NO_CAMERA = { camera: false, face_presence: false, multiple_faces: false, attention: false, objects: false, audio: false };
const REQUIRED_WITH_CAMERA = ["camera", "face_presence", "multiple_faces"];

/**
 * Steps before a live interview: 1) what happens and what is monitored (separate opt-in per feature),
 * 2) camera / microphone / network check (permissions are requested only when the student presses the button),
 * 3) start. The first question and the models are being prepared on the server meanwhile.
 * `typed`: the typed interview page - no voice or microphone steps and no additional-voice check.
 */
export default function InterviewSetup({ session, persona: p, voice, camera, answerLimit, onStart, onUnlockAudio, typed = false }) {
  const [policy, setPolicy] = useState(null);
  const [policyError, setPolicyError] = useState(null);
  const [features, setFeatures] = useState(NONE);
  const [camState, setCamState] = useState({ status: "idle" }); // idle | starting | on | denied | error
  const [mic, setMic] = useState({ status: "idle", level: 0 });
  const [net, setNet] = useState(null);
  const [guide, setGuide] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);
  const [agreed, setAgreed] = useState(false);
  const [calib, setCalib] = useState({ status: "idle" }); // idle | running | done | failed
  const calibration = useRef(null);
  const support = useRef(browserSupport()).current;
  const video = useRef(null);
  const monitor = useRef(null);
  const coaching = session.response_mode === "coaching";

  useEffect(() => {
    if (!typed) post("/voice/warmup").catch(() => {}); // load the AI/voice models while the student reads this page
    get("/monitoring/policy").then((pol) => {
      setPolicy(pol);
      if (pol.camera_required) {
        const on = REQUIRED_WITH_CAMERA.filter((k) => k === "camera" || pol.features[k]); // only detectors that are enabled
        setFeatures((f) => ({ ...f, ...Object.fromEntries(on.map((k) => [k, true])) }));
      }
    }).catch((e) => setPolicyError(e.message));
    checkNetwork().then(setNet);
    return () => monitor.current?.stop();
  }, []);

  const required = !!policy?.camera_required;
  const monitoringOn = policy?.enabled !== false;
  const toggle = (k, v) => setFeatures((f) => {
    const n = { ...f, [k]: v };
    if (k === "camera" && !v) Object.assign(n, NO_CAMERA);
    if (CAMERA_FEATURES.includes(k) && v) n.camera = true;
    return n;
  });

  const startCamera = async () => {
    setCamState({ status: "starting" });
    try {
      const stream = await camera.start({});
      if (video.current) video.current.srcObject = stream;
      setCamState({ status: "on" });
      monitor.current?.stop();
      monitor.current = new FaceMonitor({ fps: 3, onFrame: ({ faces, light, t }) => {
        setGuide(setupGuidance(faces, light));
        const c = calibration.current;
        if (!c) return;
        const r = c.add(t, faces);
        setCalib((x) => ({ ...x, progress: r.progress }));
        if (r.done) {
          calibration.current = null;
          setCalib(r.baseline ? { status: "done", baseline: r.baseline } : { status: "failed" });
        }
      } });
      monitor.current.start(video.current).catch(() => setGuide({ ok: null, text: "Automatic face check is not available in this browser; please check the preview yourself." }));
    } catch (e) {
      setCamState({ status: e.name === "NotAllowedError" ? "denied" : "error", message: cameraErrorMessage(e) });
    }
  };
  const stopCamera = () => { monitor.current?.stop(); camera.stop(); setCamState({ status: "idle" }); setGuide(null); setCalib({ status: "idle" }); };
  const calibrate = () => {
    calibration.current = new Calibration({ durationMs: policy?.thresholds?.calibration_ms ?? 5000 });
    setCalib({ status: "running", progress: 0 });
  };

  // Load the phone/notes detector while the student is still on this page (it briefly blocks the page the first
  // time; doing it at interview start delayed the interviewer's first words by ~5 s in testing).
  useEffect(() => {
    if (features.objects && camState.status === "on") preloadObjectDetector(video.current);
  }, [features.objects, camState.status]);

  const runChecks = async () => {
    onUnlockAudio?.(); // user gesture: allow the interviewer's audio to play later without delay
    if (features.camera && camState.status !== "on") await startCamera();
    if (!typed && voice?.stt?.enabled !== false) {
      setMic({ status: "testing", level: 0 });
      const r = await testMicrophone((level) => setMic((m) => ({ ...m, level })));
      setMic(r.ok ? { status: r.heard ? "ok" : "quiet", level: 0 } : { status: "error", message: r.error, level: 0 });
    }
    setNet(await checkNetwork());
  };

  useEffect(() => { if (!features.camera && camState.status === "on") stopCamera(); }, [features.camera]); // eslint-disable-line react-hooks/exhaustive-deps

  const cameraBlocked = features.camera && camState.status !== "on";
  const anyMonitoring = monitoringOn && Object.values(features).some(Boolean);
  const unsupported = Object.values(support).filter((x) => x.required && !x.ok);
  const missing = Object.values(support).filter((x) => !x.required && !x.ok).map((x) => x.label);
  // explicit acknowledgement before any monitoring starts; never while calibration is still running
  const canStart = !!policy && !starting && !(required && camState.status !== "on") && (!anyMonitoring || agreed)
    && calib.status !== "running";

  const start = async () => {
    setStarting(true);
    setError(null);
    onUnlockAudio?.();
    const granted = camState.status === "on";
    const consented = monitoringOn ? { ...features, ...(granted ? {} : NO_CAMERA) } : NONE;
    // Full screen must be requested inside this click (browsers only allow it from a user gesture), before any await.
    const fullscreen = consented.screen && !document.fullscreenElement
      ? document.documentElement.requestFullscreen?.().catch(() => {}) : null;
    try {
      const res = await post(`/student/interviews/${session.id}/monitoring/consent`, {
        policy_version: policy.version, features: consented,
        camera_permission: granted ? "granted" : camState.status === "denied" ? "denied" : camState.status === "error" ? "unavailable" : "not_requested",
      });
      monitor.current?.stop(); // the setup check ends; the interview monitor (if consented) takes over
      monitor.current = null;
      if (!consented.camera && camera.active) camera.stop();
      // the server's interview clock continues across reloads (elapsed_ms); the stored features are authoritative
      onStart({ features: res.monitoring?.features || consented, video: video.current, policy,
        baseline: calib.status === "done" ? calib.baseline : null, elapsedMs: res.elapsed_ms || 0 });
    } catch (e) {
      if (fullscreen && document.fullscreenElement) document.exitFullscreen().catch(() => {}); // didn't start
      setError(e.message);
      setStarting(false);
    }
  };

  if (!policy && !policyError) return <Spinner label="Preparing the interview room…" />;

  return (
    <div className="card card-glow space-y-5 p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-xl font-semibold tracking-tight">Before we start with {p.name}</h2>
        <span className="rounded-full border border-brand-400/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-700">{typed ? "Typed interview" : coaching ? "Coaching mode" : "Fast interview mode"}</span>
      </div>
      {typed ? (
        <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-600 marker:text-brand-400">
          <li>{p.name} asks questions on screen and you type your answers.</li>
          <li>Your typed answers are scored by a local model on this app's server.</li>
        </ul>
      ) : (
      <ul className="list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-slate-600 marker:text-brand-400">
          <li>{p.name} asks each question aloud. Turn your sound on, or switch the voice off and read the subtitles.</li>
          <li>When {p.name} finishes, your <b>microphone turns on</b> (red "Recording" badge) and stops after a short pause. You can change how long it waits in Settings, stop it yourself, and correct the text before sending.</li>
          <li>{coaching ? `Coaching mode: ${p.name} gives short spoken feedback and hints after each answer, and you get more time.` : `Fast mode: short questions and quick transitions. Detailed feedback comes at the end.`}</li>
          {p.interrupts && <li className="text-rose-700">Stress interview: each answer has a limit of about {answerLimit} seconds. If you run over, {p.name} will stop you and keep what you said so far.</li>}
          <li>Your voice is transcribed <b>on this app's server</b> by a local model; the audio is <b>not saved</b>.</li>
        </ul>
      )}

      {/* ---------------- monitoring disclosure */}
      <section className="rounded-xl border border-slate-200 bg-slate-100/30 p-4 sm:p-5" aria-labelledby="mon-title">
        <h3 id="mon-title" className="flex items-center gap-2.5 font-semibold"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-500/15 text-brand-700 ring-1 ring-inset ring-brand-400/30"><ShieldCheck size={15} /></span> Camera and interview monitoring</h3>
        {policyError && <Notice>The monitoring policy could not be loaded ({policyError}). Monitoring stays off.</Notice>}
        {policy && !monitoringOn && <p className="mt-2 text-sm text-slate-600">Monitoring is switched off on this platform. Nothing is monitored.</p>}
        {policy && monitoringOn && (
          <>
            <p className="mt-2 text-sm text-slate-600">{required
              ? "This assessment requires your camera. The checks below are needed to start."
              : "Monitoring is optional for this practice interview. Choose what you are comfortable with - nothing is switched on unless you tick it."}</p>
            <div className="mt-3 space-y-2">
              {FEATURE_ORDER.filter((k) => policy.features[k] && !(typed && k === "audio")).map((k) => {
                const f = policy.features[k];
                const locked = required && REQUIRED_WITH_CAMERA.includes(k);
                return (
                  <label key={k} className={`flex items-start gap-3 rounded-lg border p-2.5 transition-colors ${features[k] ? "border-brand-400/35 bg-brand-500/[0.07]" : "border-transparent hover:bg-slate-100/60"}`}>
                    <input type="checkbox" className="mt-1" checked={features[k]} disabled={locked}
                      onChange={(e) => toggle(k, e.target.checked)} aria-describedby={`why-${k}`} />
                    <span className="text-sm"><b>{f.label}</b>{locked && <span className="ml-1 text-xs text-slate-500">(required)</span>}
                      <span id={`why-${k}`} className="block text-slate-500">{f.why}</span></span>
                  </label>
                );
              })}
            </div>
            <dl className="mt-4 grid gap-x-6 gap-y-3 rounded-lg border border-slate-200 bg-slate-50/50 p-4 text-sm sm:grid-cols-2">
              <Term t="Where it is processed">{policy.processing}</Term>
              <Term t="What is stored">{policy.stored}</Term>
              <Term t="Never stored">{policy.not_stored}</Term>
              <Term t="How long">Events are deleted automatically after {policy.retention_days} days.</Term>
              <Term t="Who can see it">{policy.access}</Term>
              <Term t="Review and fairness">{policy.review}</Term>
              <Term t="Stopping">{policy.withdraw}</Term>
              <Term t="Microphone">{policy.microphone}</Term>
              {policy.session_events && <Term t="Connection and device events">{policy.session_events}</Term>}
              {policy.identity && <Term t="Identity">{policy.identity}</Term>}
            </dl>
            <p className="mt-2 text-xs text-slate-500">Monitoring never measures emotions, honesty, personality or identity, and it does not affect your interview scores. If a disability, eye condition or your setup makes these checks unreliable for you, leave them off or tell your placement cell.</p>
          </>
        )}
      </section>

      {/* ---------------- device check */}
      <section className="rounded-xl border border-slate-200 bg-slate-100/30 p-4 sm:p-5" aria-labelledby="chk-title">
        <h3 id="chk-title" className="flex items-center gap-2.5 font-semibold"><span className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-500/15 text-teal-700 ring-1 ring-inset ring-teal-400/30"><Camera size={15} /></span>Check your setup</h3>
        <ul className="mt-2 list-disc space-y-0.5 pl-5 text-sm text-slate-600 marker:text-teal-400">
          <li>Sit comfortably and position your face within the camera frame.</li>
          <li>Look toward the interview screen.</li>
          <li>Make sure the room is lit well enough for your face to be clearly visible.</li>
        </ul>
        <p className="mt-1 text-sm text-slate-600">{features.camera
          ? "Your browser will ask for camera and microphone permission when you press the button. The camera picture is only analysed in this browser to help with framing - nothing is recorded."
          : "Your browser will ask for microphone permission when you press the button."}</p>
        <div className="mt-3 grid gap-4 md:grid-cols-[260px_1fr]">
          <div className={`relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-xl bg-night-900 text-xs text-slate-600 ring-1 transition-shadow ${camState.status === "on" ? "ring-emerald-400/40 shadow-[0_0_40px_-10px_rgb(16_185_129/0.55)]" : "ring-slate-200"}`}>
            <video ref={video} autoPlay muted playsInline className={`h-full w-full -scale-x-100 object-cover ${camState.status === "on" ? "" : "hidden"}`} aria-label="Your camera preview" />
            {camState.status !== "on" && <span className="p-3 text-center">{features.camera ? "Camera preview appears here" : "Camera not used"}</span>}
            {camState.status === "on" && <span className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-rose-600 px-2 py-0.5 text-[11px] text-snow shadow-[0_0_12px_rgb(244_63_94/0.7)]"><Camera size={11} /> Camera on</span>}
          </div>
          <ul className="space-y-1.5 text-sm">
            <Check ok={net?.ok} label="Connection to the interview server" detail={net?.ok ? `${net.ms} ms` : net ? "Cannot reach the server" : "Checking…"} icon={<Wifi size={14} />} />
            <Check ok={!unsupported.length} label="Browser compatibility" icon={<Globe size={14} />}
              detail={unsupported.length ? `Not supported here: ${unsupported.map((x) => x.label).join(", ")}. Please use a current Chrome, Edge or Firefox.`
                : missing.length ? `Supported. Not available in this browser, so not used: ${missing.join(", ")}.` : "Supported"} />
            {!typed && voice?.stt?.enabled !== false && (
              <Check ok={mic.status === "ok" ? true : mic.status === "idle" || mic.status === "testing" ? null : false}
                label="Microphone" icon={<Mic size={14} />}
                detail={mic.status === "testing" ? "Say something…" : mic.status === "ok" ? "Working" : mic.status === "quiet" ? "Very quiet - check the selected microphone, or type your answers" : mic.message || "Not tested yet"}>
                {mic.status === "testing" && <div className="mt-1.5 h-1.5 w-40 overflow-hidden rounded-full bg-slate-200"><div className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 shadow-[0_0_10px_rgb(16_185_129/0.7)]" style={{ width: `${Math.min(100, mic.level * 900)}%` }} /></div>}
              </Check>
            )}
            {features.camera && (
              <>
                <Check ok={camState.status === "on" ? true : camState.status === "idle" || camState.status === "starting" ? null : false}
                  label="Camera available and permitted" icon={<Camera size={14} />}
                  detail={camState.status === "on" ? "Working" : camState.message || "Not tested yet"} />
                <Check ok={camState.status !== "on" ? null : guide?.ok ?? null} label="Face visible, framing and lighting"
                  detail={camState.status === "on" ? guide?.text || "Analysing…" : "After the camera starts"} />
                {features.attention && (
                  <Check ok={calib.status === "done" ? true : calib.status === "failed" ? false : null} label="Eye-tracking calibration (optional)" icon={<Eye size={14} />}
                    detail={calib.status === "running" ? `Look at the interview screen… ${Math.round((calib.progress || 0) * 100)}%`
                      : calib.status === "done" ? (Math.abs(calib.baseline.yaw) > 30 || Math.abs(calib.baseline.pitch) > 25
                        ? "Measured - but your head seemed clearly turned. That is fine if your camera is beside the screen; otherwise please calibrate again while looking at the interview screen."
                        : "Your normal viewing position was measured. Looking away is measured from it.")
                        : calib.status === "failed" ? "Your face was not visible clearly enough. Calibration will run again when the interview starts."
                          : "Measures your normal viewing position for a few seconds, so camera placement and posture are taken into account. If you skip it, it runs at the start of the interview."}>
                    {camState.status === "on" && calib.status !== "running" && (
                      <Button size="sm" variant="ghost" className="mt-1" onClick={calibrate}>{calib.status === "done" ? "Calibrate again" : "Calibrate now"}</Button>
                    )}
                  </Check>
                )}
              </>
            )}
          </ul>
        </div>
        {camState.status === "denied" && (
          <Notice>{required
            ? "This assessment requires camera access, so it cannot start without it. To allow it, click the camera icon in the address bar, choose Allow, then press the button again. If you cannot use a camera, contact your placement cell for an alternative arrangement."
            : "Camera permission was denied. You can allow it in the address bar and try again, or start without the camera - camera monitoring will then be off."}</Notice>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={runChecks} loading={camState.status === "starting" || mic.status === "testing"}>{typed ? "Test my camera and connection" : `Test my ${features.camera ? "camera and " : ""}microphone`}</Button>
          {camState.status === "on" && !required && <Button variant="ghost" onClick={() => toggle("camera", false)}>Turn camera off</Button>}
        </div>
      </section>

      {voice && !voice.tts?.enabled && <p className="text-sm text-amber-700">The local voice is off on this server, so the browser's voice will be used (approximate lip sync).</p>}
      {voice && !voice.stt?.enabled && <p className="text-sm text-amber-700">Speech recognition is off on this server - you will type your answers.</p>}
      {error && <Notice>{error}</Notice>}
      {anyMonitoring && (
        <label className={`flex items-start gap-3 rounded-xl border p-4 text-sm leading-relaxed transition-colors ${agreed ? "border-brand-400/40 bg-brand-500/[0.08] text-slate-800" : "border-slate-200 bg-slate-100/30 text-slate-600"}`}>
          <input type="checkbox" className="mt-1" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          <span>I have read what is monitored, why, what is stored, who can see it and how long it is kept, and I agree to the monitoring selected above. If I need help or an accommodation, I can contact my placement cell before starting.</span>
        </label>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={start} disabled={!canStart} loading={starting}><Play size={16} /> {anyMonitoring ? `I agree - start the interview with ${p.name}` : `Continue - start the interview with ${p.name}`}</Button>
        {anyMonitoring && !agreed && <span className="text-xs text-slate-500">Please confirm the monitoring notice above first.</span>}
        {cameraBlocked && !required && <span className="text-xs text-slate-500">Camera not tested: the interview will start without camera monitoring.</span>}
        {required && camState.status !== "on" && <span className="text-xs text-rose-700">The camera check must pass first.</span>}
      </div>
    </div>
  );
}

function Term({ t, children }) {
  return <div><dt className="eyebrow">{t}</dt><dd className="mt-0.5 leading-relaxed text-slate-700">{children}</dd></div>;
}

function Check({ ok, label, detail, icon, children }) {
  const Icon = ok === true ? CheckCircle2 : ok === false ? XCircle : Circle;
  return (
    <li className={`flex items-start gap-3 rounded-lg border px-3 py-2 transition-colors ${ok === true ? "border-emerald-400/25 bg-emerald-500/[0.06]" : ok === false ? "border-rose-400/30 bg-rose-500/[0.07]" : "border-slate-200 bg-slate-100/30"}`}>
      <Icon size={18} className={`mt-0.5 shrink-0 ${ok === true ? "text-emerald-600 drop-shadow-[0_0_6px_rgb(52_211_153/0.7)]" : ok === false ? "text-rose-600 drop-shadow-[0_0_6px_rgb(244_63_94/0.7)]" : "text-slate-400"}`} aria-hidden="true" />
      <div className="min-w-0"><p className="flex items-center gap-1.5 font-medium text-slate-900">{icon}{label}</p><p className="text-xs leading-relaxed text-slate-500">{detail}</p>{children}</div>
    </li>
  );
}
