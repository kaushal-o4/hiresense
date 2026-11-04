"""Points, badges and mentor-goal tracking.

Anti-gaming rules:
  * Each activity (source_type, source_id) can earn a given reward at most once (DB unique constraint).
  * Per-activity daily caps from `reward_rules.daily_cap`.
  * Minimum-quality requirements (answer count/length, verified active seconds) checked by callers.
  * Flagged activities never earn rewards; admins can revoke points for flagged items.
"""
from datetime import date, datetime, timedelta, timezone

from ..odm import func, select
from ..odm import Session

from ..models import (
    AssessmentResult, Badge, Challenge, ChallengeCompletion, EnglishSession, ImprovementPlan, InterviewSession,
    PlanGoal, PointTransaction, PracticeExercise, RewardRule, StudentBadge, VocabularyReview,
)
from . import english_vocab
from .common import notify


def _today_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def award_points(db: Session, student_id: int, activity_type: str, source_type: str, source_id: int,
                 reason: str) -> PointTransaction | None:
    rule = db.scalar(select(RewardRule).where(RewardRule.activity_type == activity_type))
    if not rule or not rule.active or rule.points <= 0:
        return None
    exists = db.scalar(select(PointTransaction.id).where(
        PointTransaction.student_id == student_id, PointTransaction.activity_type == activity_type,
        PointTransaction.source_type == source_type, PointTransaction.source_id == source_id))
    if exists:
        return None
    today_count = db.scalar(select(func.count(PointTransaction.id)).where(
        PointTransaction.student_id == student_id, PointTransaction.activity_type == activity_type,
        PointTransaction.created_at >= _today_start())) or 0
    if rule.daily_cap and today_count >= rule.daily_cap:
        return None
    tx = PointTransaction(student_id=student_id, points=rule.points, activity_type=activity_type,
                          source_type=source_type, source_id=source_id, reason=reason)
    db.add(tx)
    db.flush()
    notify(db, student_id, f"+{rule.points} points", reason, "reward", "/student/rewards")
    return tx


def rule_requirements(db: Session, activity_type: str) -> dict:
    rule = db.scalar(select(RewardRule).where(RewardRule.activity_type == activity_type))
    return (rule.requirements or {}) if rule else {}


def activity_dates(db: Session, student_id: int) -> set[date]:
    dates: set[date] = set()
    for (d,) in db.execute(select(InterviewSession.completed_at).where(
            InterviewSession.student_id == student_id, InterviewSession.status == "completed",
            InterviewSession.flagged.is_(False))):
        if d:
            dates.add(d.date())
    for (d,) in db.execute(select(EnglishSession.ended_at).where(
            EnglishSession.student_id == student_id, EnglishSession.status == "completed",
            EnglishSession.active_seconds >= 60)):
        if d:
            dates.add(d.date())
    for (d,) in db.execute(select(AssessmentResult.submitted_at).where(
            AssessmentResult.student_id == student_id, AssessmentResult.submitted_at.is_not(None),
            AssessmentResult.flagged.is_(False))):
        if d:
            dates.add(d.date())
    for (d,) in db.execute(select(PracticeExercise.completed_at).where(
            PracticeExercise.student_id == student_id, PracticeExercise.status == "completed",
            PracticeExercise.active_seconds >= 10)):
        if d:
            dates.add(d.date())
    return dates


def streaks(db: Session, student_id: int) -> tuple[int, int]:
    """Return (current_streak, longest_streak) in days of verified activity."""
    return streak_lengths(activity_dates(db, student_id))


def streak_lengths(days) -> tuple[int, int]:
    """(current, longest) run of consecutive days; the current run may end today or yesterday."""
    dates = sorted(set(days))
    if not dates:
        return 0, 0
    longest = run = 1
    for a, b in zip(dates, dates[1:]):
        run = run + 1 if (b - a).days == 1 else 1
        longest = max(longest, run)
    today = datetime.now(timezone.utc).date()
    current = 0
    if dates[-1] >= today - timedelta(days=1):
        current = 1
        for a, b in zip(reversed(dates[:-1]), reversed(dates[1:])):
            if (b - a).days == 1:
                current += 1
            else:
                break
    return current, longest


