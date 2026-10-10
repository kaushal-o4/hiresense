"""Latency benchmark for the interview pipeline with the REAL local models (Ollama, Kokoro, Whisper).

Measures each stage separately so the bottleneck is visible instead of guessed:
  * LLM cold load, question generation, answer scoring (with Ollama's own load / prompt / generation split)
  * text-to-speech: whole question vs. first sentence only (what the streaming path waits for)
  * speech-to-text of a recorded answer
  * the full "answer -> next question" server path (score + question), as the old endpoint did it

Run from the backend folder (Ollama running, model pulled):
    .\\venv\\Scripts\\python.exe tests_perf\\bench_interview_latency.py [--runs 5] [--out results.json]

Uses an in-memory database; no candidate data is written anywhere. Prints p50 / p95 / mean per stage.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import database, seed as seed_module  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402

get_settings.cache_clear()
HERE = Path(__file__).resolve().parent
WAV = HERE.parent / "tests_e2e" / "output" / "candidate_answer.wav"

RESUME = dict(job_role="Backend Developer", category="technical", total=5,
              resume_summary="Final-year B.Tech CSE student who built a Flask REST API for a library system and a "
                             "React dashboard; interned at a fintech startup working on PostgreSQL reports.",
              skills=["Python", "Flask", "PostgreSQL", "REST APIs", "Git", "React", "Docker"],
              projects=["Library management REST API", "Expense dashboard"],
              topics=["SQL joins", "indexing", "HTTP status codes", "authentication"], subject=None)
ANSWERS = [
    "In my library project I used Flask blueprints to split the API into books, members and loans. Each route "
    "validated the JSON body with marshmallow and returned proper status codes like 201 for created and 404 when a "
    "book was missing. I used SQLAlchemy models with PostgreSQL and added an index on the ISBN column because "
    "searches were slow.",
    "An index is a data structure, usually a B-tree, that lets the database find rows without scanning the whole "
    "table. It speeds up reads on the indexed columns but slows down inserts and updates a little because the "
    "index must also be updated, and it uses extra disk space.",
    "I am not fully sure, but I think a left join returns all rows from the left table and matching rows from "
    "the right table, and null when there is no match.",
]


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summary(xs):
    return {"n": len(xs), "p50_ms": round(pct(xs, 50)), "p95_ms": round(pct(xs, 95)),
            "mean_ms": round(statistics.mean(xs)), "min_ms": round(min(xs)), "max_ms": round(max(xs))} if xs else None


def timed(fn, *a, **kw):
    t = time.perf_counter()
    out = fn(*a, **kw)
    return out, (time.perf_counter() - t) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    database.SessionLocal = factory
    seed_module.SessionLocal = factory
    seed_module.seed(demo=False)
    db = factory()

    from app.services import ai, local_llm, stt, tts
    st = local_llm.runtime_status(force=True)
    if not (st["running"] and st["model_ready"]):
        sys.exit(f"LLM not available: {st['error']}")
    s = get_settings()
    res: dict = {"label": args.label, "model": s.ollama_model, "num_ctx": s.ollama_num_ctx, "runs": args.runs,
                 "stages": {}, "ollama_breakdown": {}}
    breakdowns: dict[str, list] = {}
    orig_chat = local_llm.chat_json

    def spy(*a, **kw):  # records Ollama's own timing split when the client exposes it
        r = orig_chat(*a, **kw)
        if getattr(r, "timings", None):
            breakdowns.setdefault(spy.feature, []).append(r.timings)
        return r
    local_llm.chat_json = spy
    spy.feature = "cold"

    def q(history, position, **extra):
        return ai.next_interview_question(db, None, position=position, history=history, difficulty="medium",
                                          interviewer="aria", **RESUME, **extra)

    # 1. cold start (model load) - only meaningful right after Ollama unloaded the model
    print("cold question (includes model load if not loaded)...", flush=True)
    _, cold = timed(q, [], 1)
    res["stages"]["llm_question_first_call_ms"] = round(cold)

    gen, score, turn = [], [], []
    history: list[dict] = []
    for i in range(args.runs):
        spy.feature = "question"
        nq, ms = timed(q, history, len(history) + 1)
        gen.append(ms)
        ans = ANSWERS[i % len(ANSWERS)]
        spy.feature = "score"
        ev, ms_s = timed(ai.score_answer, db, None, job_role=RESUME["job_role"], question=nq["question"],
                         question_type=nq["question_type"], answer=ans, rubric=[
                             {"name": "Relevance", "weight": 0.25}, {"name": "Correctness", "weight": 0.3},
                             {"name": "Clarity", "weight": 0.25}, {"name": "Communication", "weight": 0.2}])
        score.append(ms_s)
        turn.append(ms_s + ms)  # old server path after an answer: score, then the next question
        history.append({"question": nq["question"], "type": nq["question_type"], "difficulty": "medium",
                        "answer": ans, "score": ev["score"]})
        print(f"  run {i + 1}: question {ms:.0f} ms, score {ms_s:.0f} ms", flush=True)
    res["stages"]["llm_question_ms"] = summary(gen)
    res["stages"]["llm_score_ms"] = summary(score)
    res["stages"]["server_answer_to_next_question_ms"] = summary(turn)
    for k, v in breakdowns.items():
        res["ollama_breakdown"][k] = {f: round(statistics.mean(x[f] for x in v)) for f in v[0]}

    # 2. TTS: whole question vs first sentence
    if s.tts_enabled:
        tts.warmup()
        sample = ("Thanks for walking me through that. In your library API, how did you decide which columns to "
                  "index, and how would you check that an index is actually being used by PostgreSQL?")
        first = sample.split(". ")[0] + "."
        tts._cache.clear()
        whole, part = [], []
        for i in range(3):
            tts._cache.clear()
            _, ms = timed(tts.synthesize, sample, "af_heart", 0.95 + i * 0.001)
            whole.append(ms)
            tts._cache.clear()
            _, ms = timed(tts.synthesize, first, "af_heart", 0.95 + i * 0.001)
            part.append(ms)
        res["stages"]["tts_whole_question_ms"] = summary(whole)
        res["stages"]["tts_first_sentence_ms"] = summary(part)
        res["stages"]["tts_audio_seconds"] = tts.synthesize(sample, "af_heart", 0.95)["duration"]

    # 3. STT of a recorded spoken answer
    if s.stt_enabled and WAV.exists():
        stt.warmup()
        data = WAV.read_bytes()
        times = []
        for _ in range(3):
            out, ms = timed(stt.transcribe, data)
            times.append(ms)
        res["stages"]["stt_ms"] = summary(times)
        res["stages"]["stt_audio_seconds"] = out["duration"]

    local_llm.chat_json = orig_chat
    print(json.dumps(res, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
