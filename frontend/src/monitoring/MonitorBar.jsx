import { useEffect, useState } from "react";
import { Camera, CameraOff, Crosshair, Eye, Mic, MicOff, ShieldCheck, ShieldOff, Wifi, WifiOff } from "lucide-react";
import { get, put } from "../api";
import { Button, ConfirmButton } from "../components/ui";
import { AttentionCard, AttentionReport } from "./AttentionPanels";

// Glass status pills: tinted fill + ring; "live" capture (camera/mic) glows rose so it is never missed.
const PILL = "flex items-center gap-1.5 rounded-full px-3 py-1 font-medium ring-1 ring-inset backdrop-blur";
const ON = "bg-emerald-500/10 text-emerald-700 ring-emerald-400/30";
const OFF = "bg-slate-100/70 text-slate-600 ring-slate-200";
const WARN = "bg-amber-500/10 text-amber-700 ring-amber-400/35";
const LIVE = "bg-rose-500/15 text-rose-700 ring-rose-400/45 shadow-[0_0_14px_-2px_rgb(244_63_94/0.55)]";
const GAZE = { calibrating: ["Eye tracking: calibrating - look at the screen", ON], active: ["Eye tracking: active", ON],
  uncalibrated: ["Eye tracking: active (not calibrated)", ON] };

/**
 * Always-visible status of camera, microphone, face, eye tracking, connection and monitoring during the interview,
 * plus neutral warnings. Only statuses the running monitor actually reports are shown.
 */
