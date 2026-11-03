"""Latency + quality benchmark of the analysis prompts (resume analysis, answer scoring, answer feedback, final
interview report) with the REAL configured provider (Gemini, falling back to Ollama), using the app's own functions.

    .\\venv\\Scripts\\python.exe tests_perf\\bench_prompts.py --runs 2 --out tests_perf\\results\\prompts_after.json

Uses the throwaway MongoDB database "hiresense_bench" (cleared first). Fictional inputs only. Prints timings, token
counts, which provider answered and simple quality checks; model text is not stored.
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

from app import database, seed as seed_module  # noqa: E402
from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

RESUME = """Rohan Mehta
rohan.mehta@example.com | github.com/rohanm | Pune
EDUCATION
B.E. Computer Engineering, Pune Institute of Technology, 2026, CGPA 8.4
HSC, Fergusson College, 2022, 89%
SKILLS
Python, Java, JavaScript, React, Node.js, Express, MongoDB, MySQL, Git, Docker, REST APIs, Data Structures
PROJECTS
Campus Canteen App - A React and Node.js web app for ordering food in the college canteen; used by 300 students,
cut queue time by 40%. Built the REST API with Express and MongoDB and added JWT login.
Stock Price Predictor - Python and scikit-learn model that predicts next-day prices from 5 years of data; LSTM tried.
INTERNSHIP
Web Development Intern, Brightlabs Software, Jun 2025 - Aug 2025: built admin dashboards in React, fixed 30+ bugs.
ACHIEVEMENTS
Led a team of 4 in Smart India Hackathon 2024 (finalist). Coordinator of the college coding club.
CERTIFICATIONS
AWS Cloud Practitioner (2025)
"""
QUESTION = "What is a database index and what is the trade-off of adding one?"
ANSWERS = [
    ("strong", (65, 100), "An index is a separate data structure, usually a B-tree, that lets the database find rows "
     "without scanning the whole table. Reads on the indexed columns get much faster, but every insert and update must "
     "also update the index, and it uses extra disk space, so I index columns used in filters and joins, not everything."),
    ("partial", (25, 70), "An index makes queries faster. I think it stores the data in sorted order."),
    ("incorrect", (0, 40), "An index is a backup copy of the table that is used when the server crashes, and it "
     "makes writes faster because it removes duplicate rows."),
    ("irrelevant", (0, 25), "My favourite hobby is cricket and I play with my friends every Sunday morning."),
]
RUBRIC = [{"name": n, "weight": w, "description": d} for n, w, d in [
    ("Relevance", 20, "Answers the question asked"), ("Correctness", 30, "Facts and reasoning are right"),
    ("Completeness", 20, "Key points covered"), ("Clarity", 15, "Well structured"),
    ("Communication", 15, "Professional language")]]
QA = [
    {"type": "technical", "question": QUESTION, "answer": ANSWERS[0][2], "score": 82},
    {"type": "project", "question": "In your Campus Canteen App, how did you handle two students ordering the last item "
     "at the same time?", "answer": "We did not really think about it, I think MongoDB handles it automatically.",
     "score": 38},
    {"type": "behavioral", "question": "Tell me about a time you disagreed with a teammate.",
     "answer": "In the hackathon my teammate wanted Flutter but I wanted React. We compared which one we knew better and "
               "chose React, and we finished the demo on time.", "score": 71},
    {"type": "hr", "question": "Why should we hire you?", "answer": "Because I am hard working and I learn fast.",
     "score": 45},
]


def stats(xs):
    return {"n": len(xs), "p50_ms": round(statistics.median(xs)), "max_ms": round(max(xs))} if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    database.init_db()
    database.clear_database()
    seed_module.seed()
    db = database.SessionLocal()

    from app.models import AIUsageLog
    from app.odm import select
    from app.services import ai, embeddings, gemini_llm, local_llm
    embeddings.warmup()

    who: list[str] = []
    real_gem, real_oll = gemini_llm.chat_json, local_llm._chat_ollama

    def gem(*a, **k):
        r = real_gem(*a, **k); who.append("gemini"); return r

    def oll(*a, **k):
        r = real_oll(*a, **k); who.append("ollama"); return r
    gemini_llm.chat_json, local_llm._chat_ollama = gem, oll

    def timed(fn):
        n = len(who)
        t = time.perf_counter()
        try:
            out = fn()
        except ai.AIUnavailable as e:
            return None, (time.perf_counter() - t) * 1000, f"fail:{e.kind or e.status_code}"
        return out, (time.perf_counter() - t) * 1000, ",".join(who[n:]) or "?"

    rep: dict = {"provider": get_settings().local_ai_provider, "runs": args.runs, "features": {}}
    feats = {k: {"ms": [], "by": [], "quality": []} for k in ("resume_analysis", "answer_scoring", "answer_feedback",
                                                              "interview_report")}
    for run in range(args.runs):
        out, ms, by = timed(lambda: ai.analyze_resume(db, None, RESUME, "Backend Developer"))
        feats["resume_analysis"]["ms"].append(ms); feats["resume_analysis"]["by"].append(by)
        if out:
            feats["resume_analysis"]["quality"].append({
                "skills": len(out["skills"]), "projects": len(out["projects"]),
                "internships": len(out["internships"]), "removed_unsupported": len(out["validation"]["removed_unsupported"]),
                "questions": len(out["suggested_interview_questions"]), "missing_skills": len(out["missing_skills"])})
        print(f"[{run}] resume {ms:.0f} ms via {by}", flush=True)

        scored = {}
        for label, band, ans in ANSWERS:
            out, ms, by = timed(lambda: ai.score_answer(db, None, job_role="Backend Developer", question=QUESTION,
                                                        question_type="technical", answer=ans, rubric=RUBRIC))
            feats["answer_scoring"]["ms"].append(ms); feats["answer_scoring"]["by"].append(by)
            if out:
                scored[label] = out
                feats["answer_scoring"]["quality"].append({"label": label, "score": out["score"],
                                                           "in_band": band[0] <= out["score"] <= band[1]})
            print(f"[{run}] score {label} {ms:.0f} ms via {by} -> {out and out['score']}", flush=True)

        sc = scored.get("partial") or next(iter(scored.values()), None)
        if sc:
            out, ms, by = timed(lambda: ai.answer_feedback(db, None, job_role="Backend Developer", question=QUESTION,
                                                           question_type="technical", answer=ANSWERS[1][2], scored=sc))
            feats["answer_feedback"]["ms"].append(ms); feats["answer_feedback"]["by"].append(by)
            if out:
                feats["answer_feedback"]["quality"].append({"improvements": len(out["improvements"]),
                                                            "sample_words": len(out["sample_answer"].split())})
            print(f"[{run}] feedback {ms:.0f} ms via {by}", flush=True)

        out, ms, by = timed(lambda: ai.interview_report(db, None, job_role="Backend Developer", category="mixed", qa=QA))
        feats["interview_report"]["ms"].append(ms); feats["interview_report"]["by"].append(by)
        if out:
            feats["interview_report"]["quality"].append({
                "summary_words": len(out["summary"].split()), "strengths": len(out["strengths"]),
                "weaknesses": len(out["weaknesses"]), "suggestions": len(out["suggestions"]),
                "closing_words": len(out["closing_remarks"].split())})
        print(f"[{run}] report {ms:.0f} ms via {by}", flush=True)

    logs = db.execute(select(AIUsageLog.feature, AIUsageLog.output_tokens, AIUsageLog.input_tokens,
                             AIUsageLog.status)).all()
    for k, f in feats.items():
        toks = [o for feat, o, i, st in logs if feat == k and st == "success" and o]
        tin = [i for feat, o, i, st in logs if feat == k and st == "success" and i]
        rep["features"][k] = {"latency": stats(f["ms"]), "answered_by": f["by"],
                              "avg_tokens_out": round(statistics.mean(toks)) if toks else None,
                              "avg_tokens_in": round(statistics.mean(tin)) if tin else None,
                              "invalid_outputs": sum(1 for feat, o, i, st in logs if feat == k and st == "error"),
                              "quality": f["quality"]}
    if feats["answer_scoring"]["quality"]:
        q = feats["answer_scoring"]["quality"]
        rep["features"]["answer_scoring"]["in_band_rate"] = round(sum(x["in_band"] for x in q) / len(q), 2)
    print(json.dumps(rep, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    db.close()
    database.clear_database()


if __name__ == "__main__":
    main()
