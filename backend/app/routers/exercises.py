"""English learning drills: pronunciation practice and speaking exercises (student portal)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from typing import Literal
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_student
from ..models import PracticeExercise, User
from ..serializers import iso
from ..services import ai, fluency, practice_plan, stt
from ..services.common import paginate
from ..services.english_learning import MAX_ACTIVE_SECONDS, pick_prompt, score_pronunciation
from ..services.practice_plan import TIMED_PROMPTS
from ..services.insights import record_progress
from ..services.rewards import after_activity, award_points, rule_requirements

router = APIRouter(prefix="/api/student/exercises", tags=["english learning"])
MAX_AUDIO_BYTES = 12 * 1024 * 1024
TIMED_SECONDS = 60


def _same_recording(heard: str, submitted: str) -> bool:
    import difflib
    a, b = " ".join(heard.lower().split()), " ".join(submitted.lower().split())
    return bool(a) and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


class ExerciseStart(BaseModel):
    kind: Literal["pronunciation", "speaking"]
    level: Literal["easy", "medium", "hard"] = "medium"
    # "timed_answer": a timed spoken answer with delivery measures; plan_item: an item from GET /plan;
    # retry_of: the same prompt again, to compare attempts
    drill: Literal["standard", "timed_answer"] = "standard"
    plan_item: str | None = Field(default=None, max_length=40)
    retry_of: int | None = None


class ExerciseSubmit(BaseModel):
    transcript: str = Field(min_length=1, max_length=5000)
    speech_confidence: float | None = Field(default=None, ge=0, le=1)


def exercise_out(x: PracticeExercise) -> dict:
    return {"id": x.id, "kind": x.kind, "prompt": x.prompt, "level": x.level, "status": x.status,
            "response_text": x.response_text, "active_seconds": x.active_seconds, "score": x.score,
            "details": x.details, "evaluation_status": x.evaluation_status, "created_at": iso(x.created_at),
            "completed_at": iso(x.completed_at)}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("")
def history(kind: str | None = None, page: int = 1, page_size: int = 20, user: User = Depends(require_student),
            db: Session = Depends(get_db)):
    stmt = select(PracticeExercise).where(PracticeExercise.student_id == user.id, PracticeExercise.status == "completed")
    if kind:
        stmt = stmt.where(PracticeExercise.kind == kind)
    items, meta = paginate(db, stmt.order_by(PracticeExercise.id.desc()), page, page_size)
    return {"items": [exercise_out(x) for x in items], **meta}


@router.get("/plan")
def plan(user: User = Depends(require_student), db: Session = Depends(get_db)):
    """Personal practice plan built from the student's own conversations, interviews and drills."""
    return practice_plan.build(db, user.id)


@router.post("", status_code=201)
def start(body: ExerciseStart, user: User = Depends(require_student), db: Session = Depends(get_db)):
    recent = set(db.scalars(select(PracticeExercise.prompt).where(
        PracticeExercise.student_id == user.id, PracticeExercise.kind == body.kind)
        .order_by(PracticeExercise.id.desc()).limit(8)))
    kind, level, drill, target, prompt, meta = body.kind, body.level, body.drill, None, None, {}
    if body.retry_of is not None:
        prev = db.get(PracticeExercise, body.retry_of)
        if not prev or prev.student_id != user.id or prev.status != "completed":
            raise HTTPException(404, "Exercise not found")
        pd = prev.details or {}
        kind, level, prompt = prev.kind, prev.level, prev.prompt
        drill, target = pd.get("drill", "standard"), pd.get("target_seconds")
        meta = {"retry_of": prev.id}
    elif body.plan_item:
        item = practice_plan.item(db, user.id, body.plan_item)
        if not item:
            raise HTTPException(404, "This plan item is no longer available. Refresh your plan.")
        kind, level, drill, target = item["kind"], item["level"], item["drill"], item.get("target_seconds")
        fresh = [p for p in item.get("prompts") or [] if p not in recent] or item.get("prompts") or []
        prompt = fresh[0] if fresh else None
        meta = {"plan_item": item["id"], "plan_title": item["title"]}
    if drill in ("timed_answer", "project_pitch") and target is None:
        target = TIMED_SECONDS
    if prompt is None:
        pool = TIMED_PROMPTS if drill == "timed_answer" and kind == "speaking" else None
        prompt = pick_prompt(kind, level, recent) if pool is None else \
            ([p for p in pool[level] if p not in recent] or pool[level])[0]
    x = PracticeExercise(student_id=user.id, kind=kind, level=level, prompt=prompt,
                         details={"drill": drill, "target_seconds": target, **meta})
    db.add(x)
    db.commit()
    return exercise_out(x)


