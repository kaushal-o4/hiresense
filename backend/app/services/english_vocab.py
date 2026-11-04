"""Personal English word list with spaced repetition (Leitner boxes), a daily plan, and English progress numbers.

No language-model call is made here. Cards come from the corrections Aria already gave in practice sessions
(front = what the student said, back = the corrected form, plus her explanation) or from words the student adds.

Leitner boxes 1-5. Knowing a card moves it up one box and waits longer before showing it again (INTERVAL_DAYS);
not knowing it sends it back to box 1 (shown again tomorrow). Knowing a box-5 card marks it *mastered*. A card in
box 4 or higher counts as *learned* (it was known on at least three separate reviews in a row).

Days are UTC days, like the rest of the app (streaks, daily challenges).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from ..odm import Session, func, select

from ..models import (
    EnglishSession, InterviewAnswer, InterviewQuestion, InterviewSession, PointTransaction, VocabularyItem,
    VocabularyReview,
)

MAX_BOX = 5
INTERVAL_DAYS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
MASTERED_INTERVAL_DAYS = 30
LEARNED_BOX = 4
DAILY_REVIEW_TARGET = 10
REVIEW_BATCH = 20
MAX_ITEMS = 500  # per student; the oldest mastered cards make room after that

PLAN_ACTIVITY = "english_daily_plan"
MASTERED_ACTIVITY = "english_word_mastered"

# Which practice mode helps most with the weakest score of the last evaluated session.
MODE_FOR_SKILL = {
    "grammar": "english_learning",
    "sentence_formation": "english_learning",
    "vocabulary": "free_conversation",
    "fluency": "confidence",
}
MODE_LABELS = {"free_conversation": "Free conversation", "english_learning": "English learning",
               "confidence": "Confidence building"}
SKILL_LABELS = {"grammar": "grammar", "sentence_formation": "sentence formation", "vocabulary": "vocabulary",
                "fluency": "fluency"}

_SPACE = re.compile(r"\s+")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def day_start(d: date | None = None) -> datetime:
    d = d or _now().date()
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def normalise(text: str) -> str:
    """Key for de-duplication: lower case, single spaces, no trailing punctuation."""
    return _SPACE.sub(" ", (text or "").replace("’", "'").strip().lower()).strip(" .!?,;:")[:300]


# --------------------------------------------------------------------------- Leitner rules (pure)

def next_state(box: int, knew: bool, now: datetime) -> tuple[int, datetime, bool]:
    """(new box, next due time, became_mastered) after one answer."""
    box = max(1, min(MAX_BOX, int(box or 1)))
    if not knew:
        return 1, now + timedelta(days=INTERVAL_DAYS[1]), False
    if box == MAX_BOX:
        return MAX_BOX, now + timedelta(days=MASTERED_INTERVAL_DAYS), True
    new_box = box + 1
    return new_box, now + timedelta(days=INTERVAL_DAYS[new_box]), False


# --------------------------------------------------------------------------- collecting cards

def _add(db: Session, student_id: int, *, kind: str, front: str, back: str, explanation: str | None,
         session_id: int | None, now: datetime) -> VocabularyItem | None:
    front, back = (front or "").strip()[:300], (back or "").strip()[:300]
    key = normalise(back)
    if not front or not key or (kind == "correction" and normalise(front) == key):
        return None
    item = db.scalar(select(VocabularyItem).where(VocabularyItem.student_id == student_id, VocabularyItem.key == key))
    if item is not None:
        if kind == "correction":
            # The same mistake again: it is not learned yet, so start this card over.
            item.front, item.box, item.due_at, item.mastered_at = front, 1, now, None
            if explanation:
                item.explanation = explanation[:500]
            item.source_session_id = session_id or item.source_session_id
        return item
    item = VocabularyItem(student_id=student_id, key=key, kind=kind, front=front, back=back,
                          explanation=(explanation or "")[:500] or None, source_session_id=session_id,
                          box=1, due_at=now, reviews=0, correct=0)
    db.add(item)
    return item


def collect_corrections(db: Session, student_id: int, session_id: int, corrections: list[dict]) -> int:
    """Add the corrections Aria just gave as cards (called when a message is saved; does not commit)."""
    now = _now()
    added = 0
    for c in corrections or []:
        if _add(db, student_id, kind="correction", front=c.get("original", ""), back=c.get("corrected", ""),
                explanation=(c.get("explanation") or "").strip() or None, session_id=session_id, now=now):
            added += 1
    if added:
        db.flush()
        _trim(db, student_id)
    return added


def add_word(db: Session, student_id: int, word: str, meaning: str, example: str | None = None) -> VocabularyItem:
    now = _now()
    item = _add(db, student_id, kind="word", front=word, back=meaning, explanation=example, session_id=None, now=now)
    if item is None:
        raise ValueError("Please enter a word and its meaning.")
    db.flush()
    _trim(db, student_id)
    return item


def _trim(db: Session, student_id: int) -> None:
    count = db.scalar(select(func.count(VocabularyItem.id)).where(VocabularyItem.student_id == student_id)) or 0
    if count <= MAX_ITEMS:
        return
    old = db.scalars(select(VocabularyItem).where(VocabularyItem.student_id == student_id,
                                                  VocabularyItem.mastered_at.is_not(None))
                     .order_by(VocabularyItem.mastered_at)).all()
    for item in old[:count - MAX_ITEMS]:
        db.delete(item)


# --------------------------------------------------------------------------- reviewing

def due_items(db: Session, student_id: int, limit: int = REVIEW_BATCH) -> list[VocabularyItem]:
    return list(db.scalars(select(VocabularyItem).where(
        VocabularyItem.student_id == student_id, VocabularyItem.due_at <= _now()
    ).order_by(VocabularyItem.due_at, VocabularyItem.id).limit(limit)))


def review(db: Session, student_id: int, item_id: int, knew: bool) -> tuple[VocabularyItem, bool] | None:
    """Record one answer. Returns (item, became_mastered), or None if the card is not the student's."""
    item = db.get(VocabularyItem, item_id)
    if not item or item.student_id != student_id:
        return None
    now = _now()
    before = item.box
    box, due, mastered = next_state(item.box, knew, now)
    item.box, item.due_at, item.last_reviewed = box, due, now
    item.reviews += 1
    item.correct += 1 if knew else 0
    became = mastered and item.mastered_at is None
    if became:
        item.mastered_at = now
    if not knew:
        item.mastered_at = None
    db.add(VocabularyReview(student_id=student_id, item_id=item.id, knew=bool(knew), box_before=before, box_after=box))
    db.flush()
    return item, became


