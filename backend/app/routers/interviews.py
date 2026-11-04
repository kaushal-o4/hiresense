"""AI mock interviews (student portal)."""
import difflib
import json
import logging
import queue
import random
import re
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from ..odm import func, select
from ..odm import Session

from .. import database
from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, require_student
from ..models import (
    BankQuestion, EvaluationRubric, InterviewAnswer, InterviewCategory, InterviewQuestion,
    InterviewSession, MentorAssignment, User,
)
from ..schemas import AnswerIn, InterviewStart, TurnIn
from ..serializers import interview_out
from ..services import ai, background, consent, interview_engine, interviewers, local_llm, perf, question_classifier, speech_stream, tts
from ..services.common import get_setting, notify, paginate
from ..services.insights import current_resume, record_progress
from ..services.report_metrics import report_metrics
from ..services.rewards import after_activity, award_points, rule_requirements

router = APIRouter(prefix="/api/student/interviews", tags=["interviews"])
public_router = APIRouter(tags=["interviews"])


@public_router.get("/api/interviewers")
def list_interviewers(user: User = Depends(get_current_user)):
    """Interviewer personalities for the selection screen (behaviour prompts stay on the server)."""
    return [i.public() for i in interviewers.INTERVIEWERS.values()]
logger = logging.getLogger("hiresense.interviews")

DEFAULT_RUBRIC = [
    {"name": "Relevance", "weight": 0.25, "description": "Answers the question that was asked"},
    {"name": "Correctness", "weight": 0.3, "description": "Technically accurate / sound reasoning"},
    {"name": "Clarity", "weight": 0.25, "description": "Well structured, specific, with examples"},
    {"name": "Communication", "weight": 0.2, "description": "Professional, confident, concise language"},
]
QUESTION_TYPES = {"technical", "hr", "behavioral", "communication", "project"}
LIVE_QUESTION_ATTEMPTS = 2  # first try + 1 retry: the candidate is listening and waiting
TEXT_QUESTION_ATTEMPTS = 3


def _rubric(db: Session, applies_to: str) -> list[dict]:
    """Criteria used to score answers: the newest active admin rubric for `applies_to`, or DEFAULT_RUBRIC."""
    r = db.scalar(select(EvaluationRubric).where(EvaluationRubric.applies_to == applies_to,
                                                 EvaluationRubric.active.is_(True)).order_by(EvaluationRubric.id.desc()))
    return r.criteria if r and r.criteria else DEFAULT_RUBRIC


def _get_session(db: Session, user: User, session_id: int) -> InterviewSession:
    """Load an interview that belongs to this student; 404 otherwise (also hides other students' interviews)."""
    s = db.get(InterviewSession, session_id)
    if not s or s.student_id != user.id:
        raise HTTPException(404, "Interview not found")
    return s


def _bank_question(db: Session, session: InterviewSession, level: str) -> tuple[str, str] | None:
    """Pick an unused question from the admin question bank, preferring the wanted difficulty and the
    student's job role. Returns (question text, question type) or None when the bank has nothing suitable left.
    """
    used = [q.text for q in session.questions]
    stmt = select(BankQuestion).join(InterviewCategory).where(BankQuestion.active.is_(True),
                                                              InterviewCategory.active.is_(True))
    if session.category != "mixed":
        stmt = stmt.where(InterviewCategory.code == session.category)
    pool = [q for q in db.scalars(stmt) if not is_repeat(q.question, used)]
    same_level = [q for q in pool if q.difficulty == level]
    pool = same_level or pool
    role = session.job_role.lower()
    preferred = [q for q in pool if q.role_tag and q.role_tag.lower() in role]
    pick = random.choice(preferred or pool) if pool else None
    if not pick:
        return None
    qtype = pick.category.code if pick.category.code in QUESTION_TYPES else "technical"
    return pick.question, qtype


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def is_repeat(text: str, previous: list[str]) -> bool:
    """True if `text` is the same as, or a light rephrasing of, an earlier question."""
    a = _norm(text)
    a_words = {w for w in a.split() if len(w) > 3}
    for p in previous:
        b = _norm(p)
        if not a or not b:
            continue
        if difflib.SequenceMatcher(None, a, b).ratio() >= 0.8:
            return True
        b_words = {w for w in b.split() if len(w) > 3}
        if a_words and b_words and len(a_words & b_words) / len(a_words | b_words) >= 0.7:
            return True
    return False


def _next_level(session: InterviewSession) -> tuple[str, bool]:
    """(difficulty for the next question, whether the student struggled with the previous one)."""
    persona = interviewers.get(session.interviewer)
    prev = session.questions[-1] if session.questions else None
    if prev is None:
        # Start gently: a "hard" interview opens with a medium warm-up question.
        return ("medium" if session.difficulty == "hard" else session.difficulty), False
    ans = prev.answer
    score = ans.score if ans and ans.evaluation_status in ("scored", "completed") else None
    level = ai.next_difficulty(prev.difficulty or session.difficulty, score,
                               up=persona.difficulty_up, down=persona.difficulty_down)
    struggling = score is not None and score < 45
    if struggling and prev.preface:  # already gave one simpler follow-up; move on instead of drilling further
        struggling = False
    return level, struggling