@router.post("/{exercise_id}/transcribe")
def transcribe(exercise_id: int, audio: UploadFile = File(...), user: User = Depends(require_student),
               db: Session = Depends(get_db)):
    """Local Whisper transcription of one recording. Audio is processed in memory and never stored; only its
    timing (duration, voiced seconds, pauses) is kept with the exercise for the delivery measures."""
    x = db.get(PracticeExercise, exercise_id)
    if not x or x.student_id != user.id:
        raise HTTPException(404, "Exercise not found")
    if x.status == "completed":
        raise HTTPException(400, "This exercise has already been submitted")
    tries = (x.details or {}).get("transcriptions", 0)
    if tries >= 10:
        raise HTTPException(429, "Too many recordings for this exercise. Start the next exercise.")
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "The recording is too long")
    if not data:
        raise HTTPException(400, "The recording is empty")
    try:
        out = stt.transcribe(data)
    except stt.BadAudio as exc:
        raise HTTPException(400, str(exc))
    except stt.STTUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message)
    x.details = {**(x.details or {}), "audio": {k: out.get(k) for k in (
        "duration", "speech_seconds", "longest_pause_s", "long_pauses", "spoken_span_s")}, "audio_transcript": out["text"],
        "transcriptions": tries + 1}
    db.commit()
    return out


@router.post("/{exercise_id}/submit")
def submit(exercise_id: int, body: ExerciseSubmit, user: User = Depends(require_student), db: Session = Depends(get_db)):
    x = db.get(PracticeExercise, exercise_id)
    if not x or x.student_id != user.id:
        raise HTTPException(404, "Exercise not found")
    if x.status == "completed":
        raise HTTPException(400, "This exercise has already been submitted")
    now = datetime.now(timezone.utc)
    words = len(body.transcript.split())
    elapsed = int((now - _aware(x.created_at)).total_seconds())
    # Verified time: real elapsed time, capped per exercise; empty attempts earn nothing.
    x.active_seconds = min(max(elapsed, 0), MAX_ACTIVE_SECONDS[x.kind]) if words >= 3 else 0
    x.response_text = body.transcript.strip()
    x.speech_confidence = body.speech_confidence
    x.status = "completed"
    x.completed_at = now
    error = None
    setup = {k: v for k, v in (x.details or {}).items() if k != "audio_transcript"}
    # Timing is trusted only when the submitted text is (close to) what local Whisper heard for that recording;
    # an answer typed afterwards has no timing.
    heard = (x.details or {}).get("audio_transcript") or ""
    audio = setup.pop("audio", None)
    if audio and not _same_recording(heard, body.transcript):
        audio = None
    if x.kind == "pronunciation":
        x.details = {**setup, **score_pronunciation(x.prompt, body.transcript, body.speech_confidence)}
        x.score = x.details["score"]
        x.evaluation_status = "completed"
    else:
        flu = fluency.analyse(body.transcript, audio, setup.get("target_seconds"))
        prev = db.get(PracticeExercise, setup["retry_of"]) if setup.get("retry_of") else None
        flu["compared_to_previous"] = fluency.compare(flu, ((prev.details or {}).get("delivery") if prev else None))
        x.details = {**setup, "delivery": flu}
        try:
            fb = ai.speaking_feedback(db, user.id, prompt_text=x.prompt, transcript=body.transcript)
            crit = ("grammar", "vocabulary", "fluency", "sentence_formation", "relevance")
            x.score = round(10 * sum(fb[k] for k in crit) / len(crit), 1)
            x.details = {**fb, **x.details}
            x.evaluation_status = "completed"
        except ai.AIUnavailable as exc:
            x.evaluation_status = "unavailable"
            error = exc.message
    db.flush()
    if x.score is not None:
        record_progress(db, user.id, f"{x.kind}_score", x.score, "exercise", x.id, x.prompt[:200])
    min_secs = int(rule_requirements(db, "english_exercise").get("min_active_seconds", 15))
    if x.active_seconds >= min_secs:
        award_points(db, user.id, "english_exercise", "exercise", x.id, f"English {x.kind} exercise")
    new_badges = after_activity(db, user.id, "english_practice")
    db.commit()
    return {"exercise": exercise_out(x), "evaluation_error": error, "new_badges": new_badges}


@router.delete("/{exercise_id}")
def discard(exercise_id: int, user: User = Depends(require_student), db: Session = Depends(get_db)):
    x = db.get(PracticeExercise, exercise_id)
    if not x or x.student_id != user.id:
        raise HTTPException(404, "Exercise not found")
    if x.status == "completed":
        raise HTTPException(400, "Completed exercises are kept in your practice history")
    db.delete(x)
    db.commit()
    return {"ok": True}
