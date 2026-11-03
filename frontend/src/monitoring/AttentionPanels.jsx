/*
 * Estimated visual attention toward the interview screen.
 *  - AttentionCard: the live figure during the interview (rolling window), with the tracking status.
 *  - AttentionReport: the stored whole-interview figure, coverage, timeline and limits (candidate and reviewers).
 * Both say "estimated", never show an old value as current, and never use colour alone for the status.
 */
import { Crosshair } from "lucide-react";

// What the tracker is doing, in the words of the monitoring states (never "active" unless frames are being analysed).
export function trackingLabel({ status, cameraOn, cameraLost }) {
  if (cameraLost) return { text: "Camera disconnected", ok: false };
  if (status?.analysis === "stopped") return { text: "Interview monitoring stopped", ok: false };
  if (status?.analysis === "unavailable") return { text: "Eye tracking temporarily unavailable", ok: false };
  if (!cameraOn) return { text: "Camera permission required or camera off", ok: false };
  if (!status || status.analysis === "starting") return { text: "Camera initializing", ok: false };
  const a = status.attention;
  if (a?.calibrating || status.gaze === "calibrating") return { text: "Calibrating: look naturally toward the screen", ok: false };
  if (status.faces === 0) return { text: "Face not detected", ok: false };
  if (a?.state === "paused") return { text: "Interview paused", ok: false };
  if (a && ["low_confidence", "unavailable", "gap"].includes(a.state)) return { text: "Tracking quality is low", ok: false };
  return { text: "Eye tracking active", ok: true };
}

export function AttentionCard({ status, cameraOn, cameraLost }) {
  const a = status?.attention;
  if (!a && status?.analysis !== "starting") return null;
  const t = trackingLabel({ status, cameraOn, cameraLost });
  const face = status?.faces === 1 ? (status.edge ? "partly visible" : "detected") : status?.faces > 1 ? "more than one" : "not detected";
  const secs = Math.round((a?.windowMs ?? 30000) / 1000);
  return (
    <section aria-label="Visual attention" className="rounded-xl border border-slate-200 bg-white/70 px-4 py-2.5 text-xs text-slate-700 backdrop-blur">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="flex items-center gap-1 font-semibold uppercase tracking-wide text-slate-500"><Crosshair size={13} /> Visual attention</span>
        {a?.pct != null ? (
          <span className="flex items-center gap-2">
            <span className="text-lg font-bold text-slate-900" aria-label={`Estimated visual attention ${a.pct} percent over the last ${secs} seconds`}>{a.pct}%</span>
            <span className="h-1.5 w-28 overflow-hidden rounded-full bg-slate-200" role="progressbar" aria-valuemin={0} aria-valuemax={100}
              aria-valuenow={a.pct} aria-label="Estimated visual attention">
              <span className="block h-full bg-gradient-to-r from-brand-500 to-violet-500 shadow-[0_0_10px_rgb(129_140_248/0.6)] transition-[width] duration-500" style={{ width: `${a.pct}%` }} />
            </span>
          </span>
        ) : a?.collecting ? (
          <span className="font-medium text-slate-600">Collecting observations…</span>
        ) : (
          <span className="font-medium text-slate-600">Attention estimate temporarily unavailable.</span>
        )}
        <span>Tracking: <b>{t.text}</b></span>
        <span>Face: <b>{face}</b></span>
        <span>Coverage: <b>{a?.coveragePct != null ? `${a.coveragePct}%` : "n/a"}</b></span>
        <span>Window: <b>{secs} s</b></span>
        {status?.recalibrate && !a?.calibrating && (
          <button type="button" className="underline" onClick={status.recalibrate}>Recalibrate</button>
        )}
      </div>
      {a && !a.calibrated && !a.calibrating && (
        <p className="mt-1 text-amber-800">Not calibrated, so the estimate is less reliable. Use Recalibrate while looking naturally at the screen.</p>
      )}
      <p className="mt-1 text-slate-500">An estimate of looking toward the screen from head and eye direction. Natural movement is fine; it does not show whether you are listening or understanding.</p>
    </section>
  );
}

