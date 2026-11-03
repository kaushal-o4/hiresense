"""Skill assessments: students take aptitude / technical / coding tests; admins and recruiters manage them.

MCQs are graded instantly on the server. Coding answers are reviewed by AI (the code is not executed);
if AI is unavailable the attempt stays "pending" until it can be evaluated - no score is invented.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from ..odm import or_, select
from ..odm import Session

from ..database import get_db
from ..deps import client_ip, require_roles, require_student
from ..models import Assessment, AssessmentAssignment, AssessmentResult, Job, JobApplication, User
from ..schemas import AssessmentGenerate, AssessmentIn, AssessmentSubmit
from ..serializers import assessment_out, iso, result_out
from ..services import ai
from ..services.common import audit, notify, paginate
from ..services.insights import record_progress
from ..services.rewards import after_activity, award_points

student_router = APIRouter(prefix="/api/student/assessments", tags=["assessments"])
manage_router = APIRouter(prefix="/api/assessments", tags=["assessment management"])

require_manager = require_roles("admin", "recruiter")


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def qtype(q: dict) -> str:
    return q.get("type") or "mcq"


# --------------------------------------------------------------------------- student

def _visible_to_student(db: Session, student_id: int):
    applied_jobs = select(JobApplication.job_id).where(JobApplication.student_id == student_id)
    assigned = select(AssessmentAssignment.assessment_id).where(AssessmentAssignment.student_id == student_id)
    return select(Assessment).where(Assessment.active.is_(True),
                                    or_(Assessment.job_id.is_(None), Assessment.job_id.in_(applied_jobs),
                                        Assessment.id.in_(assigned)))


@student_router.get("")
def available(topic: str | None = None, category: str | None = None, user: User = Depends(require_student),
              db: Session = Depends(get_db)):
    stmt = _visible_to_student(db, user.id)
    if topic:
        stmt = stmt.where(Assessment.topic.ilike(f"%{topic}%"))
    if category:
        stmt = stmt.where(Assessment.category == category)
    items = db.scalars(stmt.order_by(Assessment.id.desc())).all()
    best: dict[int, float] = {}
    for r in db.scalars(select(AssessmentResult).where(AssessmentResult.student_id == user.id,
                                                       AssessmentResult.submitted_at.is_not(None))):
        if r.score is not None and r.score > best.get(r.assessment_id, -1):
            best[r.assessment_id] = r.score
    assignments = {a.assessment_id: a for a in db.scalars(select(AssessmentAssignment).where(
        AssessmentAssignment.student_id == user.id))}
    out = []
    for a in items:
        d = assessment_out(a)
        d.pop("questions")
        d["best_score"] = best.get(a.id)
        d["job_title"] = db.get(Job, a.job_id).title if a.job_id else None
        asg = assignments.get(a.id)
        d["assignment"] = {"status": asg.status, "due_at": iso(asg.due_at)} if asg else None
        out.append(d)
    out.sort(key=lambda d: (not (d["assignment"] and d["assignment"]["status"] == "assigned"),))
    return out


@student_router.get("/results")
def my_results(page: int = 1, page_size: int = 20, user: User = Depends(require_student), db: Session = Depends(get_db)):
    stmt = select(AssessmentResult).where(AssessmentResult.student_id == user.id,
                                          AssessmentResult.submitted_at.is_not(None)).order_by(AssessmentResult.id.desc())
    items, meta = paginate(db, stmt, page, page_size)
    return {"items": [result_out(r) for r in items], **meta}


@student_router.get("/results/{result_id}")
def result_detail(result_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    r = db.get(AssessmentResult, result_id)
    if not r or r.student_id != user.id or not r.submitted_at:
        raise HTTPException(404, "Result not found")
    return {"result": result_out(r), "review": _review(r)}


@student_router.post("/{assessment_id}/start", status_code=201)
def start(assessment_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    a = db.scalar(_visible_to_student(db, user.id).where(Assessment.id == assessment_id))
    if not a:
        raise HTTPException(404, "Assessment not found")
    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent = db.scalars(select(AssessmentResult).where(AssessmentResult.student_id == user.id,
                                                       AssessmentResult.assessment_id == a.id,
                                                       AssessmentResult.started_at >= since)).all()
    if len(recent) >= 3:
        raise HTTPException(429, "You can attempt this assessment at most 3 times per day")
    result = AssessmentResult(assessment_id=a.id, student_id=user.id, answers=[])
    db.add(result)
    db.commit()
    return {"result_id": result.id, "assessment": assessment_out(a), "started_at": result.started_at.isoformat()}


def _grade_coding(db: Session, user_id: int, q: dict, code: str | None) -> dict:
    marks = float(q.get("marks", 5))
    if not code or not str(code).strip() or str(code).strip() == (q.get("starter_code") or "").strip():
        return {"type": "coding", "status": "completed", "score": 0, "marks": 0, "max_marks": marks,
                "feedback": "No solution was submitted."}
    try:
        rev = ai.evaluate_code(db, user_id, question=q["question"], language=q.get("language", "python"),
                               code=str(code), test_cases=q.get("test_cases", []))
    except ai.AIUnavailable as exc:
        return {"type": "coding", "status": "pending", "score": None, "marks": None, "max_marks": marks,
                "feedback": exc.message}
    return {"type": "coding", "status": "completed", "score": rev["score"],
            "marks": round(marks * rev["score"] / 100, 2), "max_marks": marks, "feedback": rev["feedback"],
            "verdicts": rev["verdicts"], "improved_solution": rev["improved_solution"], "method": "ai_review"}


def _grade(db: Session, r: AssessmentResult, only_pending: bool = False) -> None:
    questions = r.assessment.questions or []
    details = list(r.details or [None] * len(questions))
    for i, (q, ans) in enumerate(zip(questions, r.answers)):
        if only_pending and details[i] and details[i].get("status") != "pending":
            continue
        if qtype(q) == "coding":
            details[i] = _grade_coding(db, r.student_id, q, ans)
        else:
            m = float(q.get("marks", 1))
            correct = isinstance(ans, int) and not isinstance(ans, bool) and ans == q["answer_index"]
            details[i] = {"type": "mcq", "status": "completed", "correct": correct, "marks": m if correct else 0,
                          "max_marks": m}
    r.details = details
    r.max_marks = sum(d["max_marks"] for d in details)
    pending = any(d["status"] == "pending" for d in details)
    r.correct_count = sum(1 for d in details if d.get("correct") or (d["type"] == "coding" and (d.get("score") or 0) >= 60))
    r.evaluation_status = "pending" if pending else "completed"
    if pending:
        r.marks_obtained, r.score, r.passed = None, None, None
    else:
        r.marks_obtained = round(sum(d["marks"] for d in details), 2)
        r.score = round(100 * r.marks_obtained / r.max_marks, 1) if r.max_marks else 0
        r.passed = r.score >= r.assessment.pass_percent


def _finalize(db: Session, user: User, r: AssessmentResult) -> list[str]:
    """Progress, rewards, assignment completion and recruiter notification once a score exists."""
    a = r.assessment
    record_progress(db, user.id, "assessment_score", r.score, "assessment", r.id, a.title)
    if a.category in ("aptitude", "coding", "technical"):
        record_progress(db, user.id, f"{a.category}_test_score", r.score, "assessment", r.id, a.title)
    if r.passed and not r.flagged:
        award_points(db, user.id, "assessment_passed", "assessment", a.id, f"Passed assessment: {a.title}")
    new_badges = after_activity(db, user.id, "assessment")
    for asg in db.scalars(select(AssessmentAssignment).where(AssessmentAssignment.assessment_id == a.id,
                                                            AssessmentAssignment.student_id == user.id,
                                                            AssessmentAssignment.status == "assigned")):
        asg.status, asg.result_id = "completed", r.id
    if a.job_id:
        job = db.get(Job, a.job_id)
        notify(db, job.recruiter_id, "Assessment submitted", f"{user.full_name} scored {r.score}% on '{a.title}'.",
               "assessment", f"/recruiter/jobs/{job.id}")
    return new_badges


def _review(r: AssessmentResult) -> list[dict]:
    out = []
    for i, q in enumerate(r.assessment.questions or []):
        ans = r.answers[i] if i < len(r.answers) else None
        d = (r.details or [None] * (i + 1))[i] or {}
        item = {"type": qtype(q), "question": q["question"], "your_answer": ans, "result": d}
        if qtype(q) == "mcq":
            item.update(options=q["options"], answer_index=q["answer_index"], explanation=q.get("explanation", ""))
        else:
            item.update(language=q.get("language"), test_cases=q.get("test_cases", []))
        out.append(item)
    return out


@student_router.post("/results/{result_id}/submit")
def submit(result_id: int, body: AssessmentSubmit, user: User = Depends(require_student), db: Session = Depends(get_db)):
    r = db.get(AssessmentResult, result_id)
    if not r or r.student_id != user.id:
        raise HTTPException(404, "Attempt not found")
    if r.submitted_at:
        raise HTTPException(400, "This attempt has already been submitted")
    a = r.assessment
    questions = a.questions or []
    answers = list(body.answers)[:len(questions)] + [None] * max(0, len(questions) - len(body.answers))
    for q, ans in zip(questions, answers):
        if qtype(q) == "mcq" and ans is not None and not isinstance(ans, int):
            raise HTTPException(422, "Multiple-choice answers must be option numbers")
        if qtype(q) == "coding" and ans is not None and not isinstance(ans, str):
            raise HTTPException(422, "Coding answers must be source code")
    now = datetime.now(timezone.utc)
    elapsed = (now - _aware(r.started_at)).total_seconds()
    reasons = []
    if elapsed > a.time_limit_minutes * 60 + 60:
        reasons.append(f"submitted after the time limit ({int(elapsed // 60)} min)")
    r.answers = answers
    r.submitted_at = now
    _grade(db, r)
    mcq_all_right = all(d.get("correct") for d in r.details if d["type"] == "mcq")
    if len(questions) >= 5 and elapsed < 2 * len(questions) and mcq_all_right:
        reasons.append(f"all answers correct in {int(elapsed)}s")
    if reasons:
        r.flagged = True
        r.flag_reason = "; ".join(reasons)
    db.flush()
    new_badges = _finalize(db, user, r) if r.evaluation_status == "completed" else []
    db.commit()
    return {"result": result_out(r), "review": _review(r), "new_badges": new_badges}


@student_router.post("/results/{result_id}/evaluate")
def evaluate_pending(result_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    r = db.get(AssessmentResult, result_id)
    if not r or r.student_id != user.id or not r.submitted_at:
        raise HTTPException(404, "Result not found")
    if r.evaluation_status != "pending":
        raise HTTPException(400, "This attempt is already fully evaluated")
    _grade(db, r, only_pending=True)
    db.flush()
    if r.evaluation_status == "pending":
        db.commit()
        raise HTTPException(503, next(d["feedback"] for d in r.details if d["status"] == "pending"))
    new_badges = _finalize(db, user, r)
    db.commit()
    return {"result": result_out(r), "review": _review(r), "new_badges": new_badges}


# --------------------------------------------------------------------------- management (admin + recruiter)

def _check_owner(db: Session, user: User, a: Assessment) -> None:
    if user.role == "admin":
        return
    if a.created_by != user.id:
        raise HTTPException(403, "You can only manage assessments you created")


def _validate_job(db: Session, user: User, job_id: int | None) -> None:
    if user.role == "recruiter":
        if not job_id:
            raise HTTPException(400, "Recruiter assessments must be linked to one of your jobs")
        job = db.get(Job, job_id)
        if not job or job.recruiter_id != user.id:
            raise HTTPException(403, "You can only link assessments to your own jobs")
    elif job_id and not db.get(Job, job_id):
        raise HTTPException(404, "Job not found")


def _apply(a: Assessment, body: AssessmentIn) -> None:
    a.title, a.description, a.topic = body.title, body.description, body.topic
    a.category, a.difficulty = body.category, body.difficulty
    a.questions = [q.model_dump() for q in body.questions]
    a.time_limit_minutes, a.pass_percent, a.job_id, a.active = body.time_limit_minutes, body.pass_percent, body.job_id, body.active


@manage_router.get("")
def list_managed(page: int = 1, page_size: int = 20, category: str | None = None,
                 user: User = Depends(require_manager), db: Session = Depends(get_db)):
    stmt = select(Assessment)
    if user.role == "recruiter":
        stmt = stmt.where(Assessment.created_by == user.id)
    if category:
        stmt = stmt.where(Assessment.category == category)
    items, meta = paginate(db, stmt.order_by(Assessment.id.desc()), page, page_size)
    return {"items": [assessment_out(a, with_answers=True) for a in items], **meta}


@manage_router.post("", status_code=201)
def create(body: AssessmentIn, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    _validate_job(db, user, body.job_id)
    a = Assessment(created_by=user.id, title="", topic="")
    _apply(a, body)
    db.add(a)
    db.flush()
    audit(db, user.id, "assessment.create", "assessment", a.id, {"title": a.title}, client_ip(request))
    db.commit()
    return assessment_out(a, with_answers=True)


@manage_router.put("/{assessment_id}")
def update(assessment_id: int, body: AssessmentIn, request: Request, user: User = Depends(require_manager),
           db: Session = Depends(get_db)):
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    _check_owner(db, user, a)
    _validate_job(db, user, body.job_id)
    _apply(a, body)
    audit(db, user.id, "assessment.update", "assessment", a.id, {"title": a.title}, client_ip(request))
    db.commit()
    return assessment_out(a, with_answers=True)


@manage_router.delete("/{assessment_id}")
def delete(assessment_id: int, request: Request, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    _check_owner(db, user, a)
    audit(db, user.id, "assessment.delete", "assessment", a.id, {"title": a.title}, client_ip(request))
    db.delete(a)
    db.commit()
    return {"ok": True}


@manage_router.get("/{assessment_id}/results")
def results(assessment_id: int, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    a = db.get(Assessment, assessment_id)
    if not a:
        raise HTTPException(404, "Assessment not found")
    _check_owner(db, user, a)
    rows = db.scalars(select(AssessmentResult).where(AssessmentResult.assessment_id == a.id,
                                                     AssessmentResult.submitted_at.is_not(None))
                      .order_by(AssessmentResult.score.desc())).all()
    out = []
    for r in rows:
        d = result_out(r)
        d["student_name"] = db.get(User, r.student_id).full_name
        d["review"] = _review(r)
        out.append(d)
    return out


@manage_router.post("/generate")
def generate(body: AssessmentGenerate, user: User = Depends(require_manager), db: Session = Depends(get_db)):
    """Returns AI-drafted questions for review; nothing is saved until the author creates the assessment."""
    try:
        return {"questions": ai.generate_assessment(db, user.id, topic=body.topic, count=body.count,
                                                    difficulty=body.difficulty), "method": "ai"}
    except ai.AIUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message)
