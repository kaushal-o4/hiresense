// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/PlacementReadinessCard.jsx
//
// FILE PURPOSE:
// Shows the student's placement-readiness score: overall score, level and per-area bars.
//
// WHAT THIS FILE DOES:
// 1. Shows the level as a coloured pill (Placement ready / Almost ready / Needs preparation).
// 2. Shows bars for interviews, assessments, English, resume and profile.
//
// HOW THIS FILE WORKS:
// It only displays the readiness object; the score is calculated on the backend
// (student_performance_insights.py).
//
// IMPORTANT FUNCTIONS:
//    - ReadinessCard()
//        Card with the readiness score and area bars.
//
// INPUT:
// Prop: readiness (from the dashboard or report API).
//
// OUTPUT:
// Rendered card.
//
// FILES CONNECTED TO THIS FILE:
//    Uses: components/SharedUiComponents.jsx
//    Used by: pages/student/PerformanceReport.jsx, pages/student/StudentDashboard.jsx
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
/*
 * Placement-readiness score card (overall score ring, level and per-area meters), shown on the student
 * dashboard and in the performance report. The score itself is computed by the backend (services/student_progress/student_performance_insights.py).
 */

import { Card, Pill } from "./SharedUiComponents";
import { Meter, ScoreRing } from "./DashboardWidgets";

const LEVEL = {
  ready: { tone: "green", label: "Placement ready" },
  almost: { tone: "amber", label: "Almost ready" },
  not_ready: { tone: "red", label: "Needs preparation" },
};
const NAMES = { interviews: "Mock interviews", assessments: "Assessments", english: "English", resume: "Resume", profile: "Profile completeness" };

export function ReadinessCard({ readiness, className = "" }) {
  if (!readiness) return null;
  const lv = LEVEL[readiness.level] || LEVEL.not_ready;
  return (
    <Card title="Placement readiness" className={className} actions={<Pill dot tone={lv.tone}>{lv.label}</Pill>}>
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4 sm:flex-col sm:items-center sm:gap-2">
          <ScoreRing value={readiness.score} tone={lv.tone} size={120} />
          <p className="max-w-[10rem] text-xs text-slate-500 sm:text-center">Ready from <span className="num font-medium text-slate-700">{readiness.threshold}</span></p>
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          {Object.entries(readiness.weights).map(([k, w]) => (
            <Meter key={k} label={`${NAMES[k]} · ${Math.round(w * 100)}%`} tone="auto"
              value={readiness.components[k] == null ? null : readiness.components[k]} />
          ))}
        </div>
      </div>
      <p className="mt-5 border-t border-slate-100 pt-3 text-xs leading-relaxed text-slate-500">
        Weighted average of your scores; activities you haven't done yet count as 0.
        {readiness.missing.length > 0 && ` Not started yet: ${readiness.missing.map((m) => NAMES[m].toLowerCase()).join(", ")}.`}
      </p>
    </Card>
  );
}
