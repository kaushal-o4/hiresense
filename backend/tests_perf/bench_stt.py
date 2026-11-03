"""Speech-to-text latency on this computer: how long after the candidate stops talking until the text is ready.

Makes spoken answers with the app's own TTS voice (Kokoro), then times the configured STT engine on them, and checks
the words come back (word error rate against the script). Run:  python tests_perf/bench_stt.py [engine ...]
Engines: whatever STT_ENGINE/STT_MODEL say, unless names are given (e.g. "transformers:openai/whisper-base.en",
"faster:base.en", "faster:small.en"). Clips are cached in tests_perf/results/stt_clips/.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("TTS_ENABLED", "true")
os.environ.setdefault("STT_ENABLED", "true")

SCRIPTS = {
    "short_3s": "I have worked with Python for about two years.",
    "medium_8s": "In my final year project I built a placement portal with React and FastAPI. "
                 "I handled the backend and the database design.",
    "segment_15s": "A list in Python is ordered and mutable, so you can change it after creating it. "
                   "A tuple is also ordered but immutable, which makes it hashable, so it can be used as a "
                   "dictionary key. I usually pick a tuple for fixed records like coordinates.",
}
CLIPS = Path(__file__).resolve().parent / "results" / "stt_clips"


def words(t: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", t.lower()).split()


def wer(ref: str, hyp: str) -> float:
    r, h = words(ref), words(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)] / max(1, len(r))


def clips() -> dict[str, bytes]:
    CLIPS.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, text in SCRIPTS.items():
        f = CLIPS / f"{name}.wav"
        if not f.exists():
            from app.services import tts
            f.write_bytes(base64.b64decode(tts.synthesize(text)["audio_wav_b64"]))
        out[name] = f.read_bytes()
    return out


def main() -> None:
    from app.config import get_settings
    from app.services import stt
    data = clips()
    engines = sys.argv[1:] or [f"{get_settings().stt_engine}:{get_settings().stt_model}"]
    results = []
    for spec in engines:
        engine, model = spec.split(":", 1)
        s = get_settings()
        s.stt_engine, s.stt_model = engine, model
        stt.reset()
        t = time.perf_counter()
        stt.warmup()
        load_s = time.perf_counter() - t
        print(f"\n== {spec}  (load {load_s:.1f} s)")
        stt.transcribe(data["short_3s"])  # first call pays one-off setup
        for name, wav in data.items():
            times = []
            for _ in range(3):
                t = time.perf_counter()
                out = stt.transcribe(wav)
                times.append(time.perf_counter() - t)
            best = min(times)
            e = wer(SCRIPTS[name], out["text"])
            print(f"  {name:12s} audio {out['duration']:5.1f}s  stt {best:5.2f}s (median {sorted(times)[1]:.2f}s)  "
                  f"WER {e:.0%}  {out['text'][:70]!r}")
            results.append({"engine": spec, "clip": name, "audio_s": out["duration"], "best_s": round(best, 3),
                            "median_s": round(sorted(times)[1], 3), "wer": round(e, 3)})
    (CLIPS.parent / "bench_stt.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
