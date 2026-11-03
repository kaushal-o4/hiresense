/*
 * Admin -> AI & Monitoring -> Security settings: which detectors are offered, detection thresholds, reminder and
 * pause rules, severity caps, risk-summary weights and recruiter access (GET/PUT /admin/security-settings, audited).
 * Global switches (monitoring on/off, camera required, retention) use the existing platform settings.
 * Values are engineering starting points, not validated cheating thresholds - tune them against test sessions.
 */

import { useEffect, useState } from "react";
import { get, put } from "../../api";
import { Button, Card, ErrorBox, Notice, Spinner, useApi, useToast } from "../../components/ui";

const DETECTORS = {
  face_presence: "Face visibility (incl. partly out of frame)", multiple_faces: "More than one face",
  attention: "Approximate head direction and eye gaze", focus_changes: "Browser tab / window focus",
  screen: "Full screen and extra displays", paste: "Pasted text", objects: "Phone or notes in view",
  audio: "Possible additional voice during answers",
};
// [key, label, unit, step]
const THRESHOLDS = [
  ["frame_rate", "Face analyses per second (lowered automatically on slow devices)", "/s", 0.5],
  ["calibration_ms", "Calibration of the normal viewing position", "ms", 500],
  ["gaze_record_ms", "Looking away is recorded after", "ms", 500],
  ["gaze_warn_ms", "Looking away: reminder shown after", "ms", 500],
  ["gaze_yaw_deg", "Head turn beyond the calibrated position", "°", 1],
  ["gaze_pitch_deg", "Head tilt beyond the calibrated position", "°", 1],
  ["gaze_eye", "Eye direction difference (0-1)", "", 0.05],
  ["gaze_repeat_count", "Repeated looking away: number of deviations", "", 1],
  ["gaze_repeat_window_s", "... within", "s", 10],
  ["face_absent_warn_ms", "No face: reminder after", "ms", 500],
  ["face_absent_record_ms", "No face: recorded after", "ms", 500],
  ["multiple_faces_warn_ms", "More than one face: reminder after", "ms", 500],
  ["multiple_faces_record_ms", "More than one face: recorded after", "ms", 500],
  ["focus_record_ms", "Tab/window switches shorter than this are ignored", "ms", 100],
  ["audio_min_speech_ms", "Additional voice: speech needed before judging", "ms", 500],
  ["attention_window_s", "Live visual-attention percentage: rolling window", "s", 5],
  ["attention_confirm_ms", "Attention: a look toward/away must last this long to count", "ms", 100],
  ["attention_max_gap_ms", "Attention: longer without a camera frame counts as unobserved", "ms", 250],
  ["min_confidence", "Minimum frame agreement before an event can rise above 'info' (0-1)", "", 0.05],
];

function Num({ label, unit, value, step, onChange }) {
  return (
    <label className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-slate-700">{label}</span>
      <span className="flex items-center gap-1">
        <input className="input w-28 py-1" type="number" step={step} min="0" value={value} onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} aria-label={label} />
        <span className="w-6 text-xs text-slate-500">{unit}</span>
      </span>
    </label>
  );
}

function Switch({ label, checked, onChange }) {
  return (
    <label className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-slate-700">{label}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} aria-label={label} />
    </label>
  );
}