def _add_next_question(db: Session, user: User, session: InterviewSession, stream=None) -> None:
    """stream: optional object with on_delta(json_so_far) and retract() - the live interview speaks the question
    while it is being written (see interview_turn)."""
    position = len(session.questions) + 1
    level, struggling = _next_level(session)
    previous = [q.text for q in session.questions]
    if session.question_source == "ai":
        resume = current_resume(db, user.id)
        analysis = (resume.analysis or {}) if resume and resume.analysis_status == "completed" else {}
        profile = user.student_profile
        skills = list(profile.skills or []) if profile else []
        skills += [s["name"] for s in analysis.get("skills", []) if s.get("name") and s["name"] not in skills]
        history = [{"question": q.text, "type": q.question_type, "difficulty": q.difficulty,
                    "answer": q.answer.text if q.answer else None,
                    "score": q.answer.score if q.answer else None,
                    "communication": (q.answer.scores or {}).get("communication") if q.answer else None}
                   for q in session.questions]
        kwargs = dict(job_role=session.job_role, category=session.category, position=position,
                      total=session.planned_questions, resume_summary=analysis.get("candidate_summary", ""),
                      skills=skills, history=history, difficulty=level, subject=session.subject,
                      projects=[p.get("name", "") for p in analysis.get("projects", [])],
                      topics=analysis.get("recommended_topics", []), struggling=struggling,
                      interviewer=session.interviewer or interviewers.DEFAULT)
        persona = interviewers.get(session.interviewer)
        ctx = interview_engine.candidate_context(analysis, list(profile.skills or []) if profile else [])
        prev_meta = [q.meta or {} for q in session.questions]
        for h, m in zip(history, prev_meta):
            h["meta"] = m
        last_answer = session.questions[-1].answer.text if session.questions and session.questions[-1].answer \
            else None
        signals = interview_engine.answer_signals(last_answer) if last_answer is not None else []
        allow_repeat = any(s["code"] == "repeat_request" for s in signals)
        kwargs.update(candidate_facts=interview_engine.context_block(ctx), signals=signals,
                      coverage=interview_engine.coverage(history, ctx, persona.aspect_order, session.category,
                                                         session.subject),
                      stage=interview_engine.stage(position, session.planned_questions))
        if session.response_mode == "coaching":
            kwargs["response_mode"] = "coaching"
        if stream is not None:
            kwargs["on_delta"] = stream.on_delta
        # Live interviews: one retry (each attempt keeps the candidate waiting ~4 s); text mode: a few more.
        attempts = LIVE_QUESTION_ATTEMPTS if stream is not None else TEXT_QUESTION_ATTEMPTS
        avoid: list[str] = []
        rejected: list[str] = []
        try:
            for attempt in range(attempts):
                if attempt and stream is not None:
                    stream.retract()  # it may already have been spoken: take it back before asking again
                nq = ai.next_interview_question(db, user.id, **kwargs, **({"avoid": avoid} if avoid else {}))
                text = nq["question"].strip()
                nq["topic"] = interview_engine.derive_topic(text, ctx) or nq.get("topic")
                # A clarifying follow-up may stay on the previous question's topic/aspect.
                concept_meta = prev_meta[:-1] if nq.get("is_followup") else prev_meta
                dup, reason = interview_engine.is_duplicate(
                    text, previous, meta=nq, previous_meta=concept_meta, allow_repeat=allow_repeat,
                    similarity=interview_engine.embedding_similarity)
                problems = interview_engine.validate_question(text, persona.max_question_words + 15)
                if not dup and not problems:
                    qtype = nq["question_type"] if nq["question_type"] in QUESTION_TYPES else "technical"
                    session.questions.append(InterviewQuestion(
                        position=position, text=text, question_type=qtype,
                        is_followup=bool(nq["is_followup"]), difficulty=level, preface=nq.get("preface") or None,
                        meta={"source": "ai", "classifier": question_classifier.predict(text),
                              "topic": nq.get("topic") or None, "aspect": nq.get("aspect"),
                              "signals": [s["code"] for s in signals],
                              "attempts": attempt + 1, **({"rejected": rejected} if rejected else {})}))
                    return
                rejected.append(reason or problems[0])
                avoid.append(text)
            # Never log the question text (it may quote the candidate): reason codes only.
            logger.info("interview %s: %d generated question(s) rejected (%s); using a fallback", session.id,
                        len(rejected), ",".join(rejected))
        except ai.AIUnavailable:
            # A one-off failure only affects this question (it is labelled as a bank question). Switch the whole
            # interview to the question bank only when the AI is really unavailable (not running / disabled).
            if not ai.ai_status(db)["available"]:
                session.question_source = "question_bank"
        if stream is not None:
            stream.retract()
        # Fallback 1: a template question about the candidate's own resume that has not been covered yet.
        fb = interview_engine.fallback_question(ctx, history, role=session.job_role, category=session.category,
                                                aspect_order=persona.aspect_order, include_general=False)
        if fb:
            session.questions.append(InterviewQuestion(
                position=position, text=fb["question"], question_type=fb["question_type"], difficulty=level,
                meta={"source": "fallback_template", "topic": fb["topic"], "aspect": fb["aspect"],
                      **({"rejected": rejected} if rejected else {})}))
            return
    picked, source = _bank_question(db, session, level), "question_bank"
    if not picked:  # Fallback 3: general role questions, so an interview can never get stuck
        fb = interview_engine.fallback_question(
            interview_engine.candidate_context(None), [{"question": q.text, "meta": q.meta} for q in session.questions],
            role=session.job_role, category=session.category, aspect_order=(), include_general=True)
        if fb:
            picked, source = (fb["question"], fb["question_type"]), "fallback_template"
    if not picked:
        raise HTTPException(503, "The AI service is unavailable and the question bank has no more questions for "
                                 "this category. Please try again later.")
    session.questions.append(InterviewQuestion(position=position, text=picked[0], question_type=picked[1],
                                               difficulty=level, meta={"source": source}))


