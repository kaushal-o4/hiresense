"""HireSense FastAPI application entry point.

Creates the FastAPI app, registers all routers, adds security headers and the global error handler, and warms up the local AI models at startup.
"""

import logging
import re
import time
import traceback
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import SessionLocal
from .models import ErrorLog
from .routers import (
    admin, assessments, auth, common, english, interviews, jobs, mentors, monitoring, students, voice,
)

logger = logging.getLogger("hiresense")
settings = get_settings()

app = FastAPI(
    title="HireSense API",
    description="AI-Powered Intelligent Interview and Placement Assessment System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # A request ID ties together the client's report, this log line and the perf metrics of one call. A caller-sent
    # ID is kept only if it looks harmless (it ends up in logs).
    rid = request.headers.get("x-request-id", "")
    request.state.request_id = rid if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", rid) else uuid.uuid4().hex[:16]
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    if elapsed > 5 and not request.url.path.endswith(("/turn", "/transcribe", "/speak")):
        logger.info("slow request id=%s %s %s %.1fs status=%s", request.state.request_id, request.method,
                    request.url.path, elapsed, response.status_code)  # path only: no query string, no body
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    try:
        db = SessionLocal()
        db.add(ErrorLog(path=request.url.path[:300], method=request.method,
                        error="".join(traceback.format_exception(exc))[-4000:],
                        user_id=getattr(request.state, "user_id", None)))
        db.commit()
        db.close()
    except Exception:  # never let error logging mask the original error
        pass
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. It has been logged."})


for r in (auth.router, common.router, students.router, students.shared, interviews.public_router,
          interviews.router, english.router,
          assessments.student_router, assessments.manage_router, jobs.student_router, jobs.recruiter_router,
          mentors.router, admin.router, voice.router, monitoring.router):
    app.include_router(r)


PLACEHOLDER_SECRETS = ("change-me", "replace-with")


def check_secret_key() -> None:
    """Anyone who knows the SECRET_KEY can forge login cookies, and the placeholder values are public (README,
    .env.example). Warn always; refuse to start when COOKIE_SECURE=true, which means the app is served over HTTPS."""
    key = settings.secret_key
    weak = len(key) < 32 or any(key.startswith(p) for p in PLACEHOLDER_SECRETS)
    if not weak:
        return
    if settings.cookie_secure:
        raise RuntimeError("SECRET_KEY is a placeholder or shorter than 32 characters while COOKIE_SECURE=true. "
                           "Set a long random SECRET_KEY in backend/.env before running in production.")
    logger.warning("SECURITY: SECRET_KEY is a placeholder. Fine for development; set a long random value "
                   "before deploying (the app refuses to start with COOKIE_SECURE=true until you do).")


@app.on_event("startup")
def warm_up_models():
    check_secret_key()
    from .database import init_db
    init_db()  # MongoDB indexes and unique constraints
    # Load the models in the background so the first request doesn't wait for them (the language model alone took
    # ~64 s on its first call in tests_perf). Never blocks startup.
    import threading

    from .services import embeddings, local_llm, stt, tts

    def warm():  # one after another, to avoid large loads competing for memory at once
        for fn in (local_llm.warmup, embeddings.warmup, tts.warmup, stt.warmup, tts.prewarm_static):
            try:
                fn()
            except Exception:  # noqa: BLE001 - warm-up is best effort
                logger.warning("warm-up step %s failed", getattr(fn, "__name__", fn), exc_info=True)
    threading.Thread(target=warm, daemon=True, name="model-warmup").start()
    try:  # delete integrity events past their retention period
        from . import database
        db = database.SessionLocal()
        try:
            monitoring.purge_expired(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - e.g. tables not migrated yet
        logger.warning("could not purge expired integrity events", exc_info=True)
    warn_published_admin_password()


def warn_published_admin_password():
    """Loud warning while any admin account still accepts the password older versions published in the README."""
    from .odm import select

    from . import database
    from .models import User
    from .security import verify_password
    from .seed import PUBLISHED_ADMIN_PASSWORD
    try:
        db = database.SessionLocal()
        try:
            weak = [u.email for u in db.scalars(select(User).where(User.role == "admin"))
                    if verify_password(PUBLISHED_ADMIN_PASSWORD, u.password_hash)]
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - e.g. tables not migrated yet
        return
    for email in weak:
        logger.warning("SECURITY: admin account %s still uses the published default password. Change it now "
                       "(Account settings -> Change password).", email)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/health/live", tags=["health"])
def liveness():
    """The process is up. Never touches the database or the model, so an orchestrator can use it to decide
    whether to restart the process."""
    return {"status": "alive"}


@app.get("/api/health/ready", tags=["health"])
def readiness():
    """Whether the app can serve requests. The database is required (503 if it fails). The AI parts are reported per
    component but never make the app 'not ready': the app is designed to keep working, with clearly labelled
    reduced features, while Ollama or a voice model is unavailable. No user data or file paths are returned."""
    from .database import get_database
    from .services import embeddings, local_llm, model_router, stt, tts

    try:
        get_database().command("ping")
        database_ok = True
    except Exception:  # noqa: BLE001
        logger.warning("readiness: database check failed", exc_info=True)
        database_ok = False
    llm = local_llm.runtime_status() if settings.ai_enabled else {"running": False, "model_ready": False,
                                                                  "error": "AI is disabled in the configuration."}
    emb = embeddings.status()
    components = {
        "database": {"ok": database_ok},
        "language_model": {"ok": bool(llm["running"] and llm["model_ready"]), "model": llm.get("model"),
                           "detail": llm.get("error")},
        "embeddings": {"ok": bool(emb.get("enabled") and emb.get("installed") and not emb.get("error"))},
        "routing": model_router.describe() if settings.ai_enabled else None,
    }
    for name, mod in (("speech_synthesis", tts), ("speech_recognition", stt)):
        try:
            st = mod.status()
            components[name] = {"ok": bool(st.get("enabled") and not st.get("error"))}
        except Exception:  # noqa: BLE001
            components[name] = {"ok": False}
    ready = database_ok
    degraded = [k for k, v in components.items() if v and not v.get("ok") and k != "routing"]
    return JSONResponse(status_code=200 if ready else 503,
                        content={"status": "ready" if ready and not degraded else
                                 ("degraded" if ready else "not_ready"),
                                 "degraded": degraded, "components": components})