def badge_stats(db: Session, student_id: int) -> dict:
    base = select(InterviewSession).where(InterviewSession.student_id == student_id,
                                          InterviewSession.status == "completed",
                                          InterviewSession.flagged.is_(False))
    sessions = db.scalars(base).all()
    scored = [s.overall_score for s in sessions if s.overall_score is not None]
    tech = [s.overall_score for s in sessions if s.overall_score is not None and s.category == "technical"]
    english = db.scalars(select(EnglishSession).where(EnglishSession.student_id == student_id,
                                                      EnglishSession.status == "completed")).all()
    english_scores = [e.overall_score for e in english if e.overall_score is not None]
    passed = db.scalar(select(func.count(AssessmentResult.id)).where(
        AssessmentResult.student_id == student_id, AssessmentResult.passed.is_(True),
        AssessmentResult.flagged.is_(False))) or 0
    current, longest = streaks(db, student_id)
    exercises = db.scalars(select(PracticeExercise).where(PracticeExercise.student_id == student_id,
                                                          PracticeExercise.status == "completed")).all()
    exercise_seconds = sum(x.active_seconds for x in exercises)
    return {
        "interviews_completed": len(sessions),
        "avg_interview_score": round(sum(scored) / len(scored), 1) if scored else 0,
        "technical_best_score": max(tech) if tech else 0,
        "high_score_interviews": sum(1 for s in scored if s >= 80),
        "english_minutes": round((sum(e.active_seconds for e in english) + exercise_seconds) / 60, 1),
        "pronunciation_drills": sum(1 for x in exercises if x.kind == "pronunciation"),
        "speaking_exercises": sum(1 for x in exercises if x.kind == "speaking"),
        "english_sessions": sum(1 for e in english if e.active_seconds >= 60),
        "english_avg_score": round(sum(english_scores) / len(english_scores), 1) if english_scores else 0,
        "assessments_passed": passed,
        **english_vocab_stats(db, student_id),
        "streak_days": longest,
        "current_streak": current,
    }


def english_vocab_stats(db: Session, student_id: int) -> dict:
    c = english_vocab.counts(db, student_id)
    return {"english_words_learned": c["learned"], "english_words_mastered": c["mastered"],
            "english_plan_days": english_vocab.plan_days_completed(db, student_id)}


def evaluate_badges(db: Session, student_id: int) -> list[Badge]:
    stats = badge_stats(db, student_id)
    owned = set(db.scalars(select(StudentBadge.badge_id).where(StudentBadge.student_id == student_id)))
    new = []
    for badge in db.scalars(select(Badge).where(Badge.active.is_(True))):
        if badge.id in owned:
            continue
        value = stats.get(badge.criteria_type)
        if value is None or value < badge.threshold:
            continue
        db.add(StudentBadge(student_id=student_id, badge_id=badge.id))
        if badge.points > 0:
            db.add(PointTransaction(student_id=student_id, points=badge.points, activity_type="badge",
                                    source_type="badge", source_id=badge.id, reason=f"Earned badge: {badge.name}"))
        notify(db, student_id, f"{badge.icon} New badge: {badge.name}", badge.description, "badge", "/student/rewards")
        new.append(badge)
    db.flush()
    return new


def total_points(db: Session, student_id: int) -> int:
    return db.scalar(select(func.coalesce(func.sum(PointTransaction.points), 0)).where(
        PointTransaction.student_id == student_id, PointTransaction.revoked.is_(False))) or 0


def revoke_for_source(db: Session, student_id: int, source_type: str, source_id: int) -> int:
    txs = db.scalars(select(PointTransaction).where(
        PointTransaction.student_id == student_id, PointTransaction.source_type == source_type,
        PointTransaction.source_id == source_id, PointTransaction.revoked.is_(False))).all()
    for tx in txs:
        tx.revoked = True
    return sum(t.points for t in txs)


# --------------------------------------------------------------------------- mentor goals

def _goal_progress(db: Session, student_id: int, goal: PlanGoal) -> int:
    since = goal.created_at
    if goal.goal_type == "mock_interview":
        q = select(InterviewSession).where(InterviewSession.student_id == student_id,
                                           InterviewSession.status == "completed",
                                           InterviewSession.flagged.is_(False),
                                           InterviewSession.completed_at >= since)
        items = db.scalars(q).all()
        if goal.target_score is not None:
            items = [s for s in items if (s.overall_score or 0) >= goal.target_score]
        return len(items)
    if goal.goal_type == "english_practice":
        items = db.scalars(select(EnglishSession).where(
            EnglishSession.student_id == student_id, EnglishSession.status == "completed",
            EnglishSession.active_seconds >= 60, EnglishSession.ended_at >= since)).all()
        if goal.target_score is not None:
            items = [s for s in items if (s.overall_score or 0) >= goal.target_score]
        drills = db.scalars(select(PracticeExercise).where(
            PracticeExercise.student_id == student_id, PracticeExercise.status == "completed",
            PracticeExercise.completed_at >= since)).all()
        if goal.target_score is not None:
            drills = [d for d in drills if (d.score or 0) >= goal.target_score]
        return len(items) + len(drills)
    if goal.goal_type == "assessment":
        items = db.scalars(select(AssessmentResult).where(
            AssessmentResult.student_id == student_id, AssessmentResult.submitted_at >= since,
            AssessmentResult.flagged.is_(False))).all()
        if goal.target_score is not None:
            items = [r for r in items if (r.score or 0) >= goal.target_score]
        return len(items)
    return 1 if goal.status == "completed" else 0


def goal_progress(db: Session, student_id: int, goal: PlanGoal) -> int:
    return _goal_progress(db, student_id, goal)


