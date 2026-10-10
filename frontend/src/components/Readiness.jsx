import { Card, Pill, ScoreBar } from "./ui";

const LEVEL = {
  ready: { tone: "green", label: "Placement ready" },
  almost: { tone: "amber", label: "Almost ready" },
  not_ready: { tone: "red", label: "Needs preparation" },
};
const NAMES = { interviews: "Mock interviews", assessments: "Assessments", english: "English", resume: "Resume", profile: "Profile completeness" };

export function ReadinessCard({ readiness, className = "" }) {
  if (!readiness) return null;
  const lv = LEVEL[readiness.level];
  return (
    <Card title="Placement readiness score" className={className} actions={<Pill tone={lv.tone}>{lv.label}</Pill>}>
      <div className="flex flex-wrap items-center gap-6">
        <div className="relative h-28 w-28 shrink-0">
          <svg viewBox="0 0 36 36" className="h-28 w-28 -rotate-90">
            <circle cx="18" cy="18" r="15.9" fill="none" stroke="#e2e8f0" strokeWidth="3.2" />
            <circle cx="18" cy="18" r="15.9" fill="none" strokeWidth="3.2" strokeLinecap="round"
              stroke={readiness.level === "ready" ? "#10b981" : readiness.level === "almost" ? "#f59e0b" : "#ef4444"}
              strokeDasharray={`${readiness.score} 100`} />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold">{Math.round(readiness.score)}</span>
            <span className="text-[10px] text-slate-500">of 100</span>
          </div>
        </div>
        <div className="min-w-[14rem] flex-1 space-y-2">
          {Object.entries(readiness.weights).map(([k, w]) => (
            <ScoreBar key={k} label={`${NAMES[k]} (${Math.round(w * 100)}%)`} value={readiness.components[k] == null ? null : Math.round(readiness.components[k])} />
          ))}
        </div>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        Weighted average of your scores; activities you haven't done yet count as 0. "Placement ready" from {readiness.threshold}.
        {readiness.missing.length > 0 && ` Not started yet: ${readiness.missing.map((m) => NAMES[m].toLowerCase()).join(", ")}.`}
      </p>
    </Card>
  );
}
