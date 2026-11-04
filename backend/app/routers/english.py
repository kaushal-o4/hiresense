"""AI English communication practice (student portal)."""
import json
import logging
import queue
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from ..odm import select
from ..odm import Session

from .. import database
from ..database import get_db
from ..deps import require_student
from ..models import EnglishMessage, EnglishSession, User, VocabularyItem
from ..schemas import EnglishMessageIn, EnglishStart, VocabularyReviewIn, VocabularyWordIn
from ..serializers import english_out
from ..services import ai, english_companion, english_profile, english_vocab, speech_stream
from ..services.common import paginate
from ..services.insights import record_progress
from ..services.rewards import after_activity, award_points, rule_requirements, streak_lengths

router = APIRouter(prefix="/api/student/english", tags=["english"])
logger = logging.getLogger("hiresense.english")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

MAX_GAP_SECONDS = 120  # longer pauses are not counted as active practice
MIN_WORDS_FOR_ACTIVE = 3


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute_active_seconds(session: EnglishSession) -> int:
    """Verified active time: for each substantive student message, count the time since the previous
    message (capped), so idle tabs and one-word spam don't accumulate practice time."""
    total = 0
    prev = _aware(session.created_at)
    for m in session.messages:
        ts = _aware(m.created_at)
        if m.sender == "student" and len(m.content.split()) >= MIN_WORDS_FOR_ACTIVE:
            total += int(min(max((ts - prev).total_seconds(), 0), MAX_GAP_SECONDS))
        prev = ts
    return total


def confidence_meter(session: EnglishSession) -> int | None:
    """0-100 motivational estimate of how freely the student is speaking: longer answers, fewer corrections, more
    turns and speaking aloud all raise it. It is shown during practice only; scores come from the evaluation."""
    replies = [m for m in session.messages if m.sender == "student"]
    if not replies:
        return None
    n = len(replies)
    avg_words = sum(len(m.content.split()) for m in replies) / n
    avg_fixes = sum(len(m.corrections or []) for m in replies) / n
    voice_share = sum(m.input_mode == "voice" for m in replies) / n
    score = (40 * min(1.0, avg_words / 25) + 30 * max(0.0, 1 - avg_fixes / 3)
             + 20 * min(1.0, n / 6) + 10 * voice_share)
    return int(round(score))


def _ai_message(reply: dict) -> EnglishMessage:
    return EnglishMessage(sender="ai", content=reply["reply"], meta={
        k: reply.get(k) for k in ("avatar_mode", "encouragement", "suggested_followups")})


def session_out(session: EnglishSession) -> dict:
    d = english_out(session, detail=True)
    d["confidence"] = confidence_meter(session)
    m = english_companion.mode(session.learning_mode)
    d["learning_mode"] = m.id
    d["learning_mode_settings"] = {"label": m.label, "tts_speed": m.tts_speed, "listen_silence_ms": m.listen_silence_ms}
    d["memory"] = english_companion.public_memory(session.memory)
    if session.status == "in_progress":
        d["live_active_seconds"] = compute_active_seconds(session)  # same rule as at the end, so it never jumps
    return d


def _get(db: Session, user: User, session_id: int) -> EnglishSession:
    s = db.get(EnglishSession, session_id)
    if not s or s.student_id != user.id:
        raise HTTPException(404, "Practice session not found")
    return s


OPENERS = {
    "free_talk": "Hi! I'd like to practise speaking English about: {topic}",
    "interview": "Hi! I'd like to practise a job interview. Focus: {topic}",
}


@router.post("", status_code=201)
def start(body: EnglishStart, user: User = Depends(require_student), db: Session = Depends(get_db)):
    history = [{"sender": "student", "content": OPENERS[body.style].format(topic=body.topic.strip())}]
    try:
        opening = ai.english_reply(db, user.id, topic=body.topic, history=history, style=body.style,
                                   learning_mode=body.learning_mode, synthetic_opening=True)
    except ai.AIUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message)
    # The opener above is synthetic, so nothing the student "said" can be corrected or praised yet.
    opening = {**opening, "corrections": [], "encouragement": ""}
    session = EnglishSession(student_id=user.id, topic=body.topic.strip(), mode=body.mode, style=body.style,
                             learning_mode=body.learning_mode, memory=opening.get("memory"))
    session.messages.append(_ai_message(opening))
    db.add(session)
    db.commit()
    return session_out(session)


