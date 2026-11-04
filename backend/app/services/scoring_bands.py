"""Score bands shown next to 0-100 interview scores.

An AI score has a few points of noise (eval/calibrate_scoring.py measures it), so students see a band such as
"Strong (75-89)" next to the number instead of treating 82 vs 84 as meaningful. The same table is mirrored in
frontend/src/components/scoreBand.js. Bands never depend on the interviewer persona.
"""

BANDS = (  # (lowest score in the band, key, label)
    (90, "outstanding", "Outstanding"),
    (75, "strong", "Strong"),
    (60, "competent", "Competent"),
    (40, "developing", "Developing"),
    (0, "needs_work", "Needs work"),
)


def band(score: float | None) -> dict | None:
    """{"key", "label", "min", "max", "text"} for a 0-100 score, or None when there is no score."""
    if score is None:
        return None
    s = max(0.0, min(100.0, float(score)))
    upper = 100
    for lo, key, label in BANDS:
        if s >= lo:
            return {"key": key, "label": label, "min": lo, "max": upper, "text": f"{label} ({lo}-{upper})"}
        upper = lo - 1
    return None  # unreachable: the last band starts at 0
