"""Personal English practice plan, built from the student's own recent data (no AI call, no invented evidence).

Sources:
  * corrections Aria gave in English conversations -> grammar patterns + the student's own corrected sentences
  * interview reports -> filler words, speaking pace, very short answers
  * earlier drills -> delivery scores, words that were hard to read aloud
  * the resume -> a 60-second project pitch about the student's real project

Each plan item says WHY it is suggested (the evidence) and which drill practises it. The drill content is built here
on the server; the browser only sends the item id, so a drill can never claim evidence that does not exist.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EnglishMessage, EnglishSession, InterviewSession, PracticeExercise
from . import english_companion as ec
from .insights import current_resume

TIMED_PROMPTS = {
    "easy": ["Introduce yourself in one minute: who you are, what you study, and what you enjoy building.",
             "Describe your favourite subject and one thing you learned in it recently."],
    "medium": ["Tell me about a time you solved a difficult problem. What did you do, and what was the result?",
               "Why do you want to work in this field? Give one real reason and one example.",
               "Describe a time you worked in a team. What was YOUR part?"],
    "hard": ["Explain a technical concept you know well to someone who is not technical.",
             "Describe a failure, what you did about it, and what you would do differently now."],
}


def _recent_corrections(db: Session, user_id: int, limit_sessions: int = 10) -> list[dict]:
    sessions = db.scalars(select(EnglishSession.id).where(EnglishSession.student_id == user_id)
                          .order_by(EnglishSession.id.desc()).limit(limit_sessions)).all()
    if not sessions:
        return []
    msgs = db.scalars(select(EnglishMessage).where(EnglishMessage.session_id.in_(sessions),
                                                   EnglishMessage.sender == "student")
                      .order_by(EnglishMessage.id.desc()).limit(200)).all()
    return [c for m in msgs for c in (m.corrections or []) if c.get("corrected")]


def build(db: Session, user_id: int) -> dict:
    items: list[dict] = []
    corrections = _recent_corrections(db, user_id)
    patterns = Counter(p for p in (ec._pattern(c) for c in corrections) if p)
    if corrections:
        top = patterns.most_common(1)[0] if patterns else ("sentence formation", len(corrections))
        sentences = []
        for c in corrections:
            s = c["corrected"].strip().rstrip(".") + "."
            if len(s.split()) >= 3 and s not in sentences:
                sentences.append(s)
        items.append({
            "id": "my_sentences", "kind": "pronunciation", "drill": "my_sentences", "level": "medium",
            "title": f"Say your own corrected sentences ({top[0]})",
            "why": f"Aria corrected {len(corrections)} thing(s) in your recent conversations, most often "
                   f"{top[0]} ({top[1]}x). Saying the corrected versions aloud builds the right habit.",
            "evidence": [f"'{c['original']}' -> '{c['corrected']}'" for c in corrections[:3]],
            "prompts": sentences[:5],
        })

    reports = [s.report for s in db.scalars(
        select(InterviewSession).where(InterviewSession.student_id == user_id, InterviewSession.status == "completed",
                                       InterviewSession.report.is_not(None))
        .order_by(InterviewSession.id.desc()).limit(5)) if s.report]
    ind = [r.get("indicators") or {} for r in reports]
    fillers = [x["filler_words_per_100"] for x in ind if x.get("filler_words_per_100") is not None]
    paces = [x["speaking_pace_wpm"] for x in ind if x.get("speaking_pace_wpm")]
    short = sum(x.get("very_short_answers") or 0 for x in ind)

    drills = db.scalars(select(PracticeExercise).where(
        PracticeExercise.student_id == user_id, PracticeExercise.status == "completed",
        PracticeExercise.kind == "speaking").order_by(PracticeExercise.id.desc()).limit(10)).all()
    flu = [(x.details or {}).get("delivery") or {} for x in drills]
    drill_fpm = [f["fillers_per_min"] for f in flu if f.get("fillers_per_min") is not None and f.get("timed")]
    drill_pace = [f["pace_wpm"] for f in flu if f.get("pace_wpm")]

    if (fillers and sum(fillers) / len(fillers) > 4) or (drill_fpm and sum(drill_fpm) / len(drill_fpm) > 3):
        ev = []
        if fillers:
            ev.append(f"Interviews: about {sum(fillers) / len(fillers):.1f} filler words per 100 words")
        if drill_fpm:
            ev.append(f"Drills: about {sum(drill_fpm) / len(drill_fpm):.1f} filler words per minute")
        items.append({"id": "fillers", "kind": "speaking", "drill": "timed_answer", "level": "medium",
                      "title": "Replace filler words with short pauses",
                      "why": "Filler words make answers sound less sure. Practise pausing silently instead.",
                      "evidence": ev, "target_seconds": 60})
    all_pace = paces + drill_pace
    if all_pace:
        avg = sum(all_pace) / len(all_pace)
        if avg > 170 or avg < 95:
            items.append({"id": "pace", "kind": "speaking", "drill": "timed_answer", "level": "easy",
                          "title": "Slow down a little" if avg > 170 else "Keep your answer flowing",
                          "why": f"Your average speaking pace is about {round(avg)} words per minute; "
                                 "100-165 is easiest to follow in an interview.",
                          "evidence": [f"{len(all_pace)} recorded answer(s)"], "target_seconds": 60})
    if short >= 2:
        items.append({"id": "longer_answers", "kind": "speaking", "drill": "timed_answer", "level": "medium",
                      "title": "Give fuller answers: point, example, result",
                      "why": f"{short} of your recent interview answers were very short.",
                      "evidence": [f"{short} very short interview answers"], "target_seconds": 60})

    resume = current_resume(db, user_id)
    projects = [p for p in ((resume.analysis or {}).get("projects") or []) if p.get("name")] \
        if resume and resume.analysis_status == "completed" else []
    if projects:
        p = projects[0]
        items.append({"id": "project_pitch", "kind": "speaking", "drill": "project_pitch", "level": "medium",
                      "title": f"60-second pitch: {p['name']}",
                      "why": "Interviewers almost always ask about your projects. Practise a clear one-minute "
                             "version: the problem, what YOU built, and the result.",
                      "evidence": [f"Project on your resume: {p['name']}"], "target_seconds": 60,
                      "prompts": [f"Explain your project '{p['name']}' in about 60 seconds: what problem it solves, "
                                  "which part you built yourself, and what the result was."]})

    hard_words = Counter(w for x in db.scalars(select(PracticeExercise).where(
        PracticeExercise.student_id == user_id, PracticeExercise.kind == "pronunciation",
        PracticeExercise.status == "completed").order_by(PracticeExercise.id.desc()).limit(15))
        for w in ((x.details or {}).get("practice_words") or []))
    repeated = [w for w, n in hard_words.most_common(8) if n >= 2 and len(w) > 3]
    if repeated:
        items.append({"id": "tricky_words", "kind": "pronunciation", "drill": "standard", "level": "medium",
                      "title": "Words you often missed: " + ", ".join(repeated[:4]),
                      "why": "These words were missed or misheard in more than one read-aloud drill.",
                      "evidence": [f"'{w}' x{hard_words[w]}" for w in repeated[:4]]})

    if not items:
        items.append({"id": "baseline", "kind": "speaking", "drill": "timed_answer", "level": "easy",
                      "title": "Start here: a one-minute introduction",
                      "why": "There is no practice data yet. This first recording measures your pace, pauses and "
                             "filler words so the plan can adapt to you.",
                      "evidence": [], "target_seconds": 60})
    return {"items": items[:6], "based_on": {"conversation_corrections": len(corrections),
                                             "interview_reports": len(reports), "speaking_drills": len(drills)}}


def item(db: Session, user_id: int, item_id: str) -> dict | None:
    return next((i for i in build(db, user_id)["items"] if i["id"] == item_id), None)