@router.post("", status_code=201)
def start_interview(body: InterviewStart, user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Create a new interview session (POST /api/student/interviews).

    Limits: at most `max_interview_questions` questions and 3 interviews in progress. Questions come from the AI
    when it is available, otherwise from the question bank (the response then carries a `notice`). Text interviews
    get their first question immediately; live voice interviews with `defer_first_question` get it written in a
    background thread while the student goes through the setup screen.
    """
    consent.check(user)
    max_q = int(get_setting(db, "max_interview_questions") or 10)
    if body.question_count > max_q:
        raise HTTPException(400, f"An interview can have at most {max_q} questions")
    active = db.scalar(select(func.count(InterviewSession.id)).where(
        InterviewSession.student_id == user.id, InterviewSession.status == "in_progress")) or 0
    if active >= 3:
        raise HTTPException(400, "You already have 3 interviews in progress. Finish or abandon one first.")
    resume = current_resume(db, user.id)
    status = ai.ai_status(db)
    difficulty = body.difficulty or str(get_setting(db, "default_interview_difficulty") or "medium")
    session = InterviewSession(student_id=user.id, job_role=body.job_role.strip(), category=body.category,
                               mode=body.mode, planned_questions=body.question_count, difficulty=difficulty,
                               resume_id=resume.id if resume else None,
                               subject=(body.subject or "").strip() or None, interviewer=body.interviewer,
                               response_mode=body.response_mode,
                               question_source="ai" if status["available"] else "question_bank")
    db.add(session)
    db.flush()
    if body.defer_first_question and body.mode == "voice":
        # Live interview: the candidate first reads the monitoring disclosure and tests camera/microphone. The
        # first question is written meanwhile, so it is usually ready when they press Start.
        db.commit()
        _start_prefetch(session.id, user.id)
        notice = None if session.question_source == "ai" else (
            "AI is unavailable, so questions come from the admin question bank. Answers will be evaluated once AI "
            "becomes available (use 'Retry evaluation').")
        return {"session": interview_out(session, detail=True, own=True), "notice": notice}
    try:
        _add_next_question(db, user, session)
    except HTTPException:
        # The AI call commits the new session before waiting; don't leave an empty interview behind.
        session.status = "abandoned"
        db.commit()
        raise
    db.commit()
    notice = None
    if session.question_source != "ai":
        notice = ("AI is unavailable, so questions come from the admin question bank. Answers will be evaluated "
                  "once AI becomes available (use 'Retry evaluation').")
    return {"session": interview_out(session, detail=True, own=True), "notice": notice}


@router.get("")
def list_interviews(page: int = 1, page_size: int = 10, status: str | None = None,
                    user: User = Depends(require_student), db: Session = Depends(get_db)):
    """The student's own interviews, newest first, paginated (optionally filtered by status)."""
    stmt = select(InterviewSession).where(InterviewSession.student_id == user.id)
    if status:
        stmt = stmt.where(InterviewSession.status == status)
    items, meta = paginate(db, stmt.order_by(InterviewSession.id.desc()), page, page_size)
    return {"items": [interview_out(s, own=True) for s in items], **meta}


@router.get("/{session_id}")
def get_interview(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    """One interview with its questions, answers, scores and report."""
    return interview_out(_get_session(db, user, session_id), detail=True, own=True)


def _evaluate(db: Session, user: User, session: InterviewSession, q: InterviewQuestion, rubric: list[dict],
              full: bool = True) -> str | None:
    """full=False: fast scores only (answer becomes "scored"; detailed feedback follows in the background)."""
    kwargs = dict(job_role=session.job_role, question=q.text, question_type=q.question_type, answer=q.answer.text,
                  rubric=rubric, difficulty=q.difficulty or session.difficulty)
    kwargs["interviewer"] = session.interviewer or interviewers.DEFAULT
    observed = (q.answer.details or {}).get("observed")  # kept across (re-)evaluations
    try:
        ev = ai.evaluate_answer(db, user.id, **kwargs) if full else ai.score_answer(db, user.id, **kwargs)
    except ai.AIUnavailable as exc:
        q.answer.evaluation_status = "unavailable"
        return exc.message
    q.answer.scores = {k: ev[k] for k in ("relevance", "correctness", "clarity", "communication")}
    q.answer.score = ev["score"]
    q.answer.details = {**(ev.get("details") or {}), **({"observed": observed} if observed else {})}
    if ev.get("feedback"):
        q.answer.feedback = ev["feedback"] + (f"\n\nTip: {ev['better_answer_hint']}" if ev.get("better_answer_hint") else "")
        q.answer.sample_answer = ev.get("sample_answer")
        q.answer.evaluation_status = "completed"
    else:
        q.answer.evaluation_status = "scored"
    return None


def _add_feedback(db: Session, user_id: int, answer: InterviewAnswer, priority: str = "interactive") -> str | None:
    """Detailed tips + sample answer for an already-scored answer. With priority="background" the call may be
    paused for an interactive request; it then raises AIUnavailable(kind="preempted") and nothing is changed."""
    q = answer.question
    scored = {**(answer.scores or {}), "completeness": (answer.details or {}).get("completeness", 0),
              "score": answer.score or 0}
    try:
        kw = {"priority": priority} if priority != "interactive" else {}
        fb = ai.answer_feedback(db, user_id, job_role=q.session.job_role, question=q.text,
                                question_type=q.question_type, answer=answer.text, scored=scored,
                                interviewer=q.session.interviewer or interviewers.DEFAULT, **kw)
    except ai.AIUnavailable as exc:
        if exc.kind == "preempted":
            raise
        answer.details = {**(answer.details or {}), "feedback_status": "unavailable", "feedback_error": exc.message}
        return exc.message
    answer.details = {**(answer.details or {}), "strengths": fb["strengths"], "missing_concepts": fb["missing_concepts"],
                      "improvements": fb["improvements"], "feedback_status": "completed"}
    answer.feedback = fb["feedback"] + (f"\n\nTip: {fb['better_answer_hint']}" if fb.get("better_answer_hint") else "")
    answer.sample_answer = fb["sample_answer"]
    answer.evaluation_status = "completed"
    return None


FEEDBACK_RETRY_SECONDS = (3, 6, 12, 20, 30, 45, 60, 90)


def feedback_job(answer_id: int, user_id: int) -> None:
    """Background task (runs after the response is sent): fills in detailed feedback for one answer.

    It runs at background priority: whenever the candidate is waiting for the interviewer (scoring, next question)
    the feedback generation is paused and retried afterwards, so the ~900-token tips never delay the conversation.
    """
    for wait in (0, *FEEDBACK_RETRY_SECONDS):
        if wait:
            time.sleep(wait)  # background thread only; nobody is waiting on this
        db = database.SessionLocal()
        try:
            answer = db.get(InterviewAnswer, answer_id)
            if not answer or answer.evaluation_status != "scored":
                return
            _add_feedback(db, user_id, answer, priority="background")
            session = answer.question.session
            if session.status == "completed" and session.report:  # finished before the tips were ready
                session.report = {**session.report, **report_metrics(session)}
            db.commit()
            return
        except ai.AIUnavailable as exc:
            db.rollback()
            if exc.kind != "preempted":
                return
        except Exception:  # never crash the worker; the student can use "Retry evaluation"
            logger.exception("background feedback failed for answer %s", answer_id)
            db.rollback()
            return
        finally:
            db.close()
    logger.warning("background feedback for answer %s kept being paused; use Retry evaluation", answer_id)


def _feedback_in_background(answer_id: int, user_id: int) -> None:
    background.spawn(feedback_job, answer_id, user_id, name=f"feedback-{answer_id}")


def _check_suspicious(session: InterviewSession, q: InterviewQuestion, body: AnswerIn) -> None:
    """Flag the session for admin review (never auto-penalise) when an answer looks pasted: a long answer
    submitted within 5 seconds, or an answer identical to another one in the same interview.
    """
    words = len(body.answer.split())
    reasons = []
    if body.response_seconds is not None and body.response_seconds < 5 and words > 60:
        reasons.append(f"Q{q.position}: {words}-word answer submitted in {body.response_seconds}s")
    normalized = " ".join(body.answer.lower().split())
    for other in session.questions:
        if other.id != q.id and other.answer and " ".join(other.answer.text.lower().split()) == normalized and words > 3:
            reasons.append(f"Q{q.position}: identical to the answer for Q{other.position}")
    if reasons:
        session.flagged = True
        session.flag_reason = "; ".join(filter(None, [session.flag_reason] + reasons))


@router.post("/{session_id}/answer")
def submit_answer(session_id: int, body: AnswerIn, background: BackgroundTasks, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    """Text-mode answer (POST .../answer).

    Saves the answer, scores it with the fast AI step (the score decides the next question's difficulty), adds the
    next question unless the planned number is reached, and schedules the detailed feedback as a background task.
    Returns the updated session, any evaluation error, and whether the interview is ready to complete.
    """
    t0 = time.perf_counter()
    session = _get_session(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    current = _check_current(session, body.question_id)
    _save_answer(session, current, body)
    db.flush()
    # Fast path: score now (decides the next question's difficulty), detailed feedback after the response.
    eval_error = _evaluate(db, user, session, current, _rubric(db, "interview"), full=False)
    db.commit()
    finished = len(session.questions) >= session.planned_questions
    if not finished:
        _add_next_question(db, user, session)
        db.commit()
    if current.answer.evaluation_status == "scored":
        background.add_task(feedback_job, current.answer.id, user.id)
    perf.record("answer.submit", (time.perf_counter() - t0) * 1000, True)
    return {"session": interview_out(session, detail=True, own=True), "evaluation_error": eval_error,
            "ready_to_complete": finished}


def _check_current(session: InterviewSession, question_id: int, duplicate_status: int = 400) -> InterviewQuestion:
    """duplicate_status: the live interview answers a repeated submission with 409 so the browser can tell it apart
    from a real error; the classic /answer endpoint keeps its original 400."""
    current = session.questions[-1] if session.questions else None
    if any(q.id == question_id and q.answer for q in session.questions):
        perf.record("turn.duplicate", 0, True)  # the same answer sent twice (double click, network retry)
        raise HTTPException(duplicate_status, "This answer has already been received." if duplicate_status == 409
                            else "You can only answer the current question")
    if not current or current.id != question_id:
        raise HTTPException(400, "You can only answer the current question")
    return current


def _save_answer(session: InterviewSession, current: InterviewQuestion, body: AnswerIn) -> None:
    """Attach the student's answer to the current question, with observable facts (word count, speaking time,
    whether it was cut off at the time limit) used later by the report, then run the paste/copy checks.
    """
    observed = {"words": len(body.answer.split()), "interrupted": body.interrupted}
    if body.speech_seconds:
        observed["speech_seconds"] = round(body.speech_seconds, 1)
    current.answer = InterviewAnswer(text=body.answer.strip(), input_mode=body.input_mode,
                                     response_seconds=body.response_seconds, details={"observed": observed})
    _check_suspicious(session, current, body)


# --------------------------------------------------------------------------- live interview: streamed turns
#
# One POST per conversational turn, answered with Server-Sent Events:
#   stage    {"stage": "scoring" | "question" | "speaking"}
#   scored   {"question_id", "score", "evaluation_status", "next_difficulty"}
#   sentence {"index", "gen", "text"}            one finished sentence, in speaking order
#   audio    {"index", "gen", ...Kokoro output}  its audio + mouth-shape timeline (when tts was requested)
#   tts_error{"message"}                         remaining sentences: the browser voice is used instead
#   retract  {"gen"}                             what was spoken is wrong (repeat / fallback): stop and drop it
#   done     {"session", "ready_to_complete", "evaluation_error", "timings"}
#   error    {"message", "status"}
# Only one turn per interview runs at a time; a second one gets 409 (this is what blocks double submissions).

_turn_locks: dict[int, float] = {}
_turn_locks_guard = threading.Lock()
TURN_LOCK_STALE_S = 300


def _lock_turn(session_id: int) -> bool:
    """Mark a live-interview turn as running. False if one is already running for this interview (so double
    submissions get 409); a lock older than TURN_LOCK_STALE_S is treated as abandoned.
    """
    with _turn_locks_guard:
        held = _turn_locks.get(session_id)
        if held and time.monotonic() - held < TURN_LOCK_STALE_S:
            return False
        _turn_locks[session_id] = time.monotonic()
        return True


def _unlock_turn(session_id: int) -> None:
    """Release the turn lock taken by `_lock_turn()`."""
    with _turn_locks_guard:
        _turn_locks.pop(session_id, None)


_prefetch: dict[int, threading.Event] = {}


def _start_prefetch(session_id: int, user_id: int) -> None:
    """Write the first question of a live interview in a background thread, so it is usually ready when the
    student presses Start. The turn endpoint waits on the returned event (or creates the question itself on failure).
    """
    done = threading.Event()
    _prefetch[session_id] = done

    def run():
        db = database.SessionLocal()
        try:
            s = db.get(InterviewSession, session_id)
            u = db.get(User, user_id)
            if s and u and s.status == "in_progress" and not s.questions:
                with perf.timer("prefetch.first_question"):
                    _add_next_question(db, u, s)
                db.commit()
        except Exception:  # the turn endpoint will try again (and report the error) when Start is pressed
            logger.warning("first-question prefetch failed for interview %s", session_id, exc_info=True)
            db.rollback()
        finally:
            db.close()
            done.set()
            _prefetch.pop(session_id, None)
    background.spawn(run, name=f"prefetch-{session_id}")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


class _Speaker:
    """Collects finished sentences (from the streamed reply) and synthesises them on a separate thread, in order,
    so the next sentence is being written by the model while the previous one is turned into audio."""

    def __init__(self, emit, tts_opts, t0: float):
        self.emit = emit
        self.tts = tts_opts
        self.t0 = t0
        self.index = 0
        self.gen = 0
        self.first_audio_ms: int | None = None
        self.first_text_ms: int | None = None
        self.tts_failed = False
        self.jobs: queue.Queue = queue.Queue()
        self.stream = speech_stream.SpokenStream(self.say)
        self.worker = threading.Thread(target=self._work, daemon=True, name="turn-tts") if tts_opts else None
        if self.worker:
            self.worker.start()

    # -- fed by the model stream
    def on_delta(self, buf: str) -> None:
        self.stream.feed(buf)

    def retract(self) -> None:
        self.gen += 1
        self.stream = speech_stream.SpokenStream(self.say)
        self.emit("retract", {"gen": self.gen})

    def say(self, sentence: str) -> None:
        if self.first_text_ms is None:
            self.first_text_ms = round((time.perf_counter() - self.t0) * 1000)
        if self.index == 0 and self.worker:
            # Speech synthesis time grows with length (a 116-character sentence took ~5 s on the test laptop), so a
            # long FIRST sentence is spoken in two parts split at a natural comma: the first sound comes sooner.
            head, tail = speech_stream.split_first_clause(sentence)
            if tail:
                self._say_piece(head)
                self._say_piece(tail)
                return
        self._say_piece(sentence)

    def _say_piece(self, sentence: str) -> None:
        i = self.index
        self.index += 1
        self.emit("sentence", {"index": i, "gen": self.gen, "text": sentence})
        if self.worker and not self.tts_failed:
            self.jobs.put((i, self.gen, sentence))

    def finish(self, preface: str | None, question: str) -> None:
        """Speak whatever the stream has not spoken yet - or everything again if the stream differs from the
        stored question (e.g. the AI failed and a question-bank question was used)."""
        final = speech_stream.final_sentences(preface, question)
        rest = speech_stream.remaining_after(self.stream.spoken, final)
        if rest is None:
            self.retract()
            rest = final
        for s in rest:
            self.stream.spoken.append(s)
            self.say(s)

    def close(self) -> None:
        if self.worker:
            self.jobs.put(None)
            self.worker.join(timeout=120)

    def _work(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                return
            i, gen, text = job
            if gen != self.gen or self.tts_failed:
                continue  # retracted
            try:
                t = time.perf_counter()
                out = tts.synthesize(text, self.tts.voice, self.tts.speed)
                perf.record("tts.segment", (time.perf_counter() - t) * 1000, True, chars=len(text))
                if gen != self.gen:
                    continue
                if self.first_audio_ms is None:
                    self.first_audio_ms = round((time.perf_counter() - self.t0) * 1000)
                self.emit("audio", {"index": i, "gen": gen, **out})
            except (tts.TTSUnavailable, ValueError) as exc:
                self.tts_failed = True
                perf.record("tts.segment", 0, False)
                self.emit("tts_error", {"message": getattr(exc, "message", str(exc)), "from_index": i})


def _turn_work(session_id: int, user_id: int, body: TurnIn, emit, t0: float) -> None:
    """Body of one live-interview turn, run in a worker thread; results are sent to the browser via `emit`.

    Order: save + fast-score the answer (if any) -> write the next question, speaking it sentence by sentence as it
    is generated -> schedule detailed feedback in the background -> `done` event with the session and timings.
    Errors become an `error` event; the answer is kept so the student can try again.
    """
    db = database.SessionLocal()
    speaker = _Speaker(emit, body.tts, t0)
    timings: dict = {}
    try:
        user = db.get(User, user_id)
        session = db.get(InterviewSession, session_id)
        eval_error = None
        answered = None
        if body.answer:
            current = _check_current(session, body.answer.question_id, 409)
            _save_answer(session, current, body.answer)
            db.flush()
            emit("stage", {"stage": "scoring"})
            t = time.perf_counter()
            eval_error = _evaluate(db, user, session, current, _rubric(db, "interview"), full=False)
            db.commit()
            timings["scoring_ms"] = round((time.perf_counter() - t) * 1000)
            answered = current.answer
            emit("scored", {"question_id": current.id, "score": answered.score,
                            "evaluation_status": answered.evaluation_status,
                            "next_difficulty": (answered.details or {}).get("next_difficulty")})
        last = session.questions[-1] if session.questions else None
        finished = bool(last and last.answer) and len(session.questions) >= session.planned_questions
        if not finished:
            pending = _prefetch.get(session_id)
            if pending is not None and not (last and not last.answer):
                emit("stage", {"stage": "question"})
                pending.wait(timeout=get_settings().ai_timeout_seconds)
                db.expire_all()
                session = db.get(InterviewSession, session_id)
                last = session.questions[-1] if session.questions else None
            if last is not None and not last.answer:
                question = last  # already prepared (prefetched first question, or a reconnect)
                timings["prepared"] = True
            else:
                emit("stage", {"stage": "question"})
                t = time.perf_counter()
                _add_next_question(db, user, session, stream=speaker)
                db.commit()
                timings["question_ms"] = round((time.perf_counter() - t) * 1000)
                question = session.questions[-1]
            speaker.finish(question.preface, question.text)
        speaker.close()
        timings["first_text_ms"] = speaker.first_text_ms
        timings["first_audio_ms"] = speaker.first_audio_ms
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000)
        perf.record("turn.total", timings["total_ms"], True, mode=session.response_mode or "fast",
                    kind="answer" if body.answer else "first")
        if speaker.first_audio_ms is not None:
            perf.record("turn.to_first_audio", speaker.first_audio_ms, True, kind="answer" if body.answer else "first")
        if speaker.first_text_ms is not None and body.answer:
            perf.record("llm.interview_question.first_text", speaker.first_text_ms - timings.get("scoring_ms", 0),
                        True)
        if answered is not None and answered.evaluation_status == "scored":
            _feedback_in_background(answered.id, user_id)
        emit("done", {"session": interview_out(session, detail=True, own=True), "ready_to_complete": finished,
                      "evaluation_error": eval_error, "timings": timings})
    except HTTPException as exc:
        db.rollback()
        emit("error", {"message": exc.detail, "status": exc.status_code})
    except Exception:
        logger.exception("interview turn failed for interview %s", session_id)
        db.rollback()
        perf.record("turn.total", (time.perf_counter() - t0) * 1000, False)
        emit("error", {"message": "The interviewer could not continue because of a server problem. Your answer is "
                                  "kept - try again.", "status": 500})
    finally:
        speaker.close()
        db.close()


@router.post("/{session_id}/turn")
def interview_turn(session_id: int, body: TurnIn, user: User = Depends(require_student),
                   db: Session = Depends(get_db)):
    """Live interview turn, streamed (see the event list above). The answer (if any) is scored first because the
    score decides the next question's difficulty; then the next question is streamed and spoken sentence by
    sentence. Detailed feedback is written afterwards in the background and never delays the next question."""
    session = _get_session(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    if body.answer:
        _check_current(session, body.answer.question_id, 409)  # fail fast with a normal HTTP error
    if not _lock_turn(session_id):
        perf.record("turn.duplicate", 0, True)
        raise HTTPException(409, "This turn is already being processed.")
    t0 = time.perf_counter()
    events: queue.Queue = queue.Queue()

    def emit(event: str, data: dict) -> None:
        events.put(_sse(event, data))

    def work():
        try:
            # The candidate is waiting for this whole turn (scoring, question, every spoken sentence): background
            # feedback generation must not compete for the CPU meanwhile.
            with local_llm.interactive_hold():
                _turn_work(session_id, user.id, body, emit, t0)
        finally:
            _unlock_turn(session_id)
            events.put(None)
    background.spawn(work, name=f"turn-{session_id}")

    def stream():
        while True:
            try:
                item = events.get(timeout=10)
            except queue.Empty:
                yield ": keep-alive\n\n"  # keeps proxies from closing a slow turn
                continue
            if item is None:
                return
            yield item
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/{session_id}/next-question")
def ensure_next_question(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Recovery: if the previous request saved the answer but failed before creating the next question,
    create it now. Does nothing when a question is already waiting or the interview is complete."""
    session = _get_session(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    last = session.questions[-1] if session.questions else None
    if (last is None or last.answer) and len(session.questions) < session.planned_questions:
        _add_next_question(db, user, session)
        db.commit()
    return {"session": interview_out(session, detail=True, own=True),
            "ready_to_complete": len(session.questions) >= session.planned_questions and bool(session.questions[-1].answer)}


def _finalize_scores_and_report(db: Session, user: User, session: InterviewSession) -> str | None:
    """Compute the overall score (average of the scored answers) and ask the AI for the final
    report; the deterministic metrics from report_metrics.py are always stored. Returns an error message when the
    report could not be written (report_status "unavailable"), else None.
    """
    answered = [q for q in session.questions if q.answer]
    scored = [q.answer.score for q in answered if q.answer.score is not None]
    session.overall_score = round(sum(scored) / len(scored), 1) if scored else None
    if not scored:
        session.report_status = "unavailable"
        return "Answers have not been evaluated by AI yet."
    qa = [{"question": q.text, "type": q.question_type, "answer": q.answer.text, "score": q.answer.score}
          for q in answered]
    metrics = report_metrics(session)  # deterministic: computed from stored scores and observed behaviour
    try:
        report = ai.interview_report(db, user.id, job_role=session.job_role, category=session.category, qa=qa,
                                     interviewer=session.interviewer or interviewers.DEFAULT)
        session.report = {**report, **metrics}
        session.report_status = "completed" if len(scored) == len(answered) else "partial"
        return None
    except ai.AIUnavailable as exc:
        session.report = metrics  # the numbers don't need the AI
        session.report_status = "unavailable"
        return exc.message


def _post_completion(db: Session, user: User, session: InterviewSession) -> list[str]:
    """Progress records, rewards, badges, goals and mentor alerts. Returns names of new badges."""
    if session.overall_score is None:
        return []
    record_progress(db, user.id, "interview_score", session.overall_score, "interview", session.id,
                    f"{session.job_role} ({session.category})")
    if session.category in ("technical", "hr", "behavioral", "communication"):
        record_progress(db, user.id, f"{session.category}_score", session.overall_score, "interview", session.id)
    if not session.flagged:
        req = rule_requirements(db, "interview_completed")
        answered = [q for q in session.questions if q.answer]
        min_answers = int(req.get("min_answers", 3))
        min_words = int(req.get("min_words_per_answer", 8))
        if len(answered) >= min_answers and all(len(q.answer.text.split()) >= min_words for q in answered):
            award_points(db, user.id, "interview_completed", "interview", session.id,
                         f"Completed mock interview: {session.job_role}")
            prev_best = db.scalar(select(func.max(InterviewSession.overall_score)).where(
                InterviewSession.student_id == user.id, InterviewSession.status == "completed",
                InterviewSession.id != session.id, InterviewSession.flagged.is_(False)))
            improve_by = float(rule_requirements(db, "score_improvement").get("min_improvement", 10))
            if prev_best is not None and session.overall_score >= prev_best + improve_by:
                award_points(db, user.id, "score_improvement", "interview", session.id,
                             f"Improved your best interview score to {session.overall_score}")
    new_badges = after_activity(db, user.id, "mock_interview")
    threshold = float(get_setting(db, "struggling_score_threshold") or 50)
    previous = [s for s in db.scalars(select(InterviewSession.overall_score).where(
        InterviewSession.student_id == user.id, InterviewSession.status == "completed",
        InterviewSession.id != session.id, InterviewSession.overall_score.is_not(None),
        InterviewSession.flagged.is_(False)).order_by(InterviewSession.completed_at.desc()).limit(3))]
    prev_avg = sum(previous) / len(previous) if previous else None
    alert = None
    if session.overall_score < threshold:
        alert = ("Student needs support",
                 f"{user.full_name} scored {session.overall_score} in a {session.category} mock interview.", "alert")
    elif prev_avg is not None and session.overall_score <= prev_avg - 10:
        alert = ("Performance dropped", f"{user.full_name}'s interview score fell to {session.overall_score} "
                 f"(recent average {round(prev_avg, 1)}).", "alert")
    elif prev_avg is not None and session.overall_score >= prev_avg + 10:
        alert = ("Student improving 🎉", f"{user.full_name} scored {session.overall_score}, up from a recent "
                 f"average of {round(prev_avg, 1)}. A word of encouragement could help!", "celebrate")
    if alert:
        for a in db.scalars(select(MentorAssignment).where(MentorAssignment.student_id == user.id,
                                                           MentorAssignment.active.is_(True))):
            notify(db, a.mentor_id, alert[0], alert[1], alert[2], f"/mentor/students/{user.id}")
    return new_badges


@router.post("/{session_id}/complete")
def complete_interview(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Finish an interview (POST .../complete): drop the unanswered trailing question, compute the overall
    score and report, then record progress, award points/badges and alert mentors when needed.
    """
    session = _get_session(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    answered = [q for q in session.questions if q.answer]
    if not answered:
        raise HTTPException(400, "Answer at least one question before finishing")
    # Drop the trailing unanswered question so the transcript is accurate.
    for q in list(session.questions):
        if not q.answer:
            session.questions.remove(q)
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.flush()
    report_error = _finalize_scores_and_report(db, user, session)
    new_badges = _post_completion(db, user, session)
    db.commit()
    return {"session": interview_out(session, detail=True, own=True), "report_error": report_error, "new_badges": new_badges}


@router.post("/{session_id}/retry-evaluation")
def retry_evaluation(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Re-run whatever AI work is missing: feedback for answers that only have scores, full evaluation for
    unscored answers, then the final report. 503 with the reason if the AI is still unavailable.
    """
    session = _get_session(db, user, session_id)
    rubric = _rubric(db, "interview")
    had_score = session.overall_score is not None
    error = None
    for q in session.questions:
        if q.answer and q.answer.evaluation_status == "scored":  # score known, only the tips are missing
            error = _add_feedback(db, user.id, q.answer) or error
            db.commit()
            if error:
                raise HTTPException(503, error)
        elif q.answer and q.answer.evaluation_status != "completed":
            error = _evaluate(db, user, session, q, rubric) or error
            db.commit()
            if error:
                raise HTTPException(503, error)
    new_badges = []
    if session.status == "completed" and session.report_status != "completed":
        error = _finalize_scores_and_report(db, user, session)
        if not had_score:
            new_badges = _post_completion(db, user, session)
        db.commit()
        if error:
            raise HTTPException(503, error)
    return {"session": interview_out(session, detail=True, own=True), "new_badges": new_badges}


@router.delete("/{session_id}")
def abandon_interview(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Mark an in-progress interview as abandoned (it stays in the history but is never scored)."""
    session = _get_session(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "Only in-progress interviews can be abandoned")
    session.status = "abandoned"
    db.commit()
    return {"ok": True}
