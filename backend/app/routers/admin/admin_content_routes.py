# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/routers/admin/admin_content_routes.py
#
# FILE PURPOSE:
# Admin configuration of interview content: categories, question bank, evaluation rubrics, badges,
# reward rules and challenges.
#
# WHAT THIS FILE DOES:
# 1. Create/update interview categories.
# 2. Manage the fallback question bank.
# 3. Create/update evaluation rubrics (criteria weights must be valid).
# 4. Manage badges, reward rules and challenges.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: categories, create_category, update_category, list_questions,
#    create_question, update_question, delete_question, rubrics, _validate_rubric, create_rubric,
#    update_rubric, badges, create_badge, update_badge, reward_rules, update_reward_rule,
#    list_challenges, create_challenge, update_challenge
#
# IMPORTANT CLASSES:
#    - ChallengeIn
#
# API ENDPOINTS DEFINED HERE:
#    - GET /api/admin/categories
#        categories() - admin
#    - POST /api/admin/categories
#        create_category() - admin
#    - PUT /api/admin/categories/{category_id}
#        update_category() - admin
#    - GET /api/admin/questions
#        list_questions() - admin
#    - POST /api/admin/questions
#        create_question() - admin
#    - PUT /api/admin/questions/{question_id}
#        update_question() - admin
#    - DELETE /api/admin/questions/{question_id}
#        delete_question() - admin
#    - GET /api/admin/rubrics
#        rubrics() - admin
#    - POST /api/admin/rubrics
#        create_rubric() - admin
#    - PUT /api/admin/rubrics/{rubric_id}
#        update_rubric() - admin
#    - GET /api/admin/badges
#        badges() - admin
#    - POST /api/admin/badges
#        create_badge() - admin
#    - PUT /api/admin/badges/{badge_id}
#        update_badge() - admin
#    - GET /api/admin/reward-rules
#        reward_rules() - admin
#    - PATCH /api/admin/reward-rules/{rule_id}
#        update_reward_rule() - admin
#    - GET /api/admin/challenges
#        list_challenges() - admin
#    - POST /api/admin/challenges
#        create_challenge() - admin
#    - PUT /api/admin/challenges/{challenge_id}
#        update_challenge() - admin
#
# INPUT:
# Content definitions from the admin pages.
#
# OUTPUT:
# Saved configuration; audit log entries.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/authentication_dependencies.py, app/database_connection.py, app/database_models.py,
#    app/mongodb_data_layer/__init__.py, app/request_validation_schemas.py,
#    app/services/platform_support/audit_and_notification_helpers.py
#    Used by: app/routers/admin/__init__.py
#
# EXECUTION FLOW:
#    Admin edits rubric
#       |
#       v
#    Validated
#       |
#       v
#    Saved
#       |
#       v
#    Used for scoring new answers
#
# IMPORTANT DEPENDENCIES:
#    fastapi, pydantic
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Admin portal: interview categories, question bank, rubrics, badges, reward rules, challenges."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ...mongodb_data_layer import func, select
from ...mongodb_data_layer import Session
from ...database_connection import get_db
from ...authentication_dependencies import client_ip, require_admin
from ...database_models import (
    Badge,
    BankQuestion,
    Challenge,
    ChallengeCompletion,
    EvaluationRubric,
    InterviewCategory,
    RewardRule,
    User,
)
from ...request_validation_schemas import BadgeIn, BankQuestionIn, CategoryIn, RewardRuleUpdate, RubricIn
from ...services.platform_support.audit_and_notification_helpers import audit, paginate

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --------------------------------------------------------------------------- interview configuration

@router.get("/categories")
def categories(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    for c in db.scalars(select(InterviewCategory).order_by(InterviewCategory.id)):
        out.append({"id": c.id, "code": c.code, "name": c.name, "description": c.description,
                    "default_question_count": c.default_question_count, "active": c.active,
                    "question_count": db.scalar(select(func.count(BankQuestion.id)).where(BankQuestion.category_id == c.id)) or 0})
    return out


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(InterviewCategory.id).where(InterviewCategory.code == body.code)):
        raise HTTPException(409, "Category code already exists")
    c = InterviewCategory(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, admin.id, "category.create", "interview_category", c.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"id": c.id}


