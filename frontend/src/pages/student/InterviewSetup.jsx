import { useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, Circle, Mic, Play, ShieldCheck, Wifi, XCircle } from "lucide-react";
import { get, post } from "../../api";
import { Button, Notice, Spinner } from "../../components/ui";
import { FaceMonitor } from "../../monitoring/faceMonitor";
import { setupGuidance } from "../../monitoring/frameAnalysis";
import { cameraErrorMessage, checkNetwork, testMicrophone } from "../../monitoring/mediaSession";

const FEATURE_ORDER = ["camera", "face_presence", "multiple_faces", "attention", "focus_changes"];
const NONE = { camera: false, face_presence: false, multiple_faces: false, attention: false, focus_changes: false };

/**
 * Steps before a live interview: 1) what happens and what is monitored (separate opt-in per feature),
 * 2) camera / microphone / network check (permissions are requested only when the student presses the button),
 * 3) start. The first question and the models are being prepared on the server meanwhile.
 */
export default function InterviewSetup({ session, persona: p, voice, camera, answerLimit, onStart, onUnlockAudio }) {
  const [policy, setPolicy] = useState(null);
  const [policyError, setPolicyError] = useState(null);
  const [features, setFeatures] = useState(NONE);
  const [camState, setCamState] = useState({ status: "idle" }); // idle | starting | on | denied | error
  const [mic, setMic] = useState({ status: "idle", level: 0 });
  const [net, setNet] = useState(null);
  const [guide, setGuide] = useState(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);
  const video = useRef(null);
  const monitor = useRef(null);
  const coaching = session.response_mode === "coaching";

  useEffect(() => {
    post("/voice/warmup").catch(() => {}); // load the AI/voice models while the student reads this page
    get("/monitoring/policy").then((pol) => {
      setPolicy(pol);
      if (pol.camera_required) setFeatures((f) => ({ ...f, camera: true, face_presence: true, multiple_faces: true }));
    }).catch((e) => setPolicyError(e.message));
    checkNetwork().then(setNet);
    return () => monitor.current?.stop();
  }, []);

  const required = !!policy?.camera_required;
  const monitoringOn = policy?.enabled !== false;
  const toggle = (k, v) => setFeatures((f) => {
    const n = { ...f, [k]: v };
    if (k === "camera" && !v) Object.assign(n, { face_presence: false, multiple_faces: false, attention: false });
    if (k !== "camera" && k !== "focus_changes" && v) n.camera = true;
    return n;
  });

  const startCamera = async () => {
    setCamState({ status: "starting" });
    try {
      const stream = await camera.start({});
      if (video.current) video.current.srcObject = stream;
      setCamState({ status: "on" });
      monitor.current?.stop();
      monitor.current = new FaceMonitor({ fps: 3, onFrame: ({ faces, light }) => setGuide(setupGuidance(faces, light)) });
      monitor.current.start(video.current).catch(() => setGuide({ ok: null, text: "Automatic face check is not available in this browser; please check the preview yourself." }));
    } catch (e) {
      setCamState({ status: e.name === "NotAllowedError" ? "denied" : "error", message: cameraErrorMessage(e) });
    }
  };
  const stopCamera = () => { monitor.current?.stop(); camera.stop(); setCamState({ status: "idle" }); setGuide(null); };

  const runChecks = async () => {
    onUnlockAudio?.(); // user gesture: allow the interviewer's audio to play later without delay
    if (features.camera && camState.status !== "on") await startCamera();
    if (voice?.stt?.enabled !== false) {
      setMic({ status: "testing", level: 0 });
      const r = await testMicrophone((level) => setMic((m) => ({ ...m, level })));
      setMic(r.ok ? { status: r.heard ? "ok" : "quiet", level: 0 } : { status: "error", message: r.error, level: 0 });
    }
    setNet(await checkNetwork());
  };

  useEffect(() => { if (!features.camera && camState.status === "on") stopCamera(); }, [features.camera]); // eslint-disable-line react-hooks/exhaustive-deps

  const cameraBlocked = features.camera && camState.status !== "on";
  const canStart = !!policy && !starting && !(required && camState.status !== "on");

  const start = async () => {
    setStarting(true);
    setError(null);
    onUnlockAudio?.();
    const granted = camState.status === "on";
    const consented = monitoringOn ? { ...features, ...(granted ? {} : { camera: false, face_presence: false, multiple_faces: false, attention: false }) } : NONE;
    try {
      await post(`/student/interviews/${session.id}/monitoring/consent`, {
        policy_version: policy.version, features: consented,
        camera_permission: granted ? "granted" : camState.status === "denied" ? "denied" : camState.status === "error" ? "unavailable" : "not_requested",
      });
      monitor.current?.stop(); // the setup check ends; the interview monitor (if consented) takes over
      monitor.current = null;
      if (!consented.camera && camera.active) camera.stop();
      onStart({ features: consented, video: video.current });
    } catch (e) {
      setError(e.message);
      setStarting(false);
    }
  };

  if (!policy && !policyError) return <Spinner label="Preparing the interview room…" />;

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-lg font-semibold">Before we start with {p.name}</h2>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium">{coaching ? "Coaching mode" : "Fast interview mode"}</span>
      </div>
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
        <li>{p.name} asks each question aloud. Turn your sound on, or switch the voice off and read the subtitles.</li>
        <li>When {p.name} finishes, your <b>microphone turns on</b> (red "Recording" badge) and stops after a short pause. You can change how long it waits in Settings, stop it yourself, and correct the text before sending.</li>
        <li>{coaching ? `Coaching mode: ${p.name} gives short spoken feedback and hints after each answer, and you get more time.` : `Fast mode: short questions and quick transitions. Detailed feedback comes at the end.`}</li>
        {p.interrupts && <li className="text-red-700">Stress interview: each answer has a limit of about {answerLimit} seconds. If you run over, {p.name} will stop you and keep what you said so far.</li>}
        <li>Your voice is transcribed <b>on this app's server</b> by a local model; the audio is <b>not saved</b>.</li>
      </ul>

      {/* ---------------- monitoring disclosure */}
      <section className="rounded-lg border border-slate-200 p-4" aria-labelledby="mon-title">
        <h3 id="mon-title" className="flex items-center gap-2 font-semibold"><ShieldCheck size={18} /> Camera and interview monitoring</h3>
        {policyError && <Notice>The monitoring policy could not be loaded ({policyError}). Monitoring stays off.</Notice>}
        {policy && !monitoringOn && <p className="mt-2 text-sm text-slate-600">Monitoring is switched off on this platform. Nothing is monitored.</p>}
        {policy && monitoringOn && (
          <>
            <p className="mt-2 text-sm text-slate-600">{required
              ? "This assessment requires your camera. The checks below are needed to start."
              : "Monitoring is optional for this practice interview. Choose what you are comfortable with - nothing is switched on unless you tick it."}</p>
            <div className="mt-3 space-y-2">
              {FEATURE_ORDER.map((k) => {
                const f = policy.features[k];
                const locked = required && ["camera", "face_presence", "multiple_faces"].includes(k);
                return (
                  <label key={k} className="flex items-start gap-3 rounded-md p-2 hover:bg-slate-50">
                    <input type="checkbox" className="mt-1" checked={features[k]} disabled={locked}
                      onChange={(e) => toggle(k, e.target.checked)} aria-describedby={`why-${k}`} />
                    <span className="text-sm"><b>{f.label}</b>{locked && <span className="ml-1 text-xs text-slate-500">(required)</span>}
                      <span id={`why-${k}`} className="block text-slate-500">{f.why}</span></span>
                  </label>
                );
              })}
            </div>
            <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              <Term t="Where it is processed">{policy.processing}</Term>
              <Term t="What is stored">{policy.stored}</Term>
              <Term t="Never stored">{policy.not_stored}</Term>
              <Term t="How long">Events are deleted automatically after {policy.retention_days} days.</Term>
              <Term t="Who can see it">{policy.access}</Term>
              <Term t="Review and fairness">{policy.review}</Term>
              <Term t="Stopping">{policy.withdraw}</Term>
              <Term t="Microphone">{policy.microphone}</Term>
            </dl>
            <p className="mt-2 text-xs text-slate-500">Monitoring never measures emotions, honesty, personality or identity, and it does not affect your interview scores. If a disability, eye condition or your setup makes these checks unreliable for you, leave them off or tell your placement cell.</p>
          </>
        )}
      </section>

      {/* ---------------- device check */}
      <section className="rounded-lg border border-slate-200 p-4" aria-labelledby="chk-title">
        <h3 id="chk-title" className="font-semibold">Check your setup</h3>
        <p className="mt-1 text-sm text-slate-600">{features.camera
          ? "Your browser will ask for camera and microphone permission when you press the button. The camera picture is only analysed in this browser to help with framing - nothing is recorded."
          : "Your browser will ask for microphone permission when you press the button."}</p>
        <div className="mt-3 grid gap-4 md:grid-cols-[260px_1fr]">
          <div className="relative flex aspect-[4/3] items-center justify-center overflow-hidden rounded-lg bg-slate-800 text-xs text-slate-300">
            <video ref={video} autoPlay muted playsInline className={`h-full w-full -scale-x-100 object-cover ${camState.status === "on" ? "" : "hidden"}`} aria-label="Your camera preview" />
            {camState.status !== "on" && <span className="p-3 text-center">{features.camera ? "Camera preview appears here" : "Camera not used"}</span>}
            {camState.status === "on" && <span className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-red-600 px-2 py-0.5 text-[11px] text-white"><Camera size={11} /> Camera on</span>}
          </div>
          <ul className="space-y-2 text-sm">
            <Check ok={net?.ok} label="Connection to the interview server" detail={net?.ok ? `${net.ms} ms` : net ? "Cannot reach the server" : "Checking…"} icon={<Wifi size={14} />} />
            {voice?.stt?.enabled !== false && (
              <Check ok={mic.status === "ok" ? true : mic.status === "idle" || mic.status === "testing" ? null : false}
                label="Microphone" icon={<Mic size={14} />}
                detail={mic.status === "testing" ? "Say something…" : mic.status === "ok" ? "Working" : mic.status === "quiet" ? "Very quiet - check the selected microphone, or type your answers" : mic.message || "Not tested yet"}>
                {mic.status === "testing" && <div className="mt-1 h-1.5 w-40 overflow-hidden rounded bg-slate-200"><div className="h-full bg-emerald-500" style={{ width: `${Math.min(100, mic.level * 900)}%` }} /></div>}
              </Check>
            )}
            {features.camera && (
              <>
                <Check ok={camState.status === "on" ? true : camState.status === "idle" || camState.status === "starting" ? null : false}
                  label="Camera available and permitted" icon={<Camera size={14} />}
                  detail={camState.status === "on" ? "Working" : camState.message || "Not tested yet"} />
                <Check ok={camState.status !== "on" ? null : guide?.ok ?? null} label="Face visible, framing and lighting"
                  detail={camState.status === "on" ? guide?.text || "Analysing…" : "After the camera starts"} />
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
          <Button variant="secondary" onClick={runChecks} loading={camState.status === "starting" || mic.status === "testing"}>Test my {features.camera ? "camera and " : ""}microphone</Button>
          {camState.status === "on" && !required && <Button variant="ghost" onClick={() => toggle("camera", false)}>Turn camera off</Button>}
        </div>
      </section>

      {voice && !voice.tts?.enabled && <p className="text-sm text-amber-700">The local voice is off on this server, so the browser's voice will be used (approximate lip sync).</p>}
      {voice && !voice.stt?.enabled && <p className="text-sm text-amber-700">Speech recognition is off on this server - you will type your answers.</p>}
      {error && <Notice>{error}</Notice>}
      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={start} disabled={!canStart} loading={starting}><Play size={16} /> {features.camera && camState.status === "on" ? `I agree - start the interview with ${p.name}` : `Start the interview with ${p.name}`}</Button>
        {cameraBlocked && !required && <span className="text-xs text-slate-500">Camera not tested: the interview will start without camera monitoring.</span>}
        {required && camState.status !== "on" && <span className="text-xs text-red-700">The camera check must pass first.</span>}
      </div>
    </div>
  );
}

function Term({ t, children }) {
  return <div><dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t}</dt><dd className="text-slate-700">{children}</dd></div>;
}

function Check({ ok, label, detail, icon, children }) {
  const Icon = ok === true ? CheckCircle2 : ok === false ? XCircle : Circle;
  return (
    <li className="flex items-start gap-2">
      <Icon size={18} className={ok === true ? "text-emerald-600" : ok === false ? "text-red-600" : "text-slate-400"} aria-hidden="true" />
      <div><p className="flex items-center gap-1 font-medium">{icon}{label}</p><p className="text-xs text-slate-500">{detail}</p>{children}</div>
    </li>
  );
}
