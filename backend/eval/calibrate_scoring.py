"""Score calibration check for interview answers, using the REAL configured model.

Scores the fixed answers in eval/calibration_set.json (poor / fair / good / excellent, hand-labelled) with the same
function the live interview uses (ai.score_answer + the default rubric) and reports:

  * spearman      - rank correlation between the hand label and the 0-100 score (1.0 = perfect ordering)
  * mean_by_label - average score per label, and the gap between neighbouring labels (spread)
  * in_band       - share of answers whose score falls in the band a fair interviewer would give
  * perfect_100   - answers that got 100 (nothing in this set deserves 100)

    .\\venv\\Scripts\\python.exe eval\\calibrate_scoring.py --out eval\\results\\calibration_after.json
    .\\venv\\Scripts\\python.exe eval\\calibrate_scoring.py --repeat 2      # score each answer twice (noise)

Uses a throwaway MongoDB database (hiresense_eval_calibration). Fictional answers only.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 3) if den else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--baseline", action="store_true",
                    help="switch off the 2026-11-04 calibration changes (anchors, completeness blend, open-question "
                         "and wrong-answer rules) to measure the scoring as it was before")
    args = ap.parse_args()

    os.environ.update({"MONGODB_DB": "hiresense_eval_calibration", "AI_DAILY_LIMIT_PER_USER": "100000",
                       "TTS_ENABLED": "false", "STT_ENABLED": "false"})
    sys.path.insert(0, str(BACKEND))
    os.chdir(BACKEND)
    from app import database, seed as seed_module
    from app.config import get_settings
    get_settings.cache_clear()
    database.init_db()
    database.clear_database()
    seed_module.seed()
    from app.routers.interviews import DEFAULT_RUBRIC
    from app.services import ai, local_llm, scoring_bands

    if args.baseline:
        ai.SCORE_ANCHORS = ""
        ai.COMPLETENESS_SHARE = 0.0
        ai.WRONG_ANSWER_CAP = False
        ai.MISSING_POINT_CAP = False
        ai.MISSING_POINT_PROMPT = ""
        ai.question_is_open = lambda q: False
    models: list[str] = []
    real_chat = local_llm.chat_json

    def spy(*a, **kw):  # remember which model answered (Gemini may fall back to another model or to Ollama)
        r = real_chat(*a, **kw)
        models.append((getattr(r, "timings", None) or {}).get("model") or "?")
        return r
    local_llm.chat_json = spy

    data = json.loads((HERE / "calibration_set.json").read_text(encoding="utf-8"))
    db = database.SessionLocal()
    rows = []
    for item in data["items"]:
        for rep in range(args.repeat):
            t = time.monotonic()
            ev = ai.score_answer(db, None, job_role="Software Developer", question=item["question"],
                                 question_type=item["type"], answer=item["answer"], rubric=DEFAULT_RUBRIC)
            lo, hi = item["band"]
            rows.append({"id": item["id"], "label": item["label"], "rep": rep, "score": ev["score"],
                         "band": item["band"], "in_band": lo <= ev["score"] <= hi,
                         "criteria": {k: ev[k] for k in ai.CRITERIA}, "secs": round(time.monotonic() - t, 1),
                         "model": models[-1] if models else "?", "missing_point": ev.get("missing_point", "")})
            r = rows[-1]
            print(f"{r['id']:<22} label={r['label']} score={r['score']:>5} band={lo}-{hi} "
                  f"{'ok ' if r['in_band'] else 'OUT'} {scoring_bands.band(r['score'])['label']:<11} "
                  f"{r['criteria']} {r['secs']}s {r['model']}")
    db.close()

    labels = [r["label"] for r in rows]
    scores = [r["score"] for r in rows]
    by_label = {lab: round(statistics.fmean([r["score"] for r in rows if r["label"] == lab]), 1)
                for lab in sorted(set(labels))}
    keys = sorted(by_label)
    summary = {
        "n": len(rows),
        "spearman": spearman(labels, scores),
        "mean_by_label": by_label,
        "gaps": {f"{a}->{b}": round(by_label[b] - by_label[a], 1) for a, b in zip(keys, keys[1:])},
        "in_band": round(sum(r["in_band"] for r in rows) / len(rows), 3),
        "perfect_100": [r["id"] for r in rows if r["score"] >= 100],
        "max_score": max(scores),
        "min_score": min(scores),
        "baseline": args.baseline,
        "models": {m: models.count(m) for m in sorted(set(models))},
    }
    if args.repeat > 1:
        diffs = []
        for item in data["items"]:
            s = [r["score"] for r in rows if r["id"] == item["id"]]
            diffs.append(max(s) - min(s))
        summary["repeat_spread_mean"] = round(statistics.fmean(diffs), 1)
    print(json.dumps(summary, indent=1))
    if args.out:
        st = local_llm.runtime_status()
        args.out.write_text(json.dumps({"started": datetime.now(timezone.utc).isoformat(),
                                        "provider": st.get("provider"), "model": st.get("model"),
                                        "summary": summary, "rows": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