export default function SecuritySettings() {
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => get("/admin/security-settings"));
  const [cfg, setCfg] = useState(null);
  const [glob, setGlob] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) { setCfg(data.config); setGlob(data.global); } }, [data]);
  if (loading) return <Spinner />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!cfg || !glob) return null;
  const setIn = (section, key, v) => setCfg((c) => ({ ...c, [section]: { ...c[section], [key]: v } }));

  const save = async () => {
    setBusy(true);
    try {
      const out = await put("/admin/security-settings", cfg);
      for (const [k, v] of Object.entries(glob)) if (v !== data.global[k]) await put(`/admin/settings/${k}`, { value: v });
      toast(out.changed.length ? `Saved (${out.changed.length} change${out.changed.length > 1 ? "s" : ""}, recorded in the audit log)` : "Saved - nothing changed");
      reload();
    } catch (e) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <Notice tone="blue">{data.note} The numbers are engineering starting points, not validated cheating thresholds: tune them against real test sessions. Events never change interview scores, and the security summary must never be the only basis for a hiring decision.</Notice>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Global">
          <Switch label="Offer interview monitoring at all" checked={!!glob.monitoring_enabled} onChange={(v) => setGlob({ ...glob, monitoring_enabled: v })} />
          <Switch label="Camera required (face visibility and more-than-one-face checks mandatory)" checked={!!glob.monitoring_camera_required} onChange={(v) => setGlob({ ...glob, monitoring_camera_required: v })} />
          <Num label="Event retention (deleted automatically after)" unit="days" step={1} value={glob.monitoring_retention_days} onChange={(v) => setGlob({ ...glob, monitoring_retention_days: v })} />
          <Switch label="Recruiters can see security reports of completed interviews of their applicants (disclosed to candidates; applies to new consents)" checked={!!cfg.recruiters_can_view} onChange={(v) => setCfg({ ...cfg, recruiters_can_view: v })} />
        </Card>
        <Card title="Detectors offered to candidates">
          {Object.entries(DETECTORS).map(([k, label]) => <Switch key={k} label={label} checked={!!cfg.detectors[k]} onChange={(v) => setIn("detectors", k, v)} />)}
          <p className="mt-2 text-xs text-slate-500">Identity matching is not available: it would need face recognition, which this platform does not do.</p>
        </Card>
        <Card title="Detection thresholds">
          {THRESHOLDS.map(([k, label, unit, step]) => <Num key={k} label={label} unit={unit} step={step} value={cfg.thresholds[k]} onChange={(v) => setIn("thresholds", k, v)} />)}
        </Card>
        <div className="space-y-4">
          <Card title="Reminders and pause rule">
            <Num label="The same reminder is not repeated within" unit="s" step={5} value={cfg.warning_cooldown_s} onChange={(v) => setCfg({ ...cfg, warning_cooldown_s: v })} />
            <Num label="Pause the interview when no face is visible for (0 = never)" unit="s" step={5} value={cfg.pause_on_face_absent_s} onChange={(v) => setCfg({ ...cfg, pause_on_face_absent_s: v })} />
            <p className="text-xs text-slate-500">A pause is recorded and the candidate resumes it. Interviews are never ended or failed automatically.</p>
          </Card>
          <Card title="Security summary (risk weights)">
            {Object.entries(data.risk_rules).map(([k, label]) => <Num key={k} label={label} unit="pts" step={0.5} value={cfg.risk_weights[k]} onChange={(v) => setIn("risk_weights", k, v)} />)}
            <div className="mt-2 border-t border-slate-100 pt-2">
              {["low", "moderate", "high"].map((b) => <Num key={b} label={`Band "${b}" from`} unit="pts" step={0.5} value={cfg.risk_bands[b]} onChange={(v) => setIn("risk_bands", b, v)} />)}
            </div>
          </Card>
        </div>
        <Card title="Severity caps (highest severity an event type may receive)" className="lg:col-span-2">
          <div className="grid gap-x-6 sm:grid-cols-2">
            {data.event_types.map((t) => (
              <label key={t} className="flex items-center justify-between gap-3 py-1 text-sm">
                <span className="text-slate-700">{data.labels[t]}</span>
                <select className="input w-32 py-1" value={cfg.severity_caps[t] || ""} aria-label={`Cap for ${data.labels[t]}`}
                  onChange={(e) => setCfg((c) => { const caps = { ...c.severity_caps }; if (e.target.value) caps[t] = e.target.value; else delete caps[t]; return { ...c, severity_caps: caps }; })}>
                  <option value="">no cap</option>{["info", "low", "medium", "high"].map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
            ))}
          </div>
        </Card>
      </div>
      <div className="flex gap-2">
        <Button onClick={save} loading={busy}>Save security settings</Button>
        <Button variant="secondary" onClick={() => setCfg(data.defaults)}>Reset to defaults (not saved yet)</Button>
      </div>
    </div>
  );
}
