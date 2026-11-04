// Score bands shown next to 0-100 AI interview scores (mirrors backend/app/services/scoring_bands.py).
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
