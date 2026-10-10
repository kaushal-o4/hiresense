"""Mentor portal. Mentors only see assigned students unless granted `view_all_students`."""
import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import ensure_mentor_access, require_mentor
from ..models import (
    AssessmentResult, EnglishSession, ImprovementPlan, InterviewSession, MentorAssignment, MentorFeedback,
    MentorSession, Notification, PlanGoal, User,
)
from ..schemas import FeedbackIn, GoalIn, MentorSessionIn, MentorSessionUpdate, PlanIn, PlanUpdate
from ..serializers import english_out, interview_out, iso, mentor_session_out, plan_out, resume_out, result_out
from ..services import ai
from ..services.common import get_setting, notify
from ..services.insights import (
    attempt_comparison, current_resume, practice_history, progress_series, student_summary, weekly_progress,
)
from ..services.rewards import goal_progress

router = APIRouter(prefix="/api/mentor", tags=["mentor"])


def _student_ids(db: Session, mentor: User) -> list[int]:
    if "view_all_students" in (mentor.permissions or []):
        return list(db.scalars(select(User.id).where(User.role == "student", User.status == "active")))
    return list(db.scalars(select(MentorAssignment.student_id).where(
        MentorAssignment.mentor_id == mentor.id, MentorAssignment.active.is_(True))))


def _assigned_ids(db: Session, mentor: User) -> set[int]:
    return set(db.scalars(select(MentorAssignment.student_id).where(
        MentorAssignment.mentor_id == mentor.id, MentorAssignment.active.is_(True))))


def _plans_with_progress(db: Session, plans) -> list[dict]:
    return [plan_out(p, {g.id: goal_progress(db, p.student_id, g) for g in p.goals}) for p in plans]


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def last_practice(db: Session, student_id: int) -> datetime | None:
    hist = practice_history(db, student_id, limit=1)
    return _aware(datetime.fromisoformat(hist[0]["date"])) if hist and hist[0]["date"] else None


def _recently_alerted(db: Session, mentor_id: int, title: str, link: str) -> bool:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    return db.scalar(select(Notification.id).where(Notification.user_id == mentor_id, Notification.title == title,
                                                   Notification.link == link, Notification.created_at >= since)) is not None


def run_alerts(db: Session, mentor: User, students: list[User], goals: list[PlanGoal]) -> None:
    """Inactivity and missed-task alerts, at most once a week per student and alert type."""
    now = datetime.now(timezone.utc)
    days = int(get_setting(db, "inactive_days_alert") or 7)
    for st in students:
        link = f"/mentor/students/{st.id}"
        last = last_practice(db, st.id)
        joined = _aware(st.created_at)
        if (last is None and (now - joined).days >= days) or (last is not None and (now - last).days >= days):
            if not _recently_alerted(db, mentor.id, "Student stopped practising", link):
                notify(db, mentor.id, "Student stopped practising",
                       f"{st.full_name} has not practised for {days}+ days.", "alert", link)
        missed = [g for g in goals if g.plan.student_id == st.id and g.status == "pending" and g.deadline
                  and _aware(g.deadline) < now]
        if missed and not _recently_alerted(db, mentor.id, "Missed tasks", link):
            notify(db, mentor.id, "Missed tasks", f"{st.full_name} missed {len(missed)} task deadline(s): "
                   + ", ".join(g.title for g in missed[:3]), "alert", link)
    db.commit()