def item_out(item: VocabularyItem) -> dict:
    return {"id": item.id, "kind": item.kind, "front": item.front, "back": item.back, "explanation": item.explanation,
            "box": item.box, "due_at": item.due_at, "reviews": item.reviews, "correct": item.correct,
            "learned": item.box >= LEARNED_BOX, "mastered": item.mastered_at is not None,
            "source_session_id": item.source_session_id, "created_at": item.created_at}


def counts(db: Session, student_id: int) -> dict:
    items = db.scalars(select(VocabularyItem).where(VocabularyItem.student_id == student_id)).all()
    now = _now()
    return {"total": len(items),
            "due": sum(1 for i in items if _aware(i.due_at) <= now),
            "learned": sum(1 for i in items if i.box >= LEARNED_BOX),
            "mastered": sum(1 for i in items if i.mastered_at is not None),
            "boxes": {str(b): sum(1 for i in items if i.box == b) for b in range(1, MAX_BOX + 1)}}


def reviews_since(db: Session, student_id: int, since: datetime) -> list[VocabularyReview]:
    return list(db.scalars(select(VocabularyReview).where(VocabularyReview.student_id == student_id,
                                                         VocabularyReview.created_at >= since)))


# --------------------------------------------------------------------------- daily plan

def recommended_mode(db: Session, student_id: int, before: datetime) -> tuple[str, str | None]:
    """(learning mode, weakest skill) from the last session evaluated before `before` (so the plan stays the
    same all day). With no evaluated session yet: free conversation, no skill."""
    last = db.scalar(select(EnglishSession).where(
        EnglishSession.student_id == student_id, EnglishSession.status == "completed",
        EnglishSession.overall_score.is_not(None), EnglishSession.ended_at < before
    ).order_by(EnglishSession.ended_at.desc()).limit(1))
    scores = {k: v for k, v in ((last.scores or {}) if last else {}).items() if k in MODE_FOR_SKILL and v is not None}
    if not scores:
        return "free_conversation", None
    skill = min(sorted(scores), key=lambda k: scores[k])
    return MODE_FOR_SKILL[skill], skill


def _answered_interview_today(db: Session, student_id: int, since: datetime) -> bool:
    session_ids = list(db.scalars(select(InterviewSession.id).where(InterviewSession.student_id == student_id)))
    if not session_ids:
        return False
    question_ids = list(db.scalars(select(InterviewQuestion.id).where(InterviewQuestion.session_id.in_(session_ids))))
    if not question_ids:
        return False
    return db.scalar(select(InterviewAnswer.id).where(InterviewAnswer.question_id.in_(question_ids),
                                                      InterviewAnswer.created_at >= since).limit(1)) is not None


