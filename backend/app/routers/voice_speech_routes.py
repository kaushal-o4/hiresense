# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/routers/voice_speech_routes.py
#
# FILE PURPOSE:
# Voice support endpoints: text-to-speech for the avatar and speech-to-text for spoken answers.
#
# WHAT THIS FILE DOES:
# 1. GET /api/voice/status - whether TTS/STT engines are available.
# 2. POST /api/voice/speak and /speak/stream - turn text into speech with a mouth-shape timeline.
# 3. POST /api/voice/warmup - load models while the candidate is on the setup screen.
# 4. POST .../interviews/{id}/transcribe and .../english/{id}/transcribe - turn recorded audio into
#    text.
# 5. Rate-limits each user and rejects audio over 12 MB.
#
# HOW THIS FILE WORKS:
# Audio is processed in memory and never stored. The transcribed text is then submitted through the
# normal interview/English endpoints, so scoring is the same as for typed answers.
#
# IMPORTANT FUNCTIONS:
#    - transcribe_answer()
#        Transcribe one recorded answer (or a partial segment / live caption).
#    - speak()
#        Synthesise speech for the interviewer avatar.
#    - speak_stream()
#        Same as /voice/speak, but one NDJSON line per sentence as soon as it is synthesised,
#        so playback of a long text (greeting, closing remarks) starts after the first sentence
#        instead of after the whole text.
#    - warmup()
#        Called from the interview setup screen: loads the language model (and voice models)
#        while the candidate reads the disclosure and tests the camera, so the first question
#        isn't delayed by a 30-70 s model load.
#    - transcribe_english()
#        Spoken English practice: local transcription of one reply (the text is then sent as a
#        normal message).
#    Other helper functions: _rate_limit, voice_status, _transcribe
#
# IMPORTANT CLASSES:
#    - SpeakIn
#
# API ENDPOINTS DEFINED HERE:
#    - GET /api/voice/status
#        voice_status() - any signed-in user
#    - POST /api/voice/speak
#        speak() - any signed-in user
#    - POST /api/voice/speak/stream
#        speak_stream() - any signed-in user - Same as /voice/speak, but one NDJSON line per
#        sentence as soon as it is synthesised, so playback of a long text (greeting, closing
#        remarks) starts after the first sentence instead of after the whole text.
#    - POST /api/voice/warmup
#        warmup() - any signed-in user - Called from the interview setup screen: loads the
#        language model (and voice models) while the candidate reads the disclosure and tests
#        the camera, so the first question isn't delayed by a 30-70 s model load.
#    - POST /api/student/interviews/{session_id}/transcribe
#        transcribe_answer() - student - partial=true: one speech segment while the candidate
#        is still talking (shown live and joined at the end, so only the last segment has to be
#        transcribed after they stop). live=true: a live caption of the unfinished...
#    - POST /api/student/english/{session_id}/transcribe
#        transcribe_english() - student - Spoken English practice: local transcription of one
#        reply (the text is then sent as a normal message).
#
# IMPORTANT VARIABLES / SETTINGS:
#    MAX_AUDIO_BYTES
#
# INPUT:
# Text to speak; WAV audio uploads.
#
# OUTPUT:
# Audio (base64 WAV + visemes) or transcript JSON.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py, app/authentication_dependencies.py,
#    app/database_connection.py, app/database_models.py, app/mongodb_data_layer/__init__.py,
#    app/services/ai_models/language_model_client.py,
#    app/services/monitoring/performance_timing.py, app/services/platform_support/rate_limiter.py,
#    app/services/voice/speech_to_text.py, app/services/voice/text_to_speech.py
#    Used by: app/main.py
#    Tested by: tests/test_voice.py
#
# EXECUTION FLOW:
#    Student records answer
#       |
#       v
#    Audio uploaded to /transcribe
#       |
#       v
#    Whisper converts speech to text
#       |
#       v
#    Text shown and submitted as the answer
#
# IMPORTANT DEPENDENCIES:
#    fastapi, pydantic
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Voice interview support: local text-to-speech for the avatar and local transcription of spoken answers.

