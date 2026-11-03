"""Estimated visual attention toward the interview screen: storage rules and the report.

The browser measures it (monitoring/attentionMeter.js) from webcam observations and sends cumulative TIME TOTALS, not
frames or landmarks. One monitor run ("epoch") sends running totals; a page reload starts a new epoch, so the stored
value is the sum over epochs. Because the browser can be modified, the server only accepts what is plausible and
labels the source "client": totals cannot decrease within an epoch, cannot add up to more than the interview clock
allows, and only the time totals and 10-second buckets are kept.

Definition (the same for the live indicator and this report):

    attention % = time looking toward the screen / (time toward + time away)      [valid observations only]
    coverage %  = (time toward + time away) / (time toward + away + unobserved)   [monitored time]

Unobserved time (face not visible, low confidence, tracking unavailable, missing frames) is reported separately and is
never counted as attention or as looking away. Paused and calibration time are outside both.
"""
from __future__ import annotations

from typing import Any

BUCKET_MS = 10_000
MIN_VALID_MS = 5_000          # below this much valid time no percentage is shown
MAX_EPOCHS = 20               # monitor runs kept per interview (page reloads)
MAX_BUCKETS = 720             # 2 hours of 10 s buckets per epoch
CLOCK_SLACK_MS = 30_000
REASONS = ("face_not_visible", "low_confidence", "unavailable", "gap")
TOTALS = ("toward_ms", "away_ms", "unobserved_ms", "paused_ms", "calibrating_ms")
LABEL = "Estimated visual attention toward the interview screen"
LIMITATIONS = (
    "This is an estimate from head direction and eye direction seen by a webcam. It does not show whether the "
    "candidate was listening, understanding, thinking or following the rules: people look away while they think, "
    "read notes they are allowed to use, or sit beside the camera. Glasses, lighting, camera position and a low-quality "
    "webcam change the result. The numbers are sent by the candidate's browser and are not tamper-proof. It must not "
    "be the only basis for any decision about a candidate.")


def merge(monitoring: dict | None, epoch: str, snap: dict[str, Any], elapsed_ms: int | None) -> tuple[dict | None, str]:
    """Return (updated attention record, "") or (None, reason) if the snapshot is not acceptable."""
    if elapsed_ms is None:
        return None, "no_clock"
    record = dict((monitoring or {}).get("attention") or {})
    epochs = dict(record.get("epochs") or {})
    if epoch not in epochs and len(epochs) >= MAX_EPOCHS:
        return None, "too_many_runs"
    previous = epochs.get(epoch) or {}
    for k in TOTALS:  # running totals inside one run never go down
        if snap[k] < previous.get(k, 0):
            return None, "stale"
    if snap["unobserved_ms"] < sum(snap["by_reason"].values()) - 1:
        return None, "inconsistent"
    epochs[epoch] = {**{k: snap[k] for k in TOTALS}, "by_reason": snap["by_reason"], "buckets": snap["buckets"],
                     "window_ms": snap["window_ms"], "calibrated": snap.get("calibrated")}
    total = sum(sum(e.get(k, 0) for k in TOTALS) for e in epochs.values())
    if total > elapsed_ms + CLOCK_SLACK_MS:
        return None, "exceeds_interview_time"
    record.update(epochs=epochs, source="client", version=1)
    return record, ""


def _sum_epochs(record: dict) -> dict:
    out: dict[str, Any] = {k: 0 for k in TOTALS}
    reasons = {k: 0 for k in REASONS}
    buckets: dict[int, list[int]] = {}
    for e in (record.get("epochs") or {}).values():
        for k in TOTALS:
            out[k] += int(e.get(k, 0))
        for k, v in (e.get("by_reason") or {}).items():
            if k in reasons:
                reasons[k] += int(v)
        for idx, t, a, u in e.get("buckets") or []:
            b = buckets.setdefault(int(idx), [0, 0, 0])
            b[0] += int(t)
            b[1] += int(a)
            b[2] += int(u)
    out["by_reason"] = reasons
    out["buckets"] = buckets
    return out


def pct(toward: int, away: int) -> int | None:
    valid = toward + away
    return round(100 * toward / valid) if valid >= MIN_VALID_MS else None


def report(monitoring: dict | None, events: list, duration_ms: int | None = None) -> dict | None:
    """The attention section of the monitoring report, or None if attention tracking was not used/recorded."""
    m = monitoring or {}
    record = m.get("attention")
    if not ((m.get("features") or {}).get("attention") or record):  # consent withdrawn later keeps earlier data
        return None
    if not record or not record.get("epochs"):
        return {"label": LABEL, "available": False, "limitations": LIMITATIONS,
                "reason": "No attention measurements were received for this interview."}
    t = _sum_epochs(record)
    valid = t["toward_ms"] + t["away_ms"]
    monitored = valid + t["unobserved_ms"]
    timeline = []
    for idx in sorted(t["buckets"]):
        toward, away, unobserved = t["buckets"][idx]
        timeline.append({"start_ms": idx * BUCKET_MS, "toward_ms": toward, "away_ms": away, "unobserved_ms": unobserved,
                         "attention_pct": pct(toward, away) if toward + away >= 2_000 else None})
    away_events = [e for e in events if e.event_type == "attention_away"]
    return {
        "label": LABEL, "available": True, "source": "client",
        "overall_attention_pct": pct(t["toward_ms"], t["away_ms"]),
        "valid_observation_ms": valid, "looking_toward_ms": t["toward_ms"], "looking_away_ms": t["away_ms"],
        "unobserved_ms": t["unobserved_ms"], "unobserved_by_reason": t["by_reason"],
        "monitored_ms": monitored, "coverage_pct": round(100 * valid / monitored) if monitored else None,
        "paused_ms": t["paused_ms"], "calibrating_ms": t["calibrating_ms"],
        "interview_duration_ms": duration_ms,
        "monitor_runs": len(record["epochs"]),
        "uncalibrated_runs": sum(1 for e in record["epochs"].values() if e.get("calibrated") is False),
        "window_ms": next(iter(record["epochs"].values())).get("window_ms"),
        "prolonged_deviation_events": len(away_events),
        "prolonged_deviation_ms": sum(e.duration_ms or 0 for e in away_events),
        "tracking_failures": sum(1 for e in events if e.event_type in ("monitoring_interrupted", "monitoring_unavailable")),
        "camera_interruptions": sum(1 for e in events if e.event_type in ("camera_interrupted", "permission_revoked")),
        "timeline": timeline, "bucket_ms": BUCKET_MS,
        "definition": "attention % = time looking toward the screen / (time toward + time away); unobserved time is "
                      "reported separately and is not counted as either.",
        "limitations": LIMITATIONS,
        "sufficient_data": valid >= MIN_VALID_MS,
    }
