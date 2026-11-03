"""Compare local models on the two workloads that matter most, using the app's real prompts and validation.

  1. English chat turns (the conversational path: english_reply)    -> latency + whether a grammar slip is corrected
  2. Answer scoring (score_answer) on six labelled answers           -> does the score separate good from bad?

Run from the backend folder, Ollama running, every listed model already pulled:
    .\\venv\\Scripts\\python.exe tests_perf\\bench_models.py --models qwen3:4b qwen3:1.7b --runs 3 --out results.json

Each model is unloaded first, so the first call of each model is a cold start (reported separately). Uses an
in-memory database. Only timings and numeric scores are printed; model output text is not stored.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ["MONGODB_DB"] = "hiresense_bench"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app import database, seed as seed_module  # noqa: E402
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

RUBRIC = [{"name": n, "weight": w, "description": d} for n, w, d in [
    ("Relevance", 20, "Answers the question asked"), ("Correctness", 30, "Facts and reasoning are right"),
    ("Completeness", 20, "Key points covered"), ("Clarity", 15, "Well structured"),
    ("Communication", 15, "Professional language")]]
QUESTION = "What is a database index and what is the trade-off of adding one?"
# label, expected band (lo, hi) on the 0-100 score - a sanity range, not a measured accuracy
ANSWERS = [
    ("strong", (65, 100), "An index is a separate data structure, usually a B-tree, that lets the database find rows "
     "without scanning the whole table. Reads on the indexed columns get much faster, but every insert and update must "
     "also update the index, and it uses extra disk space, so I index columns used in filters and joins, not everything."),
    ("concise_correct", (45, 100), "It is a B-tree on a column that speeds up lookups but slows down writes."),
    ("partial", (25, 70), "An index makes queries faster. I think it stores the data in sorted order."),
    ("vague", (0, 50), "It is something that helps the database work better and is used in many projects."),
    ("incorrect", (0, 40), "An index is a backup copy of the table that is used when the server crashes, and it "
     "makes writes faster because it removes duplicate rows."),
    ("irrelevant", (0, 25), "My favourite hobby is cricket and I play with my friends every Sunday morning."),
]
CHAT = [  # (topic, history incl. the student's latest message)
    ("video games", "Yesterday I go to college and meet my friend. We talk about video games."),
    ("movies", "I like movies because they are interesting. Last week I watch a very good one."),
    ("daily life", "Hello! How are you today?"),
]


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo))


def stats(xs):
    return {"n": len(xs), "p50_ms": pct(xs, 50), "p95_ms": pct(xs, 95), "mean_ms": round(statistics.mean(xs))} if xs else None


def unload_all(base: str):
    try:
        for m in httpx.get(f"{base}/api/ps", timeout=3).json().get("models", []):
            httpx.post(f"{base}/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=30)
    except httpx.HTTPError:
        pass
    time.sleep(1)


def ps_info(base: str, model: str):
    for m in httpx.get(f"{base}/api/ps", timeout=3).json().get("models", []):
        if m["name"].startswith(model.split(":")[0]):
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            return {"size_gb": round(size / 1e9, 2), "gpu_share_pct": round(100 * vram / size) if size else None}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen3:4b"])
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    database.init_db()
    database.clear_database()  # a throwaway MongoDB database (MONGODB_DB set above), never the app's own
    seed_module.seed()
    factory = database.SessionLocal
    db = factory()

    from app.services import ai, embeddings, local_llm
    embeddings.warmup()
    s = get_settings()
    base = local_llm._base_url()
    report = {"hardware_note": "RTX 3050 4 GB laptop; see PERFORMANCE_BASELINE.md", "num_ctx": s.ollama_num_ctx,
              "runs": args.runs, "models": {}}
    for model in args.models:
        s.ollama_model = model
        local_llm.runtime_status(force=True)
        unload_all(base)
        r: dict = {}
        print(f"\n== {model}", flush=True)
        t = time.perf_counter()
        local_llm.warmup()
        r["cold_load_ms"] = round((time.perf_counter() - t) * 1000)
        r["placement"] = ps_info(base, model)
        chat_ms, corr_hits, chat_fail = [], 0, 0
        for run in range(args.runs):
            for topic, msg in CHAT:
                hist = [{"sender": "student", "content": msg}]
                t = time.perf_counter()
                try:
                    out = ai.english_reply(db, None, topic=topic, history=hist, learning_mode="english_learning")
                    chat_ms.append((time.perf_counter() - t) * 1000)
                    if "go to college" in msg or "watch a very" in msg:
                        corr_hits += 1 if out.get("corrections") else 0
                except ai.AIUnavailable:
                    chat_fail += 1
        r["english_chat"] = {**(stats(chat_ms) or {}), "failed": chat_fail,
                             "correction_given_on_flawed_msgs": f"{corr_hits}/{args.runs * 2}"}
        score_ms, scores = [], {}
        for label, band, answer in ANSWERS:
            vals = []
            for _ in range(args.runs):
                t = time.perf_counter()
                try:
                    ev = ai.score_answer(db, None, job_role="Backend Developer", question=QUESTION,
                                         question_type="technical", answer=answer, rubric=RUBRIC)
                    score_ms.append((time.perf_counter() - t) * 1000)
                    vals.append(ev["score"])
                except ai.AIUnavailable:
                    pass
            scores[label] = {"scores": vals, "expected_band": list(band),
                             "in_band": sum(band[0] <= v <= band[1] for v in vals)}
        r["answer_scoring"] = {**(stats(score_ms) or {}), "by_answer": scores,
                               "ordering_ok": all(
                                   statistics.mean(scores["strong"]["scores"] or [0]) >
                                   statistics.mean(scores[k]["scores"] or [100]) for k in ("vague", "incorrect", "irrelevant"))}
        report["models"][model] = r
        print(json.dumps(r, indent=1), flush=True)
    unload_all(base)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