Answers are still submitted through the existing interview API (`POST /api/student/interviews/{id}/answer`), so
scoring, adaptive questions, persistence and rewards are unchanged. Audio is processed in memory, never stored.
"""
import json
import threading
import time


from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from ..mongodb_data_layer import Session

from ..database_connection import get_db
from ..authentication_dependencies import get_current_user, require_student
from ..database_models import EnglishSession, InterviewSession, User
from ..services.platform_support import rate_limiter as limiter
from ..services.ai_models import language_model_client as local_llm
from ..services.monitoring import performance_timing as perf
from ..services.voice import speech_to_text as stt, text_to_speech as tts

router = APIRouter(tags=["voice"])
MAX_AUDIO_BYTES = 12 * 1024 * 1024  # ~6 minutes of 16 kHz mono PCM

def _rate_limit(user_id: int, kind: str, limit: int, window_s: int = 600) -> None:
    if not limiter.hit(f"voice:{user_id}:{kind}", limit, window_s):
        raise HTTPException(429, "Too many voice requests. Please wait a few minutes.")


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    voice: str | None = Field(default=None, max_length=40)
    speed: float | None = Field(default=None, ge=0.7, le=1.4)


@router.get("/api/voice/status")
def voice_status(user: User = Depends(get_current_user)):
    from ..application_configuration import get_settings
    s = get_settings()
    return {"tts": tts.status(), "stt": stt.status(),
            # Defaults for the browser's end-of-answer detection; the student can change them in the room settings.
            "recognition": {"end_of_speech_ms": {"fast": s.voice_end_of_speech_ms,
                                                 "coaching": s.voice_end_of_speech_coaching_ms},
                            "min_speech_ms": s.voice_min_speech_ms}}


@router.post("/api/voice/speak")
def speak(body: SpeakIn, user: User = Depends(get_current_user)):
    _rate_limit(user.id, "tts", 150)
    static = tts.is_static(body.text)
    try:
        with local_llm.interactive_hold(), perf.timer("tts.request", chars=len(body.text)) as m:
            out = tts.synthesize(body.text, body.voice, body.speed, cache=True) if static \
                else tts.synthesize(body.text, body.voice, body.speed)
            m["cached"] = bool(out.get("cached"))
            return out
    except tts.TTSUnavailable as exc:
        raise HTTPException(503, exc.message)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("/api/voice/speak/stream")
def speak_stream(body: SpeakIn, user: User = Depends(get_current_user)):
    """Same as /voice/speak, but one NDJSON line per sentence as soon as it is synthesised, so playback of a long
    text (greeting, closing remarks) starts after the first sentence instead of after the whole text."""
    _rate_limit(user.id, "tts", 150)
    if not tts.status()["enabled"]:
        raise HTTPException(503, "Text-to-speech is turned off on this server (TTS_ENABLED=false).")
    segments = tts.split_segments(body.text)
    if not segments:
        raise HTTPException(400, "Nothing to say")

    def gen():
        for i, seg in enumerate(segments):
            try:
                with perf.timer("tts.segment", chars=len(seg)):
                    out = tts.synthesize(seg, body.voice, body.speed, cache=tts.is_static(seg))
                yield json.dumps({"index": i, "last": i == len(segments) - 1, **out}) + "\n"
            except (tts.TTSUnavailable, ValueError) as exc:
                yield json.dumps({"index": i, "error": getattr(exc, "message", str(exc)), "text": seg}) + "\n"
                return
    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


_warm_lock = threading.Lock()


@router.post("/api/voice/warmup")
def warmup(user: User = Depends(get_current_user)):
    """Called from the interview setup screen: loads the language model (and voice models) while the candidate
    reads the disclosure and tests the camera, so the first question isn't delayed by a 30-70 s model load."""
    _rate_limit(user.id, "warmup", 20)

    def run():
        if not _warm_lock.acquire(blocking=False):
            return
        try:
            t = time.perf_counter()
            r = local_llm.warmup()
            if r.get("ok") and not r.get("already_loaded"):
                perf.record("llm.warmup", (time.perf_counter() - t) * 1000, True)
            tts.warmup()
            stt.warmup()
        finally:
            _warm_lock.release()
    threading.Thread(target=run, daemon=True, name="interview-warmup").start()
    return {"started": True, "llm": local_llm.runtime_status(), "tts_loaded": tts.status()["loaded"],
            "stt_loaded": stt.status()["loaded"]}


@router.post("/api/student/interviews/{session_id}/transcribe")
def transcribe_answer(session_id: int, question_id: int = Form(...), audio: UploadFile = File(...),
                      partial: bool = Form(False), live: bool = Form(False),
                      user: User = Depends(require_student), db: Session = Depends(get_db)):
    """partial=true: one speech segment while the candidate is still talking (shown live and joined at the end, so
    only the last segment has to be transcribed after they stop). live=true: a live caption of the unfinished segment,
    sent about every 1.2 s while the candidate talks (one at a time), so it has its own, higher rate limit."""
    session = db.get(InterviewSession, session_id)
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Interview not found")
    if session.status != "in_progress":
        raise HTTPException(400, "This interview is already finished")
    current = session.questions[-1] if session.questions else None
    if not current or current.id != question_id or current.answer:
        raise HTTPException(409, "This recording is not for the current question")
    if live and not stt.status().get("live_captions", True):
        # Hosted speech recognition: no live captions (each would be an API call). An error, not an empty text: the
        # browser may reuse the last live caption as the final answer text.
        raise HTTPException(409, "Live captions are not available on this server")
    if live:
        _rate_limit(user.id, "stt_live", 1500)
    else:
        _rate_limit(user.id, "stt", 240 if partial else 60)
    # The question as context helps Whisper spell technical words (e.g. "FastAPI", "PostgreSQL") the candidate repeats.
    prompt = " ".join((current.text or "").split())[:300] or None
    return {**_transcribe(audio, prompt), "question_id": question_id, "partial": partial, "live": live}


@router.post("/api/student/english/{session_id}/transcribe")
def transcribe_english(session_id: int, audio: UploadFile = File(...), user: User = Depends(require_student),
                       db: Session = Depends(get_db)):
    """Spoken English practice: local transcription of one reply (the text is then sent as a normal message)."""
    session = db.get(EnglishSession, session_id)
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Practice session not found")
    if session.status != "in_progress":
        raise HTTPException(400, "This practice session has ended")
    _rate_limit(user.id, "stt", 60)
    return _transcribe(audio)


def _transcribe(audio: UploadFile, prompt: str | None = None) -> dict:
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "The recording is too long")
    if not data:
        raise HTTPException(400, "The recording is empty")
    try:
        with local_llm.interactive_hold(), perf.timer("stt.transcribe") as m:
            out = stt.transcribe(data, prompt)
            m["audio_s"] = out.get("duration") or 0
            return out
    except stt.BadAudio as exc:
        raise HTTPException(400, str(exc))
    except stt.STTUnavailable as exc:
        raise HTTPException(exc.status_code, exc.message + " You can type your answer instead.")