export function MonitorBar({ features, status, cameraOn, recording, warning, onDismiss, onStop, cameraLost, micProblem }) {
  const monitored = features && (features.camera || features.focus_changes || features.paste || features.screen);
  const list = [features?.face_presence && "face visibility", features?.multiple_faces && "more than one face",
    features?.attention && "approximate attention", features?.objects && "phone/notes", features?.audio && "additional voice",
    features?.focus_changes && "tab/window focus", features?.screen && "full screen", features?.paste && "pasting"].filter(Boolean);
  const running = status?.analysis === "running";
  const face = running && features?.face_presence
    ? (status.faces === 1 ? (status.edge ? "Face partly out of frame" : "Face visible") : status.faces > 1 ? "More than one face" : "Face not visible") : null;
  const gaze = running && features?.attention ? GAZE[status.gaze] : null;
  const offline = monitored && status && status.online === false;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs" role="status" aria-label="Camera, microphone and monitoring status">
        <span className={`${PILL} ${cameraOn ? LIVE : cameraLost ? WARN : OFF}`}>
          {cameraOn ? <Camera size={13} /> : <CameraOff size={13} />} {cameraOn ? "Camera on" : cameraLost ? "Camera disconnected" : "Camera off"}
        </span>
        <span className={`${PILL} ${recording ? LIVE : micProblem ? WARN : OFF}`} title={micProblem || undefined}>
          {recording ? <Mic size={13} /> : <MicOff size={13} />} {recording ? "Microphone recording" : micProblem ? "Microphone unavailable" : "Microphone off"}
        </span>
        <span className={`${PILL} ${monitored ? ON : OFF}`}>
          {monitored ? <ShieldCheck size={13} /> : <ShieldOff size={13} />}
          {monitored ? `Monitoring: ${list.join(", ") || "camera only"}` : "Not monitored"}
          {monitored && status?.analysis === "unavailable" && " (face analysis unavailable)"}
        </span>
        {face && <span className={`${PILL} ${status.faces === 1 && !status.edge ? ON : WARN}`}><Eye size={13} /> {face}</span>}
        {gaze && <span className={`${PILL} ${gaze[1]}`}><Crosshair size={13} /> {gaze[0]}</span>}
        {monitored && (
          <span className={`${PILL} ${offline ? WARN : ON}`}>
            {offline ? <WifiOff size={13} /> : <Wifi size={13} />} {offline ? "Connection lost - events are kept and sent later" : "Interview session connected"}
          </span>
        )}
        {monitored && onStop && (
          <ConfirmButton size="sm" variant="secondary" className="!h-7 !rounded-full"
            message="Stop all monitoring for the rest of this interview? The camera turns off immediately. Your interview continues."
            onConfirm={onStop}>Stop monitoring</ConfirmButton>
        )}
      </div>
      {monitored && features?.camera && features?.attention && (
        <AttentionCard status={status} cameraOn={cameraOn} cameraLost={cameraLost} />
      )}
      {warning && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-400/30 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-800 backdrop-blur" role="alert">
          <span className="mr-auto">{warning.message}</span>
          {warning.type === "fullscreen_exit" && document.documentElement.requestFullscreen && (
            <button type="button" className="text-xs font-semibold underline"
              onClick={() => document.documentElement.requestFullscreen().catch(() => {})}>Return to full screen</button>
          )}
          <button type="button" className="text-xs underline" onClick={onDismiss}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

const fmt = (ms) => { const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const SEV = { info: "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-200", low: "bg-sky-500/10 text-sky-700 ring-1 ring-inset ring-sky-400/30", medium: "bg-amber-500/10 text-amber-700 ring-1 ring-inset ring-amber-400/30", high: "bg-rose-500/10 text-rose-700 ring-1 ring-inset ring-rose-400/30" };

/** The student's own view after the interview: what was recorded, review status, and a place to explain. */
export function MonitoringSummary({ sessionId }) {
  const [data, setData] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [saved, setSaved] = useState({});
  useEffect(() => { get(`/student/interviews/${sessionId}/integrity-events`).then(setData).catch(() => setData(null)); }, [sessionId]);
  if (!data || !data.summary?.config) return null;
  const save = async (e) => {
    const text = (drafts[e.id] ?? "").trim();
    if (!text) return;
    const out = await put(`/student/interviews/${sessionId}/integrity-events/${e.id}/explanation`, { text });
    setData((d) => ({ ...d, events: d.events.map((x) => (x.id === e.id ? out : x)) }));
    setSaved((s) => ({ ...s, [e.id]: true }));
  };
  return (
    <section className="card p-5">
      <h2 className="text-lg font-semibold">Interview monitoring</h2>
      <p className="mt-1 text-sm text-slate-600">Reviewed separately from your performance. These signals are approximate, are not evidence of anything on their own, and did not change your scores.</p>
      <p className="mt-2 text-sm"><b>{data.summary.status.label}.</b> {data.summary.status.detail}</p>
      {data.summary.risk && <p className="mt-1 text-sm text-slate-600">Summary for reviewers: <b>{data.summary.risk.band.label}</b>. {data.summary.risk.disclaimer}</p>}
      {data.attention && <div className="mt-3"><AttentionReport a={data.attention} /></div>}
      {data.events.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 text-sm">
          {data.events.map((e) => (
            <li key={e.id} className="py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium" title={e.description}>{e.label}</span>
                <span className={`rounded px-2 py-0.5 text-xs ${SEV[e.severity]}`}>{e.severity}</span>
                <span className="text-xs text-slate-500">at {fmt(e.t_ms)}{e.duration_ms ? ` for ${fmt(e.duration_ms)}` : ""}{e.confidence != null ? ` · agreement ${Math.round(e.confidence * 100)}%` : ""}</span>
                <span className="ml-auto text-xs text-slate-500">{e.review_status === "pending" ? "not reviewed" : e.review_status.replaceAll("_", " ")}</span>
              </div>
              <div className="mt-1 flex gap-2">
                <input className="input py-1 text-sm" maxLength={1000} placeholder="Add an explanation (optional), e.g. 'my lamp switched off'"
                  value={drafts[e.id] ?? e.candidate_explanation ?? ""} onChange={(ev) => setDrafts((d) => ({ ...d, [e.id]: ev.target.value }))}
                  aria-label={`Explanation for ${e.label} at ${fmt(e.t_ms)}`} />
                <Button size="sm" variant="secondary" onClick={() => save(e)}>{saved[e.id] ? "Saved" : "Save"}</Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