const mmss = (ms) => { const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const REASON = { face_not_visible: "face not visible", low_confidence: "low tracking confidence", unavailable: "tracking unavailable", gap: "missing camera frames" };

/** The whole-interview figure. `a` = the "attention" object from the monitoring report API (null = not used). */
export function AttentionReport({ a }) {
  if (!a) return null;
  if (!a.available) {
    return (
      <section className="rounded-lg border border-slate-200 p-3 text-sm">
        <h3 className="font-semibold">Estimated visual attention</h3>
        <p className="mt-1 text-slate-600">{a.reason}</p>
      </section>
    );
  }
  const reasons = Object.entries(a.unobserved_by_reason).filter(([, v]) => v > 0);
  return (
    <section className="space-y-3 rounded-xl border border-slate-200 bg-white/60 p-4 text-sm" aria-label="Estimated visual attention">
      <div>
        <h3 className="font-semibold">{a.label}</h3>
        <p className="text-xs text-slate-500">Measured in the candidate&apos;s browser from webcam observations; not tamper-proof; shown separately from interview scores.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="Overall estimate" value={a.overall_attention_pct != null ? `${a.overall_attention_pct}%` : "Not enough data"}
          hint="toward screen ÷ (toward + away), valid time only" />
        <Stat label="Monitoring coverage" value={a.coverage_pct != null ? `${a.coverage_pct}%` : "n/a"} hint={`${mmss(a.valid_observation_ms)} valid of ${mmss(a.monitored_ms)} monitored`} />
        <Stat label="Looking away (total)" value={mmss(a.looking_away_ms)} hint={`${a.prolonged_deviation_events} prolonged deviation event${a.prolonged_deviation_events === 1 ? "" : "s"}`} />
        <Stat label="Not observed" value={mmss(a.unobserved_ms)} hint={reasons.length ? reasons.map(([k, v]) => `${REASON[k]} ${mmss(v)}`).join(", ") : "tracking worked throughout"} />
      </div>
      <ul className="list-inside list-disc text-xs text-slate-600">
        <li>Interview length {a.interview_duration_ms != null ? mmss(a.interview_duration_ms) : "unknown"}; monitored {mmss(a.monitored_ms)}{a.paused_ms ? `; paused ${mmss(a.paused_ms)}` : ""}.</li>
        <li>Camera interruptions: {a.camera_interruptions}. Tracking failures: {a.tracking_failures}. Monitoring runs (page loads): {a.monitor_runs}.</li>
        {a.uncalibrated_runs > 0 && <li>{a.uncalibrated_runs} run(s) were not calibrated; absolute angle limits were used, so treat them with extra care.</li>}
        <li>Time without a usable face or tracking is <b>not</b> counted as attention or as looking away.</li>
      </ul>
      <Timeline a={a} />
      <p className="text-xs text-slate-500">{a.limitations}</p>
    </section>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-100/50 p-2.5">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
      <p className="text-xs text-slate-500">{hint}</p>
    </div>
  );
}

/** One column per 10 s: height = attention in that bucket; a grey column = no usable observation. */
function Timeline({ a }) {
  if (!a.timeline?.length) return null;
  const last = a.timeline[a.timeline.length - 1].start_ms + a.bucket_ms;
  const byStart = new Map(a.timeline.map((b) => [b.start_ms, b]));
  const cols = [];
  for (let t = 0; t < last; t += a.bucket_ms) cols.push(byStart.get(t) || { start_ms: t, none: true });
  return (
    <div>
      <p className="mb-1 text-xs font-medium text-slate-600">Attention timeline (10-second blocks)</p>
      <div className="flex h-20 items-end gap-px overflow-x-auto rounded bg-slate-50 p-1" role="img"
        aria-label={`Attention timeline. ${cols.filter((c) => c.attention_pct != null).length} of ${cols.length} blocks have a measurement.`}>
        {cols.map((c) => {
          const known = c.attention_pct != null;
          const label = `${mmss(c.start_ms)}: ${known ? `${c.attention_pct}% toward the screen` : "no usable observation"}`;
          return (
            <div key={c.start_ms} title={label} className="flex h-full w-2 shrink-0 items-end">
              <div className={known ? (c.attention_pct >= 60 ? "bg-emerald-500" : "bg-amber-500") : "bg-slate-300"}
                style={{ height: known ? `${Math.max(4, c.attention_pct)}%` : "8%", width: "100%" }} />
            </div>
          );
        })}
      </div>
      <p className="mt-1 text-xs text-slate-500">Green: mostly toward the screen. Amber: less than 60%. Grey: nothing could be observed (not counted as either). Hover a block for its time.</p>
    </div>
  );
}
