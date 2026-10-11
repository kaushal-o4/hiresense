import logging
import traceback

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
    response = await call_next(request)
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


@app.on_event("startup")
def warm_up_models():
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
    from sqlalchemy import select

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
