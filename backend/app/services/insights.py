"""Aggregated, read-only views of a student's performance (shared by all portals)."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AssessmentResult, EnglishSession, InterviewSession, PracticeExercise, ProgressRecord, Resume, StudentBadge, User,
)
from ..serializers import iso
from .common import get_setting
from .rewards import badge_stats, total_points


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def current_resume(db: Session, student_id: int) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.student_id == student_id, Resume.is_current.is_(True))
                     .order_by(Resume.id.desc()))


def trend_label(scores: list[float], threshold: float) -> str:
    """'improving' | 'struggling' | 'stable' | 'no_data' based on chronological scores."""
    if not scores:
        return "no_data"
    recent = scores[-3:]
    earlier = scores[:-3][-3:]
    recent_avg = sum(recent) / len(recent)
    if earlier:
        delta = recent_avg - sum(earlier) / len(earlier)
        if delta >= 5:
            return "improving"
        if recent_avg < threshold or delta <= -5:
            return "struggling"
        return "stable"
    return "struggling" if recent_avg < threshold else "stable"


def student_summary(db: Session, student: User) -> dict:
    sid = student.id
    interviews = db.scalars(select(InterviewSession).where(
        InterviewSession.student_id == sid, InterviewSession.status == "completed")
        .order_by(InterviewSession.completed_at)).all()
    scored = [s for s in interviews if s.overall_score is not None and not s.flagged]
    by_cat = defaultdict(list)
    for s in scored:
        by_cat[s.category].append(s.overall_score)
    english = db.scalars(select(EnglishSession).where(
        EnglishSession.student_id == sid, EnglishSession.status == "completed")
        .order_by(EnglishSession.ended_at)).all()
    eng_crit = defaultdict(list)
    for e in english:
        for k, v in (e.scores or {}).items():
            if isinstance(v, (int, float)):
                eng_crit[k].append(v)
    results = db.scalars(select(AssessmentResult).where(
        AssessmentResult.student_id == sid, AssessmentResult.submitted_at.is_not(None),
        AssessmentResult.score.is_not(None)).order_by(AssessmentResult.submitted_at)).all()
    by_topic = defaultdict(list)
    by_cat_assess = defaultdict(list)
    for r in results:
        by_topic[r.assessment.topic].append(r.score)
        by_cat_assess[r.assessment.category].append(r.score)
    crit = defaultdict(list)
    for s in scored:
        for q in s.questions:
            if q.answer and q.answer.scores:
                for k, v in q.answer.scores.items():
                    crit[k].append(v)
    exercises = db.scalars(select(PracticeExercise).where(
        PracticeExercise.student_id == sid, PracticeExercise.status == "completed")).all()
    pron = [x.score for x in exercises if x.kind == "pronunciation" and x.score is not None]
    speak = [x.score for x in exercises if x.kind == "speaking" and x.score is not None]
    resume = current_resume(db, sid)
    threshold = float(get_setting(db, "struggling_score_threshold") or 50)
    scores_seq = [s.overall_score for s in scored]

    weak = []
    for cat, vals in by_cat.items():
        if _avg(vals) is not None and _avg(vals) < 60:
            weak.append(f"{cat.title()} interviews (avg {_avg(vals)})")
    for k, vals in eng_crit.items():
        if _avg(vals) is not None and _avg(vals) < 6:
            weak.append(f"English {k.replace('_', ' ')} (avg {_avg(vals)}/10)")
    for topic, vals in by_topic.items():
        if _avg(vals) is not None and _avg(vals) < 60:
            weak.append(f"{topic} assessments (avg {_avg(vals)}%)")
    if resume and resume.analysis:
        for m in (resume.analysis.get("missing_skills") or [])[:5]:
            weak.append(f"Missing skill: {m}")

    for k, vals in by_cat_assess.items():
        if k == "aptitude" and _avg(vals) is not None and _avg(vals) < 60:
            weak.append(f"Aptitude tests (avg {_avg(vals)}%)")
    if pron and _avg(pron) < 70:
        weak.append(f"Pronunciation (avg {_avg(pron)})")

    stats = badge_stats(db, sid)
    badges = db.scalars(select(StudentBadge).where(StudentBadge.student_id == sid)).all()
    p = student.student_profile
    summary = {
        "student": {"id": student.id, "full_name": student.full_name, "email": student.email,
                    "college": p.college if p else None, "branch": p.branch if p else None,
                    "graduation_year": p.graduation_year if p else None, "cgpa": p.cgpa if p else None,
                    "target_role": p.target_role if p else None, "skills": (p.skills if p else []) or [],
                    "last_active_at": iso(student.last_active_at)},
        "interviews": {
            "completed": len(interviews), "average_score": _avg(scores_seq),
            "best_score": max(scores_seq) if scores_seq else None,
            "by_category": {k: _avg(v) for k, v in by_cat.items()},
            "criteria": {k: _avg(v) for k, v in crit.items()},
            "recent":[{"id": s.id, "job_role": s.job_role, "category": s.category, "score": s.overall_score,
                        "completed_at": iso(s.completed_at), "flagged": s.flagged} for s in interviews[-10:]],
        },
        "english": {
            "sessions": len(english), "minutes": stats["english_minutes"],
            "average_score": _avg([e.overall_score for e in english]),
            "by_criterion": {k: _avg(v) for k, v in eng_crit.items()},
            "pronunciation_drills": len(pron), "pronunciation_avg": _avg(pron),
            "speaking_exercises": len(speak), "speaking_avg": _avg(speak),
        },
        "assessments": {
            "taken": len(results), "average_score": _avg([r.score for r in results]),
            "passed": sum(1 for r in results if r.passed),
            "by_topic": {k: _avg(v) for k, v in by_topic.items()},
            "by_category": {k: _avg(v) for k, v in by_cat_assess.items()},
        },
        "resume": None if not resume else {
            "id": resume.id, "filename": resume.filename, "analysis_status": resume.analysis_status,
            "resume_score": (resume.analysis or {}).get("resume_score"),
            "strengths": (resume.analysis or {}).get("strengths", []),
            "missing_skills": (resume.analysis or {}).get("missing_skills", []),
            "improvement_areas": (resume.analysis or {}).get("improvement_areas", []),
            "uploaded_at": iso(resume.created_at)},
        "rewards": {"points": total_points(db, sid), "badges": len(badges),
                    "current_streak": stats["current_streak"], "longest_streak": stats["streak_days"]},
        "weak_areas": weak,
        "trend": trend_label(scores_seq, threshold),
        "badge_list": [{"name": b.badge.name, "icon": b.badge.icon, "awarded_at": iso(b.awarded_at)} for b in badges],
        "english_minutes": stats["english_minutes"],
    }
    english_scores = [e.overall_score for e in english if e.overall_score is not None] + speak
    summary["readiness"] = readiness_score(db, student, summary, _avg(english_scores))
    summary["remedies"] = remedies(summary)
    return summary


# --------------------------------------------------------------------------- placement readiness

READINESS_WEIGHTS = {"interviews": 0.30, "assessments": 0.20, "english": 0.20, "resume": 0.20, "profile": 0.10}


def profile_completeness(student: User, has_resume: bool) -> int:
    p = student.student_profile
    fields = [p and p.college, p and p.branch, p and p.cgpa is not None, p and p.skills, p and p.target_role,
              p and (p.projects or p.experience), has_resume]
    return round(100 * sum(1 for f in fields if f) / len(fields))


def readiness_score(db: Session, student: User, s: dict, english_avg: float | None) -> dict:
    """Transparent weighted score. Missing components count as 0 so the score reflects real preparation."""
    components = {
        "interviews": s["interviews"]["average_score"],
        "assessments": s["assessments"]["average_score"],
        "english": english_avg,
        "resume": (s["resume"] or {}).get("resume_score"),
        "profile": profile_completeness(student, bool(s["resume"])),
    }
    score = round(sum((components[k] or 0) * w for k, w in READINESS_WEIGHTS.items()), 1)
    threshold = float(get_setting(db, "readiness_threshold") or 70)
    level = "ready" if score >= threshold else "almost" if score >= threshold - 20 else "not_ready"
    missing = [k for k, v in components.items() if v is None]
    return {"score": score, "level": level, "threshold": threshold, "weights": READINESS_WEIGHTS,
            "components": components, "missing": missing}


# --------------------------------------------------------------------------- rule-based remedies

def remedies(s: dict) -> list[dict]:
    """Deterministic weakness -> remedy suggestions (not AI). Each includes a ready-to-assign goal."""
    out = []

    def add(weakness, remedy, goal_type, title, target=1, target_score=None):
        out.append({"weakness": weakness, "remedy": remedy,
                    "goal": {"title": title, "goal_type": goal_type, "target_count": target,
                             "target_score": target_score, "description": remedy}})

    eng = s["english"]
    crit = eng["by_criterion"]
    if eng["sessions"] == 0 and eng["speaking_exercises"] == 0:
        add("No English speaking practice yet", "Practise speaking English for 15 minutes daily.",
            "english_practice", "Complete 5 English speaking sessions or exercises", 5)
    elif (eng["average_score"] or 100) < 60 or any((v or 10) < 6 for v in crit.values()):
        add("Poor English communication", "Practise speaking English for 15 minutes daily.",
            "english_practice", "Practise spoken English on 7 days", 7)
    if eng["pronunciation_avg"] is not None and eng["pronunciation_avg"] < 70:
        add("Unclear pronunciation", "Do 5 pronunciation drills daily, focusing on the highlighted words.",
            "english_practice", "Complete 10 pronunciation drills", 10)
    tech = s["interviews"]["by_category"].get("technical")
    tech_tests = s["assessments"]["by_category"].get("technical")
    if (tech is not None and tech < 60) or (tech_tests is not None and tech_tests < 60):
        add("Low technical knowledge", "Study weak topics and complete technical quizzes.",
            "assessment", "Pass 3 technical quizzes", 3, 60)
    if s["interviews"]["completed"] == 0:
        add("No mock interview practice", "Start with beginner-level mock interviews.",
            "mock_interview", "Complete 2 easy mock interviews", 2)
    elif (s["interviews"]["average_score"] or 100) < 55:
        add("Low interview confidence", "Practise beginner-level mock interviews.",
            "mock_interview", "Complete 3 mock interviews", 3)
    apt = s["assessments"]["by_category"].get("aptitude")
    if apt is not None and apt < 60:
        add("Poor aptitude score", "Solve 10 aptitude questions daily.", "assessment", "Pass 2 aptitude tests", 2, 60)
    coding = s["assessments"]["by_category"].get("coding")
    if coding is not None and coding < 60:
        add("Weak coding skills", "Solve one coding problem daily and review the reference solutions.",
            "assessment", "Score 60%+ in 2 coding tests", 2, 60)
    resume = s["resume"]
    if not resume:
        add("No resume uploaded", "Upload your resume for AI analysis.", "resume_update", "Upload and analyse your resume")
    elif (resume.get("resume_score") or 100) < 60:
        add("Weak resume", "Improve project descriptions and highlight relevant skills.",
            "resume_update", "Revise resume and re-upload for analysis")
    rel = s["interviews"]["criteria"].get("relevance")
    clar = s["interviews"]["criteria"].get("clarity")
    if (rel is not None and rel < 6) or (clar is not None and clar < 6):
        add("Difficulty answering questions", "Practise answering common interview questions aloud.",
            "mock_interview", "Complete 3 HR/behavioral mock interviews", 3)
    return out


# --------------------------------------------------------------------------- history & weekly progress

def practice_history(db: Session, student_id: int, limit: int = 100) -> list[dict]:
    items = []
    for s in db.scalars(select(InterviewSession).where(InterviewSession.student_id == student_id,
                                                       InterviewSession.status == "completed")):
        items.append({"type": "interview", "id": s.id, "title": f"{s.job_role} ({s.category}, {s.difficulty})",
                      "score": s.overall_score, "date": iso(s.completed_at), "link": f"/student/interviews/{s.id}"})
    for e in db.scalars(select(EnglishSession).where(EnglishSession.student_id == student_id,
                                                     EnglishSession.status == "completed")):
        items.append({"type": "english", "id": e.id, "title": f"English conversation: {e.topic}",
                      "score": e.overall_score, "minutes": round(e.active_seconds / 60, 1), "date": iso(e.ended_at),
                      "link": f"/student/english/{e.id}"})
    for x in db.scalars(select(PracticeExercise).where(PracticeExercise.student_id == student_id,
                                                       PracticeExercise.status == "completed")):
        items.append({"type": x.kind, "id": x.id, "title": x.prompt, "score": x.score, "date": iso(x.completed_at),
                      "link": "/student/english-learning"})
    for r in db.scalars(select(AssessmentResult).where(AssessmentResult.student_id == student_id,
                                                       AssessmentResult.submitted_at.is_not(None))):
        items.append({"type": "assessment", "id": r.id, "title": f"{r.assessment.title} ({r.assessment.category})",
                      "score": r.score, "date": iso(r.submitted_at), "link": "/student/assessments?tab=results",
                      "pending": r.evaluation_status == "pending"})
    items.sort(key=lambda i: i["date"] or "", reverse=True)
    return items[:limit]


def weekly_progress(db: Session, student_id: int, weeks: int = 8) -> list[dict]:
    """Activities and average score per ISO week for the last N weeks."""
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=now.weekday(), weeks=weeks - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    buckets = []
    for i in range(weeks):
        ws = start + timedelta(weeks=i)
        buckets.append({"week": ws.date().isoformat(), "activities": 0, "scores": [], "minutes": 0.0})
    for item in practice_history(db, student_id, limit=10000):
        if not item["date"]:
            continue
        d = datetime.fromisoformat(item["date"])
        d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        idx = (d - start).days // 7
        if 0 <= idx < weeks:
            b = buckets[idx]
            b["activities"] += 1
            if item.get("score") is not None:
                b["scores"].append(item["score"])
            b["minutes"] += item.get("minutes", 0)
    return [{"week": b["week"], "activities": b["activities"], "minutes": round(b["minutes"], 1),
             "avg_score": _avg(b["scores"])} for b in buckets]


def attempt_comparison(db: Session, student_id: int) -> list[dict]:
    """Each completed interview with the change versus the previous attempt in the same category."""
    rows = db.scalars(select(InterviewSession).where(
        InterviewSession.student_id == student_id, InterviewSession.status == "completed",
        InterviewSession.overall_score.is_not(None)).order_by(InterviewSession.completed_at)).all()
    last: dict[str, float] = {}
    out = []
    for s in rows:
        prev = last.get(s.category)
        out.append({"id": s.id, "date": iso(s.completed_at), "role": s.job_role, "category": s.category,
                    "difficulty": s.difficulty, "score": s.overall_score,
                    "change": round(s.overall_score - prev, 1) if prev is not None else None})
        last[s.category] = s.overall_score
    return list(reversed(out))


def progress_series(db: Session, student_id: int) -> list[dict]:
    rows = db.scalars(select(ProgressRecord).where(ProgressRecord.student_id == student_id)
                      .order_by(ProgressRecord.created_at)).all()
    return [{"metric": r.metric, "value": r.value, "label": r.label, "source_type": r.source_type,
             "source_id": r.source_id, "date": iso(r.created_at)} for r in rows]


def record_progress(db: Session, student_id: int, metric: str, value: float, source_type: str, source_id: int,
                    label: str | None = None) -> None:
    db.add(ProgressRecord(student_id=student_id, metric=metric, value=value, source_type=source_type,
                          source_id=source_id, label=label))