def daily_plan(db: Session, student_id: int) -> dict:
    """Today's plan. Every item is checked from what the student actually did today; nothing is ticked by hand."""
    today = _now().date()
    start = day_start(today)
    items = []

    reviewed_today = {r.item_id for r in reviews_since(db, student_id, start)}
    due_now = db.scalar(select(func.count(VocabularyItem.id)).where(
        VocabularyItem.student_id == student_id, VocabularyItem.due_at <= _now())) or 0
    target = min(DAILY_REVIEW_TARGET, due_now + len(reviewed_today))
    if target > 0:
        done_n = min(len(reviewed_today), target)
        items.append({"id": "review", "title": f"Review {target} word{'s' if target != 1 else ''}",
                      "detail": "Cards from your corrections, spaced so you see each one just before you forget it.",
                      "target": target, "progress": done_n, "done": done_n >= target,
                      "link": "/student/english/vocabulary"})

    mode, skill = recommended_mode(db, student_id, start)
    talked = db.scalars(select(EnglishSession).where(
        EnglishSession.student_id == student_id, EnglishSession.status == "completed",
        EnglishSession.ended_at >= start, EnglishSession.active_seconds >= 60)).all()
    talked_in_mode = [s for s in talked if (s.learning_mode or "free_conversation") == mode]
    items.append({"id": "conversation", "title": f"One conversation in {MODE_LABELS[mode]} mode",
                  "detail": (f"Your lowest score last time was {SKILL_LABELS[skill]}, and this mode works on it."
                             if skill else "At least one verified minute of talking with Aria."),
                  "target": 1, "progress": min(1, len(talked_in_mode)), "done": bool(talked_in_mode),
                  "link": f"/student/english?mode={mode}", "learning_mode": mode})

    answered = _answered_interview_today(db, student_id, start)
    items.append({"id": "interview", "title": "Answer one interview question",
                  "detail": "Any mock interview counts, typed or spoken.", "target": 1, "progress": int(answered),
                  "done": answered, "link": "/student/interviews"})

    done = sum(1 for i in items if i["done"])
    return {"date": today.isoformat(), "items": items, "completed": done, "total": len(items),
            "all_done": done == len(items)}


def plan_source_id(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


def plan_days_completed(db: Session, student_id: int) -> int:
    return db.scalar(select(func.count(PointTransaction.id)).where(
        PointTransaction.student_id == student_id, PointTransaction.activity_type == PLAN_ACTIVITY,
        PointTransaction.revoked.is_(False))) or 0


def check_plan(db: Session, student_id: int, plan: dict | None = None) -> dict:
    """Award the once-a-day points when every plan item is done (safe to call repeatedly)."""
    from .rewards import award_points  # local import: rewards imports this module for badge stats

    plan = plan or daily_plan(db, student_id)
    if plan["all_done"]:
        award_points(db, student_id, PLAN_ACTIVITY, PLAN_ACTIVITY, plan_source_id(date.fromisoformat(plan["date"])),
                     "Finished today's English plan")
    return plan


# --------------------------------------------------------------------------- progress

def progress(db: Session, student_id: int, weeks: int = 8) -> dict:
    """Numbers for the English progress view: words, review accuracy by week and score trend by session."""
    now = _now()
    c = counts(db, student_id)
    since = day_start((now - timedelta(weeks=weeks)).date())
    reviews = reviews_since(db, student_id, since)
    this_monday = now.date() - timedelta(days=now.weekday())
    weekly = []
    for w in range(weeks - 1, -1, -1):
        monday = this_monday - timedelta(weeks=w)
        lo, hi = day_start(monday), day_start(monday + timedelta(days=7))
        rs = [r for r in reviews if lo <= _aware(r.created_at) < hi]
        weekly.append({"week": monday.isoformat(), "reviews": len(rs),
                       "accuracy": round(100 * sum(r.knew for r in rs) / len(rs)) if rs else None})
    total_reviews = len(reviews)
    sessions = db.scalars(select(EnglishSession).where(
        EnglishSession.student_id == student_id, EnglishSession.status == "completed",
        EnglishSession.overall_score.is_not(None)).order_by(EnglishSession.ended_at.desc()).limit(20)).all()
    trend = [{"session_id": s.id, "date": _aware(s.ended_at).date().isoformat() if s.ended_at else None,
              "overall": s.overall_score,
              **{k: (s.scores or {}).get(k) for k in ("grammar", "vocabulary", "fluency", "sentence_formation")}}
             for s in reversed(sessions)]
    return {"words": c, "review_accuracy": round(100 * sum(r.knew for r in reviews) / total_reviews)
            if total_reviews else None, "reviews_recent": total_reviews, "weekly_reviews": weekly,
            "score_trend": trend, "plan_days_completed": plan_days_completed(db, student_id)}
