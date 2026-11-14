// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/scoreBandLabel.js
//
// FILE PURPOSE:
// Turns a 0-100 interview score into a band label such as 'Strong (75-89)'.
//
// WHAT THIS FILE DOES:
// 1. Defines five bands: Outstanding, Strong, Competent, Developing, Needs work.
// 2. Clamps the score to 0-100 and returns the matching band.
//
// HOW THIS FILE WORKS:
// Same table as the backend file score_band_labels.py, so both sides show the same labels.
//
// IMPORTANT FUNCTIONS:
//    - scoreBand()
//        Returns {key, label, min, max, text} for a score, or null.
//
// INPUT:
// A score number.
//
// OUTPUT:
// A band object.
//
// FILES CONNECTED TO THIS FILE:
//    Used by: pages/student/InterviewSession.jsx, pages/student/LiveVoiceInterview.jsx
//    Tested by: components/scoreBandLabel.test.js
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
// Score bands shown next to 0-100 AI interview scores (mirrors backend/app/services/interview/score_band_labels.py).
// An AI score has a few points of noise, so students see "Strong (75-89)" rather than treating 82 vs 84 as real.

const BANDS = [
  [90, "outstanding", "Outstanding"],
  [75, "strong", "Strong"],
  [60, "competent", "Competent"],
  [40, "developing", "Developing"],
  [0, "needs_work", "Needs work"],
];

export function scoreBand(score) {
  if (score == null || Number.isNaN(Number(score))) return null;
  const s = Math.max(0, Math.min(100, Number(score)));
  let upper = 100;
  for (const [lo, key, label] of BANDS) {
    if (s >= lo) return { key, label, min: lo, max: upper, text: `${label} (${lo}-${upper})` };
    upper = lo - 1;
  }
  return null;
}
