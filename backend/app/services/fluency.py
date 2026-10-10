"""Deterministic delivery (fluency) measures for spoken practice - no AI involved.

Inputs: the transcript, and - when the answer was recorded through the app's own recorder and transcribed by local
Whisper - measurements taken from the audio itself (duration, voiced seconds, pauses between stretches of speech).

The delivery score is kept separate from the AI's content/language feedback: it describes HOW the student spoke
(pace, fillers, hesitation, length), not whether the content was good.

Limitations (shown to the student): Whisper base.en often leaves out "um"/"uh", so filler counts are usually an
UNDER-estimate; pauses are measured from loudness, so background noise can hide a pause; typed answers have no
timing at all.
"""
from __future__ import annotations

import re

FILLERS = re.compile(r"\b(um+|uh+|erm+|hmm+|ah+|you know|i mean|sort of|kind of|basically|like,)", re.IGNORECASE)
PACE_RANGE = (100, 165)  # comfortable words per minute for an interview answer
LIMITATIONS = ("Speech recognition often leaves out 'um' and 'uh', so the filler count is usually lower than what "
               "you actually said. Pauses are measured from loudness, so background noise can hide them. Accent is "
               "never measured.")


def _repetitions(text: str) -> int:
    words = re.findall(r"[a-z']+", text.lower())
    return sum(1 for a, b in zip(words, words[1:]) if a == b and a not in ("very", "no", "yes", "bye", "ha"))


def analyse(transcript: str, audio: dict | None = None, target_seconds: int | None = None) -> dict:
    text = " ".join((transcript or "").split())
    words = len(text.split())
    fillers = [m.group(0).strip(",").lower() for m in FILLERS.finditer(text)]
    reps = _repetitions(text)
    a = audio or {}
    # speaking time = first word to last word (silence before starting / after finishing is not counted)
    duration = a.get("spoken_span_s") or a.get("duration")
    timed = bool(duration) and duration > 1
    minutes = (duration / 60) if timed else max(words / 130, 0.1)  # untimed: estimate from a typical pace
    out = {
        "words": words,
        "timed": timed,
        "duration_s": round(duration, 1) if timed else None,
        "pace_wpm": round(words / duration * 60) if timed and words else None,
        "fillers": len(fillers),
        "filler_words": sorted(set(fillers)),
        "fillers_per_min": round(len(fillers) / minutes, 1),
        "repetitions": reps,
        "longest_pause_s": a.get("longest_pause_s") if timed else None,
        "long_pauses": a.get("long_pauses") if timed else None,
        "target_seconds": target_seconds,
        "limitations": LIMITATIONS,
    }
    tips, score, parts = [], 0.0, 0.0

    def part(weight, value):  # value 0..1
        nonlocal score, parts
        score += weight * max(0.0, min(1.0, value))
        parts += weight

    if out["pace_wpm"] is not None:
        lo, hi = PACE_RANGE
        p = out["pace_wpm"]
        part(30, 1.0 if lo <= p <= hi else max(0.0, 1 - (lo - p) / 60 if p < lo else 1 - (p - hi) / 60))
        if p < lo:
            tips.append(f"Your pace was {p} words per minute - a little slow. Try linking your sentences without "
                        "stopping between every few words.")
        elif p > hi:
            tips.append(f"Your pace was {p} words per minute - quite fast. Slow down slightly and pause at the end "
                        "of each idea so the listener can follow.")
    fpm = out["fillers_per_min"]
    part(25, 1 - max(0.0, fpm - 2) / 8)
    if fpm > 3:
        tips.append(f"About {fpm:g} filler words per minute ({', '.join(out['filler_words'][:4])}). Replace them "
                    "with a short silent pause - silence sounds more confident than 'basically' or 'um'.")
    if out["long_pauses"] is not None:
        per_min = out["long_pauses"] / max(minutes, 0.1)
        part(25, 1 - max(0.0, per_min - 1) / 4)
        if per_min > 2:
            tips.append(f"{out['long_pauses']} long pauses (over 1.5 s). Before you start, decide your first point "
                        "and your example, so you don't stop to search for ideas mid-answer.")
    part(10, 1 - reps / 5)
    if reps >= 2:
        tips.append("You repeated a few words ('I I', 'the the'). Finish the sentence you started instead of "
                    "restarting it.")
    if target_seconds and timed:
        ratio = duration / target_seconds
        part(10, 1.0 if 0.75 <= ratio <= 1.25 else max(0.0, 1 - abs(ratio - 1)))
        if ratio < 0.75:
            tips.append(f"You spoke for {round(duration)} s of the {target_seconds} s target. Add one concrete "
                        "example or result to fill the time with substance.")
        elif ratio > 1.25:
            tips.append(f"You spoke for {round(duration)} s - over the {target_seconds} s target. Lead with your main "
                        "point and cut background detail.")
    elif words < 40:
        part(10, words / 40)
        tips.append("A short answer. In interviews, aim for 45-90 seconds: point, example, result.")
    else:
        part(10, 1.0)
    out["delivery_score"] = round(score / parts * 100) if parts else None
    out["tips"] = tips[:4] or ["Smooth delivery - keep this pace and structure."]
    return out


def compare(current: dict, previous: dict | None) -> dict | None:
    """Change since the previous attempt at the same prompt (retry drills)."""
    if not previous:
        return None
    keys = ("delivery_score", "pace_wpm", "fillers_per_min", "long_pauses", "words")
    return {k: {"before": previous.get(k), "after": current.get(k)} for k in keys
            if previous.get(k) is not None and current.get(k) is not None}