@router.get("/companion")
def companion(user: User = Depends(require_student)):
    """The English companion's public configuration and learning modes (for the start screen)."""
    return english_companion.COMPANION.public()


@router.get("/stats")
def stats(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Motivation widgets: English-practice streak (days with >= 1 verified minute) and totals."""
    done = db.scalars(select(EnglishSession).where(EnglishSession.student_id == user.id,
                                                   EnglishSession.status == "completed")).all()
    days = [_aware(s.ended_at).date() for s in done if s.ended_at and s.active_seconds >= 60]
    current, longest = streak_lengths(days)
    scored = [s.overall_score for s in sorted(done, key=lambda s: s.id) if s.overall_score is not None]
    return {"current_streak": current, "longest_streak": longest,
            "practiced_today": datetime.now(timezone.utc).date() in days,
            "sessions_completed": len(done), "total_minutes": round(sum(s.active_seconds for s in done) / 60),
            "recent_scores": scored[-5:]}


@router.get("/profile")
def learning_profile(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """The student's recurring-mistake patterns (rule-based, from corrections already given)."""
    return english_profile.public_profile(db, user.id)


@router.post("/profile/{pattern_id}/dismiss")
def dismiss_pattern(pattern_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    if not english_profile.dismiss(db, user.id, pattern_id):
        raise HTTPException(404, "Pattern not found")
    db.commit()
    return english_profile.public_profile(db, user.id)


@router.delete("/profile")
def clear_profile(user: User = Depends(require_student), db: Session = Depends(get_db)):
    english_profile.clear(db, user.id)
    db.commit()
    return english_profile.public_profile(db, user.id)


# --------------------------------------------------------------------------- vocabulary review, daily plan, progress
# (declared before /{session_id} so these paths are not read as a session id)

@router.get("/vocabulary")
def vocabulary(filter: str = "all", user: User = Depends(require_student), db: Session = Depends(get_db)):
    """The student's word list (newest first) and box counts. filter: all | due | learning | learned | mastered."""
    items = db.scalars(select(VocabularyItem).where(VocabularyItem.student_id == user.id)
                       .order_by(VocabularyItem.id.desc())).all()
    now = datetime.now(timezone.utc)
    keep = {
        "due": lambda i: _aware(i.due_at) <= now,
        "learning": lambda i: i.box < english_vocab.LEARNED_BOX,
        "learned": lambda i: i.box >= english_vocab.LEARNED_BOX and i.mastered_at is None,
        "mastered": lambda i: i.mastered_at is not None,
    }.get(filter, lambda i: True)
    return {"items": [english_vocab.item_out(i) for i in items if keep(i)],
            "counts": english_vocab.counts(db, user.id), "intervals_days": english_vocab.INTERVAL_DAYS}


@router.post("/vocabulary", status_code=201)
def add_vocabulary(body: VocabularyWordIn, user: User = Depends(require_student), db: Session = Depends(get_db)):
    try:
        item = english_vocab.add_word(db, user.id, body.word, body.meaning, body.example)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    db.commit()
    return english_vocab.item_out(item)


@router.get("/vocabulary/review")
def review_queue(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """The cards due now (oldest first, at most REVIEW_BATCH)."""
    return {"items": [english_vocab.item_out(i) for i in english_vocab.due_items(db, user.id)],
            "counts": english_vocab.counts(db, user.id)}


@router.post("/vocabulary/{item_id}/review")
def review_card(item_id: int, body: VocabularyReviewIn, user: User = Depends(require_student),
                db: Session = Depends(get_db)):
    got = english_vocab.review(db, user.id, item_id, body.knew)
    if got is None:
        raise HTTPException(404, "Card not found")
    item, mastered = got
    if mastered:
        award_points(db, user.id, english_vocab.MASTERED_ACTIVITY, "vocabulary_item", item.id,
                     f"Mastered: {item.back[:60]}")
    plan = english_vocab.check_plan(db, user.id)
    new_badges = after_activity(db, user.id)  # badges and challenges (e.g. the weekly review challenge)
    db.commit()
    return {"item": english_vocab.item_out(item), "mastered_now": mastered, "plan": plan, "new_badges": new_badges}


@router.delete("/vocabulary/{item_id}")
def delete_vocabulary(item_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    item = db.get(VocabularyItem, item_id)
    if not item or item.student_id != user.id:
        raise HTTPException(404, "Card not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/daily-plan")
def daily_plan(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Today's plan, ticked automatically from what the student did today. Finishing it earns points once a day
    (awarded here as well, because the interview item is completed outside the English pages)."""
    plan = english_vocab.daily_plan(db, user.id)
    if plan["all_done"]:
        english_vocab.check_plan(db, user.id, plan)
        after_activity(db, user.id)
        db.commit()
    return plan


@router.get("/progress")
def english_progress(user: User = Depends(require_student), db: Session = Depends(get_db)):
    return english_vocab.progress(db, user.id)


@router.get("")
def list_sessions(page: int = 1, page_size: int = 10, user: User = Depends(require_student),
                  db: Session = Depends(get_db)):
    stmt = select(EnglishSession).where(EnglishSession.student_id == user.id).order_by(EnglishSession.id.desc())
    items, meta = paginate(db, stmt, page, page_size)
    return {"items": [english_out(s) for s in items], **meta}


@router.get("/{session_id}")
def get_session(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    return session_out(_get(db, user, session_id))


@router.post("/{session_id}/message")
def send_message(session_id: int, body: EnglishMessageIn, user: User = Depends(require_student),
                 db: Session = Depends(get_db)):
    return _send_message(db, user, session_id, body)


def _send_message(db: Session, user: User, session_id: int, body: EnglishMessageIn, on_delta=None) -> dict:
    """The whole message round trip, shared by the plain and the streaming endpoint so they behave identically."""
    session = _get(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "This practice session has ended")
    if len(session.messages) >= 80:
        raise HTTPException(400, "This session is full. Please end it and start a new one.")
    history = [{"sender": m.sender, "content": m.content} for m in session.messages]
    history.append({"sender": "student", "content": body.content})
    try:
        reply = ai.english_reply(db, user.id, topic=session.topic, history=history,
                                 style=session.style or "free_talk",
                                 learning_mode=session.learning_mode or english_companion.DEFAULT_MODE,
                                 memory=session.memory, on_delta=on_delta,
                                 focus=english_profile.focus_lines(db, user.id)
                                 if session.learning_mode == "english_learning" else None)
    except ai.AIUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message)
    if reply.get("memory"):
        session.memory = reply["memory"]
    session.messages.append(EnglishMessage(sender="student", content=body.content.strip(), input_mode=body.input_mode,
                                           speech_confidence=body.speech_confidence,
                                           corrections=reply["corrections"]))
    session.messages.append(_ai_message(reply))
    english_profile.record_corrections(db, user.id, session.id, reply["corrections"])
    english_vocab.collect_corrections(db, user.id, session.id, reply["corrections"])
    db.commit()
    return session_out(session)


_streaming: set[int] = set()
_streaming_lock = threading.Lock()


@router.post("/{session_id}/message/stream")
def send_message_stream(session_id: int, body: EnglishMessageIn, user: User = Depends(require_student),
                        db: Session = Depends(get_db)):
    """Same as POST .../message, but the reply text is sent while the model writes it (Server-Sent Events):

      event: delta  {"text": "..."}   the reply so far (cumulative; it can get shorter if the model starts over,
                                      so the client always replaces what it shows)
      event: done   {"session": {...}} the saved session; its last AI message is the authoritative reply (it may
                                      differ from the streamed draft after the repeat/correction checks)
      event: error  {"detail": "...", "status": 503}

    A streamed reply is a draft until `done`: do not speak it or treat it as saved. If the connection drops, the
    server still finishes and saves the turn; reload the session to see it."""
    _get(db, user, session_id)  # fail fast with a normal HTTP error (404 for another student's session)
    with _streaming_lock:
        if session_id in _streaming:
            raise HTTPException(409, "A reply is already being written for this session.")
        _streaming.add(session_id)
    events: queue.Queue = queue.Queue()
    user_id = user.id

    def work():
        last = ""

        def on_delta(buf: str) -> None:
            nonlocal last
            got = speech_stream.partial_json_string(buf, "reply")
            if got and got[0] != last:
                last = got[0]
                events.put(_sse("delta", {"text": last}))

        own = database.SessionLocal()
        try:
            u = own.get(User, user_id)
            events.put(_sse("done", {"session": _send_message(own, u, session_id, body, on_delta=on_delta)}))
        except HTTPException as exc:
            events.put(_sse("error", {"detail": exc.detail, "status": exc.status_code}))
        except Exception:  # noqa: BLE001
            logger.exception("english stream failed")
            events.put(_sse("error", {"detail": "Something went wrong. Please try again.", "status": 500}))
        finally:
            own.close()
            with _streaming_lock:
                _streaming.discard(session_id)
            events.put(None)

    threading.Thread(target=work, daemon=True, name=f"english-stream-{session_id}").start()

    def stream():
        while True:
            try:
                item = events.get(timeout=10)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if item is None:
                return
            yield item
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@router.post("/{session_id}/end")
def end_session(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    session = _get(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "This practice session has already ended")
    student_msgs = [m for m in session.messages if m.sender == "student"]
    session.status = "completed"
    session.ended_at = datetime.now(timezone.utc)
    session.active_seconds = compute_active_seconds(session)
    error = None
    new_badges = []
    if student_msgs:
        try:
            ev = ai.english_evaluate(db, user.id, topic=session.topic, student_messages=[m.content for m in student_msgs])
            scores = {k: ev[k] for k in ("grammar", "vocabulary", "fluency", "sentence_formation")}
            voice = [m.speech_confidence for m in student_msgs if m.speech_confidence is not None]
            if voice:
                # Browser speech-recognition confidence, reported separately as a clarity indicator.
                scores["pronunciation_clarity"] = round(10 * sum(voice) / len(voice), 1)
            session.scores = scores
            session.overall_score = round(10 * sum(ev[k] for k in ("grammar", "vocabulary", "fluency",
                                                                    "sentence_formation")) / 4, 1)
            session.feedback = {"summary": ev["summary"], "strengths": ev["strengths"], "suggestions": ev["suggestions"]}
            session.evaluation_status = "completed"
        except ai.AIUnavailable as exc:
            session.evaluation_status = "unavailable"
            error = exc.message
    else:
        session.evaluation_status = "unavailable"
    db.flush()
    if session.active_seconds > 0:
        record_progress(db, user.id, "english_minutes", round(session.active_seconds / 60, 1), "english", session.id)
    if session.overall_score is not None:
        record_progress(db, user.id, "english_score", session.overall_score, "english", session.id, session.topic)
    min_active = int(rule_requirements(db, "english_session").get("min_active_seconds", 300))
    if session.active_seconds >= min_active:
        award_points(db, user.id, "english_session", "english", session.id,
                     f"{round(session.active_seconds / 60)} minutes of English practice")
    english_vocab.check_plan(db, user.id)
    new_badges = after_activity(db, user.id, "english_practice")
    db.commit()
    return {"session": session_out(session), "evaluation_error": error, "new_badges": new_badges,
            "min_active_seconds_for_points": min_active}


@router.delete("/{session_id}")
def delete_session(session_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    session = _get(db, user, session_id)
    if session.status != "in_progress":
        raise HTTPException(400, "Completed sessions are kept for your progress history")
    db.delete(session)
    db.commit()
    return {"ok": True}
