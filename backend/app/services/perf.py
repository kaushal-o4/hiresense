"""Timing of each interview-pipeline step, so the real bottleneck is visible (admin → AI & Monitoring → Performance).

What is recorded: the step name (e.g. "llm.interview_question", "tts.first_segment", "turn.total"), its duration,
success/failure, and numeric details (token counts, Ollama's load/prompt/generation split). What is NEVER recorded:
questions, answers, transcripts, resume text, audio or camera data. The same rule applies to the log line.

Writes use their own short database session so they never interfere with the request's transaction.
"""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .. import database
from ..models import PerfMetric

log = logging.getLogger("hiresense.perf")

# Metrics the browser may report (POST /api/perf/client). Anything else is rejected.
CLIENT_METRICS = {
    "client.stt_roundtrip": "Recording stopped → transcript shown (upload + Whisper)",
    "client.stt_partial": "Partial transcript of one speech segment",
    "client.tts_first_audio": "Request sent → first interviewer audio playing",
    "client.answer_to_next_question": "Answer submitted → next question starts playing",
    "client.answer_to_first_text": "Answer submitted → first words of the next question on screen",
    "client.first_question_audio": "Start pressed → first question audio playing",
    "client.end_of_speech": "Candidate stopped talking → recording closed (silence timeout)",
    "client.repeat_submit": "Duplicate submission blocked in the browser",
}
ALLOWED_META = {"tokens_in", "tokens_out", "queue_ms", "load_ms", "prompt_ms", "generate_ms", "first_token_ms",
                "segments", "audio_s", "chars", "mode", "status", "attempt", "cached", "words", "kind", "preempted"}


def _clean_meta(meta: dict | None) -> dict | None:
    if not meta:
        return None
    out = {}
    for k, v in meta.items():
        if k in ALLOWED_META and (isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) <= 20)):
            out[k] = v
    return out or None


def record(metric: str, duration_ms: float, ok: bool = True, source: str = "server", **meta) -> None:
    """Store one measurement. Never raises (monitoring must not break the interview)."""
    from ..config import get_settings
    if not get_settings().perf_metrics_enabled:
        return
    clean = _clean_meta(meta)
    log.info("perf metric=%s ms=%d ok=%s %s", metric, duration_ms, ok,
             " ".join(f"{k}={v}" for k, v in (clean or {}).items()))
    try:
        db = database.SessionLocal()
        try:
            db.add(PerfMetric(metric=metric[:60], duration_ms=int(max(0, min(duration_ms, 3_600_000))), ok=ok,
                              source=source, meta=clean))
            db.commit()
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - metrics are best-effort
        log.debug("perf metric not stored", exc_info=True)


@contextmanager
def timer(metric: str, **meta):
    """with perf.timer("tts.segment"): ...  - records the duration, and ok=False if the block raises."""
    t = time.perf_counter()
    ok = True
    try:
        yield meta  # the block may add numeric details: meta["segments"] = 3
    except BaseException:
        ok = False
        raise
    finally:
        record(metric, (time.perf_counter() - t) * 1000, ok, **meta)


def _pct(xs: list[int], p: float) -> int | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def summary(db, hours: int = 24) -> list[dict]:
    """Per metric: count, failures, average, p50, p95, max, plus averaged numeric details (e.g. token counts)."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = db.execute(select(PerfMetric.metric, PerfMetric.duration_ms, PerfMetric.ok, PerfMetric.source,
                             PerfMetric.meta).where(PerfMetric.created_at >= since)).all()
    groups: dict[str, dict] = {}
    for metric, ms, ok, source, meta in rows:
        g = groups.setdefault(metric, {"metric": metric, "source": source, "ok": [], "failed": 0, "meta": {}})
        if ok:
            g["ok"].append(ms)
        else:
            g["failed"] += 1
        for k, v in (meta or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                g["meta"].setdefault(k, []).append(v)
    out = []
    for g in groups.values():
        xs = g["ok"]
        out.append({"metric": g["metric"], "source": g["source"],
                    "description": CLIENT_METRICS.get(g["metric"]) or SERVER_METRICS.get(g["metric"].split(":")[0], ""),
                    "count": len(xs) + g["failed"], "failed": g["failed"],
                    "avg_ms": round(sum(xs) / len(xs)) if xs else None, "p50_ms": _pct(xs, 50),
                    "p95_ms": _pct(xs, 95), "max_ms": max(xs) if xs else None,
                    "avg_details": {k: round(sum(v) / len(v), 1) for k, v in g["meta"].items()}})
    return sorted(out, key=lambda r: r["metric"])


SERVER_METRICS = {
    "llm.interview_question": "Local LLM: write the next question (whole reply)",
    "llm.interview_question.first_text": "Local LLM: first words of the question available (streaming)",
    "llm.answer_scoring": "Local LLM: score the answer (fast step)",
    "llm.answer_feedback": "Local LLM: detailed tips (background, can be paused)",
    "llm.interview_report": "Local LLM: final report",
    "llm.warmup": "Load the model into memory before the interview",
    "tts.segment": "Kokoro: synthesise one sentence",
    "tts.first_segment": "Turn start → first audio sentence ready on the server",
    "tts.request": "/voice/speak (whole text)",
    "stt.transcribe": "Whisper: transcribe one recording",
    "turn.total": "Server: answer received → next question fully sent (stream)",
    "turn.to_first_audio": "Server: answer received → first question audio sent",
    "turn.duplicate": "Duplicate answer/turn request rejected",
    "answer.submit": "Classic /answer endpoint (text mode): score + next question",
}
