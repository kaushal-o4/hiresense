/* Integrity roll-up for one candidate (counts only), shown apart from performance. Used by compare and report. */

import { ShieldCheck } from "lucide-react";
import { Pill } from "../../components/ui";

const BAND_TONE = { none: "green", low: "blue", moderate: "amber", high: "red" };

export default function IntegrityOverview({ data, compact = false }) {
  if (!data) return null;
  if (!data.visible) {
    return <p className="text-xs text-slate-500">{data.reason || "Not available."}</p>;
  }
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <ShieldCheck size={14} className="text-slate-400" aria-hidden />
        <Pill dot tone={BAND_TONE[data.highest_band?.code] || "gray"}>Highest: {data.highest_band?.label}</Pill>
        <span className="text-xs text-slate-500">
          {data.monitored_sessions} monitored interview{data.monitored_sessions === 1 ? "" : "s"}
          {data.needs_review > 0 && ` · ${data.needs_review} awaiting review`}
          {data.hidden_sessions > 0 && ` · ${data.hidden_sessions} not shared`}
        </span>
      </div>
      {!compact && data.sessions?.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
          {data.sessions.map((s) => (
            <li key={s.session_id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-xs">
              <span className="text-slate-700">{s.job_role}</span>
              <span className="flex items-center gap-2 text-slate-500">
                {s.events} signal{s.events === 1 ? "" : "s"}
                <Pill tone={BAND_TONE[s.band?.code] || "gray"}>{s.band?.label}</Pill>
              </span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-[11px] leading-relaxed text-slate-500">{data.disclaimer}</p>
    </div>
  );
}
