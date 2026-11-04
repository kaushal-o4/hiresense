"""Live (voice-room) interview: one streamed POST per conversational turn.

The answer is saved and fast-scored, then the next question is generated and spoken sentence by sentence while it
is being written. Helpers shared with the typed interview (question choice, scoring, feedback, turn locks, the
first-question prefetch) live in routers/interviews.py.

Events (Server-Sent Events):
    stage    {"stage": "scoring" | "question" | "speaking"}
    scored   {"question_id", "score", "evaluation_status", "next_difficulty"}
    sentence {"index", "gen", "text"}            one finished sentence, in speaking order
    audio    {"index", "gen", ...Kokoro output}  its audio + mouth-shape timeline (when tts was requested)
    tts_error{"message"}                         remaining sentences: the browser voice is used instead
    retract  {"gen"}                             what was spoken is wrong (repeat / fallback): stop and drop it
    done     {"session", "ready_to_complete", "evaluation_error", "timings"}
    error    {"message", "status"}
  Only one turn per interview runs at a time; a second one gets 409 (this is what blocks double submissions).
"""
import json
import logging
import queue
import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from .. import database
from ..config import get_settings
from ..database import get_db
from ..deps import require_student
from ..models import InterviewSession, User
from ..odm import Session
from ..schemas import TurnIn
from ..serializers import interview_out
from ..services import background, local_llm, perf, speech_stream, tts
from .interviews import (
    _add_next_question, _check_current, _evaluate, _feedback_in_background, _get_session, _lock_turn, _prefetch,
    _rubric, _save_answer, _unlock_turn,
)

router = APIRouter(prefix="/api/student/interviews", tags=["interviews"])
logger = logging.getLogger("hiresense.interviews")


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
