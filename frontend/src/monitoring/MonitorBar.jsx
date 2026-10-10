import { useEffect, useState } from "react";
import { Camera, CameraOff, Eye, Mic, MicOff, ShieldCheck, ShieldOff } from "lucide-react";
import { get, put } from "../api";
import { Button, ConfirmButton } from "../components/ui";

const ON = "bg-emerald-600/90";
const OFF = "bg-slate-600/90";

/** Always-visible status of camera, microphone and monitoring during the interview, plus neutral warnings. */
export function MonitorBar({ features, status, cameraOn, recording, warning, onDismiss, onStop, cameraLost }) {
  const monitored = features && (features.camera || features.focus_changes);
  const list = [features?.face_presence && "face visibility", features?.multiple_faces && "more than one face",
    features?.attention && "approximate attention", features?.focus_changes && "tab/window focus"].filter(Boolean);
  const face = status?.analysis === "running" && features?.face_presence
    ? (status.faces === 1 ? "Face visible" : status.faces > 1 ? "More than one face" : "Face not visible") : null;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs text-white" role="status" aria-label="Camera, microphone and monitoring status">
        <span className={`flex items-center gap-1 rounded-full px-3 py-1 ${cameraOn ? "bg-red-600" : OFF}`}>
          {cameraOn ? <Camera size={13} /> : <CameraOff size={13} />} {cameraOn ? "Camera on" : cameraLost ? "Camera disconnected" : "Camera off"}
        </span>
        <span className={`flex items-center gap-1 rounded-full px-3 py-1 ${recording ? "bg-red-600" : OFF}`}>
          {recording ? <Mic size={13} /> : <MicOff size={13} />} {recording ? "Microphone recording" : "Microphone off"}
        </span>
        <span className={`flex items-center gap-1 rounded-full px-3 py-1 ${monitored ? ON : OFF}`}>
          {monitored ? <ShieldCheck size={13} /> : <ShieldOff size={13} />}
          {monitored ? `Monitoring: ${list.join(", ") || "camera only"}` : "Not monitored"}
          {monitored && status?.analysis === "unavailable" && " (face analysis unavailable)"}
        </span>
        {face && <span className={`flex items-center gap-1 rounded-full px-3 py-1 ${status.faces === 1 ? ON : "bg-amber-600"}`}><Eye size={13} /> {face}</span>}
        {monitored && onStop && (
          <ConfirmButton size="sm" variant="ghost" className="text-slate-700"
            message="Stop all monitoring for the rest of this interview? The camera turns off immediately. Your interview continues."
            onConfirm={onStop}>Stop monitoring</ConfirmButton>
        )}
      </div>
      {warning && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="alert">
          <span className="mr-auto">{warning.message}</span>
          <button type="button" className="text-xs underline" onClick={onDismiss}>Dismiss</button>
        </div>
      )}
    </div>
  );
}

const fmt = (ms) => { const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const SEV = { info: "bg-slate-100 text-slate-700", low: "bg-sky-100 text-sky-800", medium: "bg-amber-100 text-amber-900", high: "bg-red-100 text-red-800" };

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
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-lg font-semibold">Interview monitoring</h2>
      <p className="mt-1 text-sm text-slate-600">Reviewed separately from your performance. These signals are approximate, are not evidence of anything on their own, and did not change your scores.</p>
      <p className="mt-2 text-sm"><b>{data.summary.status.label}.</b> {data.summary.status.detail}</p>
      {data.events.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 text-sm">
          {data.events.map((e) => (
            <li key={e.id} className="py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{e.label}</span>
                <span className={`rounded px-2 py-0.5 text-xs ${SEV[e.severity]}`}>{e.severity}</span>
                <span className="text-xs text-slate-500">at {fmt(e.t_ms)}{e.duration_ms ? ` for ${fmt(e.duration_ms)}` : ""}{e.confidence != null ? ` · agreement ${Math.round(e.confidence * 100)}%` : ""}</span>
                <span className="ml-auto text-xs text-slate-500">{e.review_status === "pending" ? "not reviewed" : e.review_status.replace("_", " ")}</span>
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