@router.put("/categories/{category_id}")
def update_category(category_id: int, body: CategoryIn, request: Request, admin: User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    c = db.get(InterviewCategory, category_id)
    if not c:
        raise HTTPException(404, "Category not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit(db, admin.id, "category.update", "interview_category", c.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/questions")
def list_questions(category_id: int | None = None, q: str | None = None, page: int = 1, page_size: int = 20,
                   admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(BankQuestion)
    if category_id:
        stmt = stmt.where(BankQuestion.category_id == category_id)
    if q:
        stmt = stmt.where(BankQuestion.question.ilike(f"%{q}%"))
    items, meta = paginate(db, stmt.order_by(BankQuestion.id.desc()), page, page_size)
    return {"items": [{"id": b.id, "category_id": b.category_id, "category": b.category.name, "question": b.question,
                       "difficulty": b.difficulty, "role_tag": b.role_tag, "active": b.active} for b in items], **meta}


@router.post("/questions", status_code=201)
def create_question(body: BankQuestionIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.get(InterviewCategory, body.category_id):
        raise HTTPException(400, "Category not found")
    b = BankQuestion(**body.model_dump(), created_by=admin.id)
    db.add(b)
    db.flush()
    audit(db, admin.id, "question.create", "question", b.id, {}, client_ip(request))
    db.commit()
    return {"id": b.id}


@router.put("/questions/{question_id}")
def update_question(question_id: int, body: BankQuestionIn, request: Request, admin: User = Depends(require_admin),
                    db: Session = Depends(get_db)):
    b = db.get(BankQuestion, question_id)
    if not b:
        raise HTTPException(404, "Question not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit(db, admin.id, "question.update", "question", b.id, {}, client_ip(request))
    db.commit()
    return {"ok": True}


@router.delete("/questions/{question_id}")
def delete_question(question_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    b = db.get(BankQuestion, question_id)
    if not b:
        raise HTTPException(404, "Question not found")
    db.delete(b)
    audit(db, admin.id, "question.delete", "question", question_id, {}, client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/rubrics")
def rubrics(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": r.id, "name": r.name, "applies_to": r.applies_to, "criteria": r.criteria, "active": r.active}
            for r in db.scalars(select(EvaluationRubric).order_by(EvaluationRubric.id))]


def _validate_rubric(body: RubricIn) -> None:
    total = round(sum(c.weight for c in body.criteria), 3)
    if abs(total - 1.0) > 0.01:
        raise HTTPException(400, f"Criterion weights must add up to 1.0 (currently {total})")


@router.post("/rubrics", status_code=201)
def create_rubric(body: RubricIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    _validate_rubric(body)
    r = EvaluationRubric(name=body.name, applies_to=body.applies_to,
                         criteria=[c.model_dump() for c in body.criteria], active=body.active)
    db.add(r)
    db.flush()
    audit(db, admin.id, "rubric.create", "rubric", r.id, {"name": r.name}, client_ip(request))
    db.commit()
    return {"id": r.id}


@router.put("/rubrics/{rubric_id}")
def update_rubric(rubric_id: int, body: RubricIn, request: Request, admin: User = Depends(require_admin),
                  db: Session = Depends(get_db)):
    _validate_rubric(body)
    r = db.get(EvaluationRubric, rubric_id)
    if not r:
        raise HTTPException(404, "Rubric not found")
    r.name, r.applies_to, r.active = body.name, body.applies_to, body.active
    r.criteria = [c.model_dump() for c in body.criteria]
    audit(db, admin.id, "rubric.update", "rubric", r.id, {"name": r.name}, client_ip(request))
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- rewards configuration

@router.get("/badges")
def badges(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ...database_models import StudentBadge
    out = []
    for b in db.scalars(select(Badge).order_by(Badge.id)):
        out.append({"id": b.id, "code": b.code, "name": b.name, "description": b.description, "icon": b.icon,
                    "criteria_type": b.criteria_type, "threshold": b.threshold, "points": b.points, "active": b.active,
                    "awarded": db.scalar(select(func.count(StudentBadge.id)).where(StudentBadge.badge_id == b.id)) or 0})
    return out


@router.post("/badges", status_code=201)
def create_badge(body: BadgeIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Badge.id).where(Badge.code == body.code)):
        raise HTTPException(409, "Badge code already exists")
    b = Badge(**body.model_dump())
    db.add(b)
    db.flush()
    audit(db, admin.id, "badge.create", "badge", b.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"id": b.id}


@router.put("/badges/{badge_id}")
def update_badge(badge_id: int, body: BadgeIn, request: Request, admin: User = Depends(require_admin),
                 db: Session = Depends(get_db)):
    b = db.get(Badge, badge_id)
    if not b:
        raise HTTPException(404, "Badge not found")
    for k, v in body.model_dump().items():
        setattr(b, k, v)
    audit(db, admin.id, "badge.update", "badge", b.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"ok": True}


@router.get("/reward-rules")
def reward_rules(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"id": r.id, "activity_type": r.activity_type, "description": r.description, "points": r.points,
             "daily_cap": r.daily_cap, "requirements": r.requirements, "active": r.active}
            for r in db.scalars(select(RewardRule).order_by(RewardRule.id))]


@router.patch("/reward-rules/{rule_id}")
def update_reward_rule(rule_id: int, body: RewardRuleUpdate, request: Request, admin: User = Depends(require_admin),
                       db: Session = Depends(get_db)):
    r = db.get(RewardRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    data = body.model_dump(exclude_unset=True)
    if "requirements" in data:
        for k, v in (data["requirements"] or {}).items():
            if not isinstance(v, (int, float)) or v < 0:
                raise HTTPException(400, f"Requirement '{k}' must be a non-negative number")
    for k, v in data.items():
        setattr(r, k, v)
    audit(db, admin.id, "reward_rule.update", "reward_rule", r.id, data, client_ip(request))
    db.commit()
    return {"ok": True}

# --------------------------------------------------------------------------- challenges

class ChallengeIn(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(default="", max_length=1000)
    metric: Literal["english_minutes", "english_sessions", "speaking_exercises", "pronunciation_drills",
                    "interviews_completed", "assessments_passed"]
    target: float = Field(gt=0, le=10000)
    period: Literal["daily", "weekly"] = "daily"
    points: int = Field(default=10, ge=0, le=10000)
    active: bool = True


@router.get("/challenges")
def list_challenges(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    for c in db.scalars(select(Challenge).order_by(Challenge.id)):
        completions = db.scalar(select(func.count(ChallengeCompletion.id)).where(ChallengeCompletion.challenge_id == c.id)) or 0
        out.append({"id": c.id, "title": c.title, "description": c.description, "metric": c.metric, "target": c.target,
                    "period": c.period, "points": c.points, "active": c.active, "completions": completions})
    return out


@router.post("/challenges", status_code=201)
def create_challenge(body: ChallengeIn, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    c = Challenge(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, admin.id, "challenge.create", "challenge", c.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"id": c.id}


@router.put("/challenges/{challenge_id}")
def update_challenge(challenge_id: int, body: ChallengeIn, request: Request, admin: User = Depends(require_admin),
                     db: Session = Depends(get_db)):
    c = db.get(Challenge, challenge_id)
    if not c:
        raise HTTPException(404, "Challenge not found")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit(db, admin.id, "challenge.update", "challenge", c.id, body.model_dump(), client_ip(request))
    db.commit()
    return {"ok": True}