@router.get("/dashboard")
def dashboard(user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ids = _assigned_ids(db, user)
    students = db.scalars(select(User).where(User.id.in_(ids))).all() if ids else []
    summaries = [student_summary(db, s) for s in students]
    trend_counts = {"improving": 0, "stable": 0, "struggling": 0, "no_data": 0}
    for s in summaries:
        trend_counts[s["trend"]] += 1
    goals = db.scalars(select(PlanGoal).join(ImprovementPlan).where(ImprovementPlan.mentor_id == user.id)).all()
    sessions = db.scalars(select(MentorSession).where(MentorSession.mentor_id == user.id)).all()
    now = datetime.now(timezone.utc)

    def aware(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    students_meeting_goals = 0
    for sid in ids:
        sg = [g for g in goals if g.plan.student_id == sid]
        if sg and all(g.status == "completed" for g in sg):
            students_meeting_goals += 1
    upcoming = sorted([s for s in sessions if s.status == "scheduled" and aware(s.scheduled_at) >= now],
                      key=lambda s: aware(s.scheduled_at))
    overdue = [s for s in sessions if s.status == "scheduled" and aware(s.scheduled_at) < now]
    run_alerts(db, user, students, goals)
    inactive_days = int(get_setting(db, "inactive_days_alert") or 7)
    pending_goals = [g for g in goals if g.status == "pending" and g.plan.status == "active"]
    rows = []
    for st, s in zip(students, summaries):
        last = last_practice(db, st.id)
        inactive = last is None or (now - last).days >= inactive_days
        sp = [g for g in pending_goals if g.plan.student_id == st.id]
        rows.append({"id": st.id, "full_name": st.full_name, "trend": s["trend"], "readiness": s["readiness"]["score"],
                     "readiness_level": s["readiness"]["level"], "interview_avg": s["interviews"]["average_score"],
                     "assessment_avg": s["assessments"]["average_score"], "english_minutes": s["english"]["minutes"],
                     "pending_tasks": len(sp), "last_practice": iso(last), "inactive": inactive,
                     "badges": s["rewards"]["badges"], "remedies": s["remedies"][:2]})
    need_attention = [r for r in rows if r["trend"] in ("struggling", "no_data") or r["inactive"]]
    assess = [r["assessment_avg"] for r in rows if r["assessment_avg"] is not None]
    upcoming_tasks = sorted([g for g in pending_goals if g.deadline], key=lambda g: aware(g.deadline))[:8]
    return {
        "cards": {
            "my_students": len(ids),
            "improving": trend_counts["improving"],
            "need_attention": len(need_attention),
            "tasks_pending": len(pending_goals),
            "average_performance": round(sum(assess) / len(assess), 1) if assess else None,
            "placement_ready": sum(1 for s in summaries if s["readiness"]["level"] == "ready"),
        },
        "student_rows": rows,
        "recommendations": [{"student_id": r["id"], "student_name": r["full_name"], **rem}
                            for r in rows for rem in r["remedies"]][:12],
        "upcoming_tasks": [{"id": g.id, "title": g.title, "student_id": g.plan.student_id,
                            "student_name": db.get(User, g.plan.student_id).full_name, "deadline": iso(g.deadline),
                            "overdue": aware(g.deadline) < now} for g in upcoming_tasks],
        "assigned_students": len(ids),
        "trends": trend_counts,
        "students_meeting_goals": students_meeting_goals,
        "goals": {"total": len(goals), "completed": sum(1 for g in goals if g.status == "completed"),
                  "overdue": sum(1 for g in goals if g.status == "pending" and g.deadline and aware(g.deadline) < now)},
        "sessions": {"completed": sum(1 for s in sessions if s.status == "completed"), "upcoming": len(upcoming),
                     "pending_follow_ups": len(overdue)},
        "upcoming_sessions": [mentor_session_out(s) for s in upcoming[:6]],
        "needs_attention": [{"id": s["student"]["id"], "full_name": s["student"]["full_name"], "trend": s["trend"],
                             "interview_avg": s["interviews"]["average_score"], "weak_areas": s["weak_areas"][:3]}
                            for s in summaries if s["trend"] in ("struggling", "no_data")][:10],
        "comparison": [{"id": s["student"]["id"], "name": s["student"]["full_name"],
                        "interview_avg": s["interviews"]["average_score"], "english_avg": s["english"]["average_score"],
                        "assessment_avg": s["assessments"]["average_score"], "english_minutes": s["english"]["minutes"]}
                       for s in summaries],
    }


@router.get("/students")
def students(q: str | None = None, trend: str | None = None, user: User = Depends(require_mentor),
             db: Session = Depends(get_db)):
    ids = _student_ids(db, user)
    assigned = _assigned_ids(db, user)
    rows = []
    for st in db.scalars(select(User).where(User.id.in_(ids)).order_by(User.full_name)) if ids else []:
        if q and q.lower() not in st.full_name.lower() and q.lower() not in st.email.lower():
            continue
        s = student_summary(db, st)
        if trend and s["trend"] != trend:
            continue
        rows.append({"id": st.id, "full_name": st.full_name, "email": st.email, "branch": s["student"]["branch"],
                     "college": s["student"]["college"], "trend": s["trend"], "assigned": st.id in assigned,
                     "interviews_completed": s["interviews"]["completed"],
                     "interview_avg": s["interviews"]["average_score"], "english_minutes": s["english"]["minutes"],
                     "english_avg": s["english"]["average_score"], "assessment_avg": s["assessments"]["average_score"],
                     "resume_score": (s["resume"] or {}).get("resume_score"), "points": s["rewards"]["points"],
                     "readiness": s["readiness"]["score"], "readiness_level": s["readiness"]["level"],
                     "badges": s["rewards"]["badges"],
                     "last_active_at": s["student"]["last_active_at"], "weak_areas": s["weak_areas"][:3]})
    return rows


@router.get("/students/{student_id}")
def student_detail(student_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ensure_mentor_access(db, user, student_id)
    st = db.get(User, student_id)
    if not st or st.role != "student":
        raise HTTPException(404, "Student not found")
    resume = current_resume(db, student_id)
    interviews = db.scalars(select(InterviewSession).where(InterviewSession.student_id == student_id)
                            .order_by(InterviewSession.id.desc()).limit(20)).all()
    english = db.scalars(select(EnglishSession).where(EnglishSession.student_id == student_id)
                         .order_by(EnglishSession.id.desc()).limit(20)).all()
    results = db.scalars(select(AssessmentResult).where(AssessmentResult.student_id == student_id,
                                                        AssessmentResult.submitted_at.is_not(None))
                         .order_by(AssessmentResult.id.desc()).limit(20)).all()
    feedback = db.scalars(select(MentorFeedback).where(MentorFeedback.student_id == student_id)
                          .order_by(MentorFeedback.id.desc())).all()
    plans = db.scalars(select(ImprovementPlan).where(ImprovementPlan.student_id == student_id)
                       .order_by(ImprovementPlan.id.desc())).all()
    sessions = db.scalars(select(MentorSession).where(MentorSession.student_id == student_id)
                          .order_by(MentorSession.scheduled_at.desc())).all()
    p = st.student_profile
    return {
        "summary": student_summary(db, st),
        "profile": {"projects": p.projects or [], "experience": p.experience or [], "career_interests": p.career_interests,
                    "bio": p.bio} if p else None,
        "series": progress_series(db, student_id),
        "resume": resume_out(resume) if resume else None,
        "interviews": [interview_out(i) for i in interviews],
        "english_sessions": [english_out(e) for e in english],
        "assessment_results": [result_out(r) for r in results],
        "feedback": [{"id": f.id, "mentor_id": f.mentor_id, "mentor_name": f.mentor.full_name, "kind": f.kind,
                      "category": f.category, "content": f.content, "created_at": iso(f.created_at)} for f in feedback],
        "plans": _plans_with_progress(db, plans),
        "sessions": [mentor_session_out(s) for s in sessions],
        "weekly": weekly_progress(db, student_id),
        "attempts": attempt_comparison(db, student_id),
        "history": practice_history(db, student_id, limit=30),
    }


@router.post("/students/{student_id}/remedies/assign", status_code=201)
def assign_remedy(student_id: int, body: GoalIn, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    """Turn a suggested remedy into a tracked task in the student's 'Recommended remedies' plan."""
    ensure_mentor_access(db, user, student_id)
    plan = db.scalar(select(ImprovementPlan).where(ImprovementPlan.mentor_id == user.id,
                                                   ImprovementPlan.student_id == student_id,
                                                   ImprovementPlan.title == "Recommended remedies",
                                                   ImprovementPlan.status == "active"))
    if not plan:
        plan = ImprovementPlan(mentor_id=user.id, student_id=student_id, title="Recommended remedies",
                               description="Tasks your mentor assigned based on your performance analysis.")
        db.add(plan)
    data = body.model_dump()
    if not data.get("deadline"):
        data["deadline"] = datetime.now(timezone.utc) + timedelta(days=7)  # weekly target by default
    plan.goals.append(PlanGoal(**data))
    notify(db, student_id, "New task from your mentor", f"{body.title} (due {data['deadline'].strftime('%d %b')})",
           "plan", "/student/mentoring")
    db.commit()
    return _plans_with_progress(db, [plan])[0]


def _report_rows(db: Session, st: User) -> dict:
    s = student_summary(db, st)
    return {"student_id": st.id, "name": st.full_name, "email": st.email, "branch": s["student"]["branch"] or "",
            "readiness": s["readiness"]["score"], "readiness_level": s["readiness"]["level"], "trend": s["trend"],
            "interviews": s["interviews"]["completed"], "interview_avg": s["interviews"]["average_score"] or "",
            "interview_best": s["interviews"]["best_score"] or "", "english_minutes": s["english"]["minutes"],
            "english_avg": s["english"]["average_score"] or "", "assessments": s["assessments"]["taken"],
            "assessment_avg": s["assessments"]["average_score"] or "", "points": s["rewards"]["points"],
            "badges": s["rewards"]["badges"], "weak_areas": "; ".join(s["weak_areas"][:5])}


def _csv(rows: list[dict], filename: str) -> StreamingResponse:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()) if rows else ["empty"])
    w.writeheader()
    w.writerows(rows)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/report")
def all_students_report(user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ids = _student_ids(db, user)
    students = db.scalars(select(User).where(User.id.in_(ids)).order_by(User.full_name)).all() if ids else []
    return _csv([_report_rows(db, st) for st in students], "mentor_students_report.csv")


@router.get("/students/{student_id}/report")
def student_report(student_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    """Individual progress report (CSV): summary followed by every attempt with change over the previous one."""
    ensure_mentor_access(db, user, student_id)
    st = db.get(User, student_id)
    summary = _report_rows(db, st)
    rows = [{"section": "summary", "item": k, "value": v, "date": "", "change": ""} for k, v in summary.items()]
    for a in attempt_comparison(db, student_id):
        rows.append({"section": "interview_attempt", "item": f"{a['role']} ({a['category']}, {a['difficulty']})",
                     "value": a["score"], "date": a["date"], "change": a["change"] if a["change"] is not None else ""})
    for w in weekly_progress(db, student_id):
        rows.append({"section": "weekly", "item": f"week of {w['week']}: {w['activities']} activities, "
                     f"{w['minutes']} English min", "value": w["avg_score"] or "", "date": w["week"], "change": ""})
    return _csv(rows, f"student_{student_id}_report.csv")


@router.get("/students/{student_id}/interviews/{session_id}")
def student_interview(student_id: int, session_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ensure_mentor_access(db, user, student_id)
    s = db.get(InterviewSession, session_id)
    if not s or s.student_id != student_id:
        raise HTTPException(404, "Interview not found")
    return interview_out(s, detail=True)


@router.get("/students/{student_id}/english/{session_id}")
def student_english(student_id: int, session_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ensure_mentor_access(db, user, student_id)
    s = db.get(EnglishSession, session_id)
    if not s or s.student_id != student_id:
        raise HTTPException(404, "Session not found")
    return english_out(s, detail=True)


@router.post("/students/{student_id}/recommendations")
def ai_recommendations(student_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ensure_mentor_access(db, user, student_id)
    st = db.get(User, student_id)
    try:
        return {"method": "ai", **ai.student_recommendations(db, user.id, snapshot=student_summary(db, st))}
    except ai.AIUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message)


# --------------------------------------------------------------------------- feedback & notes

@router.post("/students/{student_id}/feedback", status_code=201)
def add_feedback(student_id: int, body: FeedbackIn, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ensure_mentor_access(db, user, student_id)
    f = MentorFeedback(mentor_id=user.id, student_id=student_id, kind=body.kind, category=body.category,
                       content=body.content.strip())
    db.add(f)
    if body.kind == "feedback":
        title = "🎉 Encouragement from your mentor" if body.category == "encouragement" else "New feedback from your mentor"
        notify(db, student_id, title, body.content[:140], "feedback", "/student/mentoring")
    db.commit()
    return {"id": f.id}


@router.delete("/feedback/{feedback_id}")
def delete_feedback(feedback_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    f = db.get(MentorFeedback, feedback_id)
    if not f or f.mentor_id != user.id:
        raise HTTPException(404, "Feedback not found")
    db.delete(f)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- improvement plans & goals

def _own_plan(db: Session, user: User, plan_id: int) -> ImprovementPlan:
    p = db.get(ImprovementPlan, plan_id)
    if not p or p.mentor_id != user.id:
        raise HTTPException(404, "Plan not found")
    return p


@router.post("/students/{student_id}/plans", status_code=201)
def create_plan(student_id: int, body: PlanIn, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ensure_mentor_access(db, user, student_id)
    plan = ImprovementPlan(mentor_id=user.id, student_id=student_id, title=body.title, description=body.description)
    for g in body.goals:
        plan.goals.append(PlanGoal(**g.model_dump()))
    db.add(plan)
    notify(db, student_id, "New improvement plan", f"Your mentor created the plan '{body.title}'.", "plan",
           "/student/mentoring")
    db.commit()
    return _plans_with_progress(db, [plan])[0]


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: int, body: PlanUpdate, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    plan = _own_plan(db, user, plan_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    db.commit()
    return _plans_with_progress(db, [plan])[0]


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    plan = _own_plan(db, user, plan_id)
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/plans/{plan_id}/goals", status_code=201)
def add_goal(plan_id: int, body: GoalIn, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    plan = _own_plan(db, user, plan_id)
    plan.goals.append(PlanGoal(**body.model_dump()))
    notify(db, plan.student_id, "New goal from your mentor", body.title, "plan", "/student/mentoring")
    db.commit()
    return _plans_with_progress(db, [plan])[0]


@router.put("/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalIn, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    goal = db.get(PlanGoal, goal_id)
    if not goal or goal.plan.mentor_id != user.id:
        raise HTTPException(404, "Goal not found")
    for k, v in body.model_dump().items():
        setattr(goal, k, v)
    db.commit()
    return _plans_with_progress(db, [goal.plan])[0]


@router.post("/goals/{goal_id}/status")
def set_goal_status(goal_id: int, status: str, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    goal = db.get(PlanGoal, goal_id)
    if not goal or goal.plan.mentor_id != user.id:
        raise HTTPException(404, "Goal not found")
    if status not in ("pending", "completed"):
        raise HTTPException(400, "Status must be pending or completed")
    goal.status = status
    goal.completed_at = datetime.now(timezone.utc) if status == "completed" else None
    db.commit()
    return _plans_with_progress(db, [goal.plan])[0]


@router.delete("/goals/{goal_id}")
def delete_goal(goal_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    goal = db.get(PlanGoal, goal_id)
    if not goal or goal.plan.mentor_id != user.id:
        raise HTTPException(404, "Goal not found")
    db.delete(goal)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- follow-up sessions

@router.get("/sessions")
def list_sessions(status: str | None = None, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    stmt = select(MentorSession).where(MentorSession.mentor_id == user.id)
    if status:
        stmt = stmt.where(MentorSession.status == status)
    return [mentor_session_out(s) for s in db.scalars(stmt.order_by(MentorSession.scheduled_at.desc()))]


@router.post("/sessions", status_code=201)
def create_session(body: MentorSessionIn, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    ensure_mentor_access(db, user, body.student_id)
    s = MentorSession(mentor_id=user.id, **body.model_dump())
    db.add(s)
    notify(db, body.student_id, "Mentoring session scheduled",
           f"{user.full_name} scheduled a session on {body.scheduled_at.strftime('%d %b %Y, %H:%M')}: {body.agenda[:100]}",
           "session", "/student/mentoring")
    db.commit()
    return mentor_session_out(s)


@router.patch("/sessions/{session_id}")
def update_session(session_id: int, body: MentorSessionUpdate, user: User = Depends(require_mentor),
                   db: Session = Depends(get_db)):
    s = db.get(MentorSession, session_id)
    if not s or s.mentor_id != user.id:
        raise HTTPException(404, "Session not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(s, k, v)
    if "scheduled_at" in data or data.get("status") == "cancelled":
        notify(db, s.student_id, "Mentoring session updated",
               f"Your session is now {s.status}" + (f" on {s.scheduled_at.strftime('%d %b %Y, %H:%M')}" if s.status == "scheduled" else ""),
               "session", "/student/mentoring")
    db.commit()
    return mentor_session_out(s)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, user: User = Depends(require_mentor), db: Session = Depends(get_db)):
    s = db.get(MentorSession, session_id)
    if not s or s.mentor_id != user.id:
        raise HTTPException(404, "Session not found")
    db.delete(s)
    db.commit()
    return {"ok": True}
