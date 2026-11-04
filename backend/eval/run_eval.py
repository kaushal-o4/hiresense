"""Behaviour evaluation of the interviewers and the English companion with the REAL local models.

Drives the real HTTP API (FastAPI TestClient, in-memory database) through the fixed scenarios in
eval/scenarios.json, so the same script measures any version of the backend:

    .\\venv\\Scripts\\python.exe eval\\run_eval.py --out eval\\results\\after.json
    .\\venv\\Scripts\\python.exe eval\\run_eval.py --backend-dir <copy of an older backend> --out before.json

Metrics (all computed automatically; transcripts are saved for manual review):
  * duplicate_pairs    - question pairs in one interview whose meaning similarity (MiniLM cosine, an independent
                         judge that is NOT the app's own duplicate filter) is >= 0.75
  * resume_grounded    - share of questions that mention something from the candidate's resume or role
  * followup_relevance - after a vague/partial answer: share of next questions whose similarity to that answer is
                         >= 0.35 (i.e. the interviewer reacted to what was said)
  * banned_phrases     - robotic acknowledgements ("Great answer", "Excellent", "Let's move on to the next question")
  * words_per_question - per interviewer (personality distinction), plus cross-persona similarity of follow-ups
  * invalid_rate       - model outputs that failed schema validation / all model calls (from ai_usage_logs)
  * latency            - model latency per feature (ai_usage_logs) and wall time per API call
  * English: topic_follow (reply mentions the candidate's topic), repeated_questions, corrections by mode,
    memory_hits (reply refers back to an earlier detail)

Fictional resumes only; nothing is written outside the in-memory database and the --out file.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANNED = re.compile(r"\b(great answer|excellent|that'?s a great|let'?s move on to the next question|interesting!)",
                    re.IGNORECASE)
VAGUE_KINDS = {"vague", "vague_claim", "team_vague", "partial", "short"}


def setup(backend_dir: Path):
    os.environ.update({"MONGODB_DB": "hiresense_eval", "TTS_ENABLED": "false", "STT_ENABLED": "false",
                       "AI_DAILY_LIMIT_PER_USER": "100000"})
    sys.path.insert(0, str(backend_dir))
    os.chdir(backend_dir)
    from app import database, seed as seed_module
    from app.config import get_settings
    from app.database import get_db
    get_settings.cache_clear()
    database.init_db()
    database.clear_database()  # a throwaway MongoDB database (MONGODB_DB set above), never the app's own
    seed_module.seed()
    factory = database.SessionLocal
    from app.main import app
    from app.routers import interviews

    def override():
        db = factory()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override
    interviews.feedback_job = lambda *a, **k: None  # tips/sample answers are not part of this evaluation
    from fastapi.testclient import TestClient
    return TestClient(app), factory


def embedder():
    from app.services import embeddings

    def sim(a: str, b: str) -> float:
        v = embeddings.embed([a, b])
        return float(v[0] @ v[1])
    return sim


def register(c, email):
    r = c.post("/api/auth/register/student", json={"full_name": "Eval Student", "email": email, "password": "Passw0rd!",
                                                   "college": "Eval College", "branch": "CS", "graduation_year": 2026})
    assert r.status_code == 201, r.text
    return r.json()["user"]["id"]


def add_resume(factory, user_id, resume):
    from app.models import Resume
    db = factory()
    for old in db.query(Resume).filter(Resume.student_id == user_id).all():  # the MongoDB layer has no bulk update
        old.is_current = False
    db.add(Resume(student_id=user_id, filename="resume.txt", stored_path="-", content_type="text/plain",
                  raw_text=resume["raw_text"], is_current=True, analysis_status="completed",
                  analysis=resume["analysis"], analyzed_at=datetime.now(timezone.utc)))
    db.commit()
    db.close()


def grounding_terms(resume) -> set[str]:
    a = resume["analysis"]
    terms = {resume["target_role"].lower()}
    for p in a["projects"]:
        terms |= {w for w in re.findall(r"[a-z]+", p["name"].lower()) if len(w) > 3 and w not in ("system", "management")}
        terms |= {t.lower() for t in p["technologies"]}
        terms |= {w for w in ("bed", "beds", "oxygen", "ward", "wards", "csv", "ssh", "failed login", "alert")
                  if w in p["description"].lower()}
    terms |= {s["name"].lower() for s in a["skills"]}
    terms |= {e["organization"].lower() for e in a.get("internships", []) + a.get("experience", [])}
    return terms


def mentions(text: str, terms: set[str]) -> bool:
    t = text.lower()
    return any(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", t) for term in terms)


def usage_since(factory, since_id: int):
    from app.models import AIUsageLog
    db = factory()
    rows = db.query(AIUsageLog).filter(AIUsageLog.id > since_id).all()
    out = [(r.feature, r.status, r.latency_ms, r.error) for r in rows]
    last = max([r.id for r in rows], default=since_id)
    db.close()
    return out, last


def run_interview(c, factory, sim, data, run, uid):
    resume = data["resumes"][run["resume"]]
    add_resume(factory, uid, resume)
    answers = data["answer_sets"][run["answers"]]
    t = time.perf_counter()
    r = c.post("/api/student/interviews", json={"job_role": resume["target_role"], "category": run["category"],
                                                "question_count": run["questions"], "difficulty": run["difficulty"],
                                                "mode": "text", "interviewer": run["interviewer"]})
    walls = [(time.perf_counter() - t) * 1000]
    assert r.status_code == 201, r.text
    s = r.json()["session"]
    turns = []
    i = 0
    while True:
        q = s["questions"][-1]
        if q.get("answer"):
            break
        if i >= len(run["answer_order"]) or len(turns) >= run["questions"]:
            turns.append({"question": q["text"], "type": q["question_type"], "difficulty": q.get("difficulty"),
                          "is_followup": q.get("is_followup"), "meta": q.get("meta"), "answer_kind": None})
            break
        ans = answers[run["answer_order"][i] % len(answers)]
        turns.append({"question": q["text"], "type": q["question_type"], "difficulty": q.get("difficulty"),
                      "is_followup": q.get("is_followup"), "meta": q.get("meta"), "answer_kind": ans["kind"],
                      "answer": ans["text"]})
        t = time.perf_counter()
        r = c.post(f"/api/student/interviews/{s['id']}/answer", json={"question_id": q["id"], "answer": ans["text"]})
        walls.append((time.perf_counter() - t) * 1000)
        if r.status_code != 200:
            turns[-1]["error"] = f"{r.status_code} {r.text[:200]}"
            break
        body = r.json()
        s = body["session"]
        turns[-1]["score"] = s["questions"][len(turns) - 1]["answer"]["score"]
        i += 1
        if body.get("ready_to_complete"):
            break
    c.delete(f"/api/student/interviews/{s['id']}")
    from app.models import InterviewQuestion  # server-side audit metadata (not part of the API response)
    db = factory()
    metas = {q_.text: q_.meta for q_ in db.query(InterviewQuestion).filter(InterviewQuestion.session_id == s["id"])}
    db.close()
    for t_ in turns:
        t_["meta"] = metas.get(t_["question"]) or t_.get("meta")
    qs = [t_["question"] for t_ in turns]
    terms = grounding_terms(resume)
    dup_pairs = [(a, b, round(sim(qs[a], qs[b]), 3)) for a in range(len(qs)) for b in range(a + 1, len(qs))]
    dup_pairs = [p for p in dup_pairs if p[2] >= 0.75]
    follow = []
    for k in range(len(turns) - 1):
        if turns[k]["answer_kind"] in VAGUE_KINDS:
            follow.append(round(sim(turns[k + 1]["question"], turns[k]["answer"]), 3))
    return {
        "id": run["id"], "interviewer": run["interviewer"], "turns": turns,
        "questions": len(qs), "duplicate_pairs": [{"a": a + 1, "b": b + 1, "similarity": x, "qa": qs[a], "qb": qs[b]}
                                                  for a, b, x in dup_pairs],
        "resume_grounded": round(sum(mentions(q, terms) for q in qs) / max(1, len(qs)), 3),
        "followup_similarity": follow,
        "followup_relevance": round(sum(x >= 0.35 for x in follow) / len(follow), 3) if follow else None,
        "banned_phrases": sum(bool(BANNED.search(q)) for q in qs),
        "words_per_question": round(statistics.mean(len(q.split()) for q in qs), 1),
        "wall_ms": [round(w) for w in walls],
        "generation_attempts": [(t_.get("meta") or {}).get("attempts") for t_ in turns],
        "rejections": [r for t_ in turns for r in ((t_.get("meta") or {}).get("rejected") or [])],
        "sources": [(t_.get("meta") or {}).get("source") for t_ in turns],
    }


def closing_question(text: str) -> str:
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.endswith("?")]
    return parts[-1] if parts else ""


def run_english(c, sim, run):
    t = time.perf_counter()
    r = c.post("/api/student/english", json={"topic": run["topic"], "mode": "text", "style": "free_talk",
                                             "learning_mode": run["learning_mode"]})
    walls = [(time.perf_counter() - t) * 1000]
    assert r.status_code == 201, r.text
    s = r.json()
    turns = []
    asked = [closing_question(s["messages"][0]["content"])]
    for turn in run["turns"]:
        t = time.perf_counter()
        r = c.post(f"/api/student/english/{s['id']}/message", json={"content": turn["text"]})
        walls.append((time.perf_counter() - t) * 1000)
        if r.status_code != 200:
            turns.append({"student": turn["text"], "error": f"{r.status_code} {r.text[:200]}"})
            continue
        s = r.json()
        reply = s["messages"][-1]["content"]
        corrections = s["messages"][-2].get("corrections") or []
        q = closing_question(reply)
        repeated = bool(q) and any(a and sim(q, a) >= 0.8 for a in asked)
        asked.append(q)
        low = reply.lower()
        turns.append({
            "student": turn["text"], "reply": reply, "corrections": corrections,
            "topic_follow": any(k in low for k in turn["expect_any"]),
            "repeated_question": repeated,
            "has_error": bool(turn.get("has_error")),
            "spoken_correction": bool(turn.get("expect_correction")) and any(
                w in low for w in ("went", "met", "were", "gave", "natural way", "you could say")),
            "memory_hit": (turn["memory_check"] in low) if turn.get("memory_check") else None,
            "memory": s.get("memory"),
        })
    c.delete(f"/api/student/english/{s['id']}")  # in-progress sessions can be deleted
    ok = [t_ for t_ in turns if "error" not in t_]
    return {
        "id": run["id"], "learning_mode": run["learning_mode"], "turns": turns,
        "topic_follow": round(sum(t_["topic_follow"] for t_ in ok) / max(1, len(ok)), 3),
        "repeated_questions": sum(t_["repeated_question"] for t_ in ok),
        "corrections_on_error_turns": [len(t_["corrections"]) for t_ in ok if t_["has_error"]],
        "corrections_on_clean_turns": [len(t_["corrections"]) for t_ in ok if not t_["has_error"]],
        "spoken_corrections": sum(t_["spoken_correction"] for t_ in ok),
        "memory_hits": [t_["memory_hit"] for t_ in ok if t_["memory_hit"] is not None],
        "reply_words": round(statistics.mean(len(t_["reply"].split()) for t_ in ok), 1) if ok else None,
        "errors": len(turns) - len(ok),
        "wall_ms": [round(w) for w in walls],
    }


def lat(rows, feature):
    xs = sorted(x[2] for x in rows if x[0] == feature and x[1] == "success" and x[2])
    if not xs:
        return None
    return {"n": len(xs), "p50_ms": xs[len(xs) // 2], "max_ms": xs[-1], "mean_ms": round(statistics.mean(xs))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend-dir", default=str(HERE.parent))
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="comma-separated run ids")
    args = ap.parse_args()
    out_path = Path(args.out).resolve()
    data = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))
    c, factory = setup(Path(args.backend_dir).resolve())
    from app.config import get_settings
    from app.services import local_llm
    st = local_llm.runtime_status(force=True)
    if not (st["running"] and st["model_ready"]):
        sys.exit(f"LLM not available: {st['error']}")
    sim = embedder()
    only = {x for x in args.only.split(",") if x}
    uid = register(c, "eval@test.dev")
    _, last = usage_since(factory, 0)
    result = {"backend_dir": str(Path(args.backend_dir).resolve()), "model": get_settings().ollama_model,
              "started": datetime.now(timezone.utc).isoformat(), "interviews": [], "english": []}
    for run in data["interview_runs"]:
        if only and run["id"] not in only:
            continue
        print(f"interview {run['id']} ...", flush=True)
        res = run_interview(c, factory, sim, data, run, uid)
        print(f"  dup={len(res['duplicate_pairs'])} grounded={res['resume_grounded']} "
              f"follow={res['followup_relevance']} words={res['words_per_question']}", flush=True)
        result["interviews"].append(res)
    for run in data["english_runs"]:
        if only and run["id"] not in only:
            continue
        print(f"english {run['id']} ...", flush=True)
        res = run_english(c, sim, run)
        print(f"  topic_follow={res['topic_follow']} repeats={res['repeated_questions']} "
              f"memory={res['memory_hits']}", flush=True)
        result["english"].append(res)
    rows, _ = usage_since(factory, last)
    features = sorted({r[0] for r in rows})
    result["latency"] = {f: lat(rows, f) for f in features}
    result["calls"] = {f: {"total": sum(r[0] == f for r in rows),
                           "invalid": sum(r[0] == f and r[1] == "error" for r in rows)} for f in features}
    total = sum(v["total"] for v in result["calls"].values())
    result["invalid_rate"] = round(sum(v["invalid"] for v in result["calls"].values()) / max(1, total), 3)
    iv = result["interviews"]
    # personality distinction: the same first (vague) answer is given to Aria, Victor and Marcus on the hospital
    # resume -> how different are their reactions (question 2)?
    second = {r["interviewer"]: r["turns"][1]["question"] for r in iv
              if r["id"].endswith("_hospital") and len(r["turns"]) > 1 and r["interviewer"] != "elena"}
    names = sorted(second)
    result["persona_followup_similarity"] = {f"{a}-{b}": round(sim(second[a], second[b]), 3)
                                             for i, a in enumerate(names) for b in names[i + 1:]}
    result["summary"] = {
        "interview_questions": sum(r["questions"] for r in iv),
        "duplicate_pairs": sum(len(r["duplicate_pairs"]) for r in iv),
        "resume_grounded_mean": round(statistics.mean(r["resume_grounded"] for r in iv), 3) if iv else None,
        "followup_relevance_mean": round(statistics.mean(r["followup_relevance"] for r in iv
                                                         if r["followup_relevance"] is not None), 3) if iv else None,
        "banned_phrases": sum(r["banned_phrases"] for r in iv),
        "words_per_question": {r["id"]: r["words_per_question"] for r in iv},
        "english_topic_follow_mean": round(statistics.mean(r["topic_follow"] for r in result["english"]), 3)
        if result["english"] else None,
        "english_repeated_questions": sum(r["repeated_questions"] for r in result["english"]),
        "invalid_rate": result["invalid_rate"],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(json.dumps(result["latency"], indent=2))


if __name__ == "__main__":
    main()