def refresh_goals(db: Session, student_id: int, goal_type: str) -> None:
    goals = db.scalars(select(PlanGoal).join(ImprovementPlan).where(
        ImprovementPlan.student_id == student_id, ImprovementPlan.status == "active",
        PlanGoal.goal_type == goal_type, PlanGoal.status == "pending")).all()
    for goal in goals:
        if _goal_progress(db, student_id, goal) >= goal.target_count:
            complete_goal(db, student_id, goal)


def complete_goal(db: Session, student_id: int, goal: PlanGoal) -> None:
    goal.status = "completed"
    goal.completed_at = datetime.now(timezone.utc)
    plan = goal.plan
    notify(db, plan.mentor_id, "Goal completed", f"A student completed the goal '{goal.title}'.", "goal",
           f"/mentor/students/{student_id}")
    award_points(db, student_id, "goal_completed", "plan_goal", goal.id, f"Completed mentor goal: {goal.title}")


# --------------------------------------------------------------------------- challenges

CHALLENGE_METRICS = ("english_minutes", "english_sessions", "speaking_exercises", "pronunciation_drills",
                     "interviews_completed", "assessments_passed", "english_reviews")


def period_bounds(period: str, now: datetime | None = None) -> tuple[datetime, str]:
    now = now or datetime.now(timezone.utc)
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        start = day - timedelta(days=day.weekday())
        iso = start.isocalendar()
        return start, f"{iso.year}-W{iso.week:02d}"
    return day, day.date().isoformat()


def challenge_progress(db: Session, student_id: int, challenge: Challenge) -> float:
    since, _ = period_bounds(challenge.period)
    m = challenge.metric
    if m in ("english_minutes", "english_sessions"):
        sessions = db.scalars(select(EnglishSession).where(
            EnglishSession.student_id == student_id, EnglishSession.status == "completed",
            EnglishSession.ended_at >= since)).all()
        if m == "english_sessions":
            return float(sum(1 for s in sessions if s.active_seconds >= 60))
        drills = db.scalars(select(PracticeExercise).where(
            PracticeExercise.student_id == student_id, PracticeExercise.status == "completed",
            PracticeExercise.completed_at >= since)).all()
        return round((sum(s.active_seconds for s in sessions) + sum(d.active_seconds for d in drills)) / 60, 1)
    if m in ("speaking_exercises", "pronunciation_drills"):
        kind = "speaking" if m == "speaking_exercises" else "pronunciation"
        return float(db.scalar(select(func.count(PracticeExercise.id)).where(
            PracticeExercise.student_id == student_id, PracticeExercise.kind == kind,
            PracticeExercise.status == "completed", PracticeExercise.completed_at >= since)) or 0)
    if m == "english_reviews":
        return float(db.scalar(select(func.count(VocabularyReview.id)).where(
            VocabularyReview.student_id == student_id, VocabularyReview.created_at >= since)) or 0)
    if m == "interviews_completed":
        return float(db.scalar(select(func.count(InterviewSession.id)).where(
            InterviewSession.student_id == student_id, InterviewSession.status == "completed",
            InterviewSession.flagged.is_(False), InterviewSession.completed_at >= since)) or 0)
    if m == "assessments_passed":
        return float(db.scalar(select(func.count(AssessmentResult.id)).where(
            AssessmentResult.student_id == student_id, AssessmentResult.passed.is_(True),
            AssessmentResult.flagged.is_(False), AssessmentResult.submitted_at >= since)) or 0)
    return 0.0


def evaluate_challenges(db: Session, student_id: int) -> list[Challenge]:
    """Award each active challenge at most once per period when its target is reached."""
    done = []
    for ch in db.scalars(select(Challenge).where(Challenge.active.is_(True))):
        _, key = period_bounds(ch.period)
        if db.scalar(select(ChallengeCompletion.id).where(
                ChallengeCompletion.challenge_id == ch.id, ChallengeCompletion.student_id == student_id,
                ChallengeCompletion.period_key == key)):
            continue
        if challenge_progress(db, student_id, ch) < ch.target:
            continue
        comp = ChallengeCompletion(challenge_id=ch.id, student_id=student_id, period_key=key)
        db.add(comp)
        db.flush()
        if ch.points > 0:
            db.add(PointTransaction(student_id=student_id, points=ch.points, activity_type="challenge",
                                    source_type="challenge_completion", source_id=comp.id,
                                    reason=f"Challenge completed: {ch.title}"))
        notify(db, student_id, f"🔥 Challenge complete: {ch.title}", f"+{ch.points} points", "reward", "/student/rewards")
        done.append(ch)
    db.flush()
    return done


def after_activity(db: Session, student_id: int, goal_type: str | None = None) -> list[str]:
    """Run every automatic reward/goal check after a verified activity. Returns new badge names."""
    badges = evaluate_badges(db, student_id)
    evaluate_challenges(db, student_id)
    if goal_type:
        refresh_goals(db, student_id, goal_type)
    return [b.name for b in badges]
