# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/main.py
#
# FILE PURPOSE:
# The entry point of the backend. It creates the FastAPI application, plugs in every API route file,
# adds security headers and a global error handler, and prepares the AI models when the server starts.
#
# MAIN RESPONSIBILITY:
# Start and configure the whole HireSense API server.
#
# WHAT THIS FILE DOES:
# 1. Creates the FastAPI `app` object with CORS settings so the React frontend can call it.
# 2. Adds a middleware that gives every request an ID, logs slow requests and adds security
#    headers.
# 3. Registers all routers (auth, student, interviews, live interview, English, assessments, jobs,
#    mentor, admin, voice, monitoring).
# 4. On startup: checks the SECRET_KEY, creates MongoDB indexes, warms up the AI models in a
#    background thread and purges expired integrity events.
# 5. On shutdown: waits for background jobs (feedback, reports) to finish saving.
# 6. Exposes health endpoints used by Docker/Render and the frontend.
#
# HOW THIS FILE WORKS:
# uvicorn imports this module and serves `app`. Each router file adds its own URLs to `app`. Unhandled
# exceptions are caught by `unhandled_error`, saved to the error_logs collection and returned as a
# polite 500 message. Model warm-up runs in a separate thread so the server is ready immediately.
#
# IMPORTANT FUNCTIONS:
#    - security_headers()
#        Middleware: request ID, slow-request log, X-Frame-Options / nosniff headers.
#    - unhandled_error()
#        Saves any unexpected error to ErrorLog and returns a generic 500 response.
#    - warm_up_models()
#        Startup hook: secret-key check, indexes, background model warm-up, retention purge.
#    - drain_background_jobs()
#        Shutdown hook: lets running background jobs finish their database writes.
#    - readiness()
#        GET /api/health/ready - reports database and AI component status (503 if DB is down).
#    - check_secret_key()
#        Anyone who knows the SECRET_KEY can forge login cookies, and the placeholder values
#        are public (README, .env.example).
#    - warn_published_admin_password()
#        Loud warning while any admin account still accepts the password older versions
#        published in the README.
#    - liveness()
#        The process is up.
#    Other helper functions: health
#
# API ENDPOINTS DEFINED HERE:
#    - GET /api/health
#        health() - public
#    - GET /api/health/live
#        liveness() - public - The process is up.
#    - GET /api/health/ready
#        readiness() - public - Whether the app can serve requests.
#
# IMPORTANT VARIABLES / SETTINGS:
#    PLACEHOLDER_SECRETS
#
# INPUT:
# HTTP requests from the browser (through the Vite proxy in development) and settings from
# backend/.env.
#
# OUTPUT:
# HTTP responses produced by the routers; health/readiness JSON.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py, app/database_connection.py, app/database_models.py,
#    app/mongodb_data_layer/__init__.py, app/password_and_token_security.py,
#    app/routers/admin/__init__.py, app/routers/authentication_routes.py,
#    app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
#    app/routers/interview_routes.py, app/routers/jobs/__init__.py,
#    app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
#    app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
#    app/routers/student_portal_routes.py, app/routers/voice_speech_routes.py,
#    app/seed_initial_data.py, app/services/ai_models/ai_task_model_router.py,
#    app/services/ai_models/language_model_client.py,
#    app/services/ai_models/sentence_embedding_model.py,
#    app/services/platform_support/background_jobs.py, app/services/voice/speech_to_text.py,
#    app/services/voice/text_to_speech.py
#    Tested by: eval/run_eval.py, tests/conftest.py, tests/test_health_and_routing.py
#
# EXECUTION FLOW:
#    uvicorn starts app.main:app
#       |
#       v
#    Startup hook: indexes + model warm-up thread
#       |
#       v
#    Request arrives -> middleware adds request ID and headers
#       |
#       v
#    Matching router function runs
#       |
#       v
#    Response (or logged error) returned to the frontend
#
# IMPORTANT DEPENDENCIES:
#    fastapi
#
# IMPORTANT NOTE:
# This file does not contain business logic; it only wires the application together. Run with: uvicorn
# app.main:app --reload (see start-backend.bat).
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

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

from .application_configuration import get_settings
from .database_connection import SessionLocal
from .database_models import ErrorLog
from .password_and_token_security import COOKIE_NAME
from .routers import (
    admin,
    skill_assessment_routes as assessments,
    authentication_routes as auth,
    profile_and_notification_routes as common,
    english_practice_routes as english,
    live_voice_interview_routes as interview_live,
    interview_routes as interviews,
    jobs,
    mentor_portal_routes as mentors,
    interview_monitoring_routes as monitoring,
    student_portal_routes as students,
    voice_speech_routes as voice,
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
    if elapsed > 5 and not request.url.path.endswith(("/turn", "/transcribe", "/speak", "/stream")):
        logger.info("slow request id=%s %s %s %.1fs status=%s", request.state.request_id, request.method,
                    request.url.path, elapsed, response.status_code)  # path only: no query string, no body
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _request_origin(request: Request) -> str | None:
    """The browser-reported origin of a request: the Origin header, else scheme://host of the Referer."""
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if referer:
        m = re.match(r"^(https?://[^/?#]+)", referer)
        return m.group(1) if m else "null"
    return None


@app.middleware("http")
async def block_cross_site_writes(request: Request, call_next):
    """CSRF defence for the cookie session. Browsers attach the hs_session cookie automatically, so a page on
    another site could make a signed-in user's browser send a body-less POST (logout, mark-all-read, finish
    interview) or a multipart upload; CORS does not stop those "simple" requests from being *sent*. A write that
    carries the session cookie is therefore accepted only from an origin listed in CORS_ORIGINS (or FRONTEND_URL),
    or from the API's own origin. Requests without the cookie (Bearer-token API clients, tests) and requests with no
    Origin/Referer at all (non-browser clients) are unaffected: browsers always send Origin on cross-site writes."""
    if request.method in UNSAFE_METHODS and COOKIE_NAME in request.cookies:
        origin = _request_origin(request)
        if origin is not None:
            own = f"{request.url.scheme}://{request.headers.get('host', '')}"
            allowed = {o.rstrip("/") for o in settings.cors_origin_list} | {settings.frontend_url.rstrip("/"), own}
            if origin not in allowed:
                logger.warning("Blocked cross-site %s %s from origin %s", request.method, request.url.path, origin[:100])
                return JSONResponse(status_code=403, content={"detail": "Cross-site request blocked."})
    return await call_next(request)


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
          interviews.router, interview_live.router, english.router,
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
    from .services.platform_support import background_jobs as background
    background.started()
    from .database_connection import init_db
    init_db()  # MongoDB indexes and unique constraints
    # Load the models in the background so the first request doesn't wait for them (the language model alone took
    # ~64 s on its first call in tests_perf). Never blocks startup.
    import threading

    from .services.ai_models import sentence_embedding_model as embeddings, language_model_client as local_llm
    from .services.voice import speech_to_text as stt, text_to_speech as tts

    def warm():  # one after another, to avoid large loads competing for memory at once
        for fn in (local_llm.warmup, embeddings.warmup, tts.warmup, stt.warmup, tts.prewarm_static):
            try:
                fn()
            except Exception:  # noqa: BLE001 - warm-up is best effort
                logger.warning("warm-up step %s failed", getattr(fn, "__name__", fn), exc_info=True)
    threading.Thread(target=warm, daemon=True, name="model-warmup").start()
    try:  # delete integrity events past their retention period
        from . import database_connection as database
        db = database.SessionLocal()
        try:
            monitoring.purge_expired(db)
        finally:
            db.close()
    except Exception:  # noqa: BLE001 - e.g. tables not migrated yet
        logger.warning("could not purge expired integrity events", exc_info=True)
    warn_published_admin_password()


@app.on_event("shutdown")
def drain_background_jobs():
    """SIGTERM / Ctrl+C: uvicorn stops accepting requests and lets open ones finish, then this waits (up to
    SHUTDOWN_GRACE_SECONDS) for background jobs such as answer feedback and reports to save their results."""
    from .services.platform_support import background_jobs as background
    left = background.drain(settings.shutdown_grace_seconds)
    logger.info("shutdown complete (%d background job(s) cut off)", left)


def warn_published_admin_password():
    """Loud warning while any admin account still accepts the password older versions published in the README."""
    from .mongodb_data_layer import select

    from . import database_connection as database
    from .database_models import User
    from .password_and_token_security import verify_password
    from .seed_initial_data import PUBLISHED_ADMIN_PASSWORD
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
    from .database_connection import get_database
    from .services.ai_models import (
        sentence_embedding_model as embeddings,
        language_model_client as local_llm,
        ai_task_model_router as model_router,
    )
    from .services.voice import speech_to_text as stt, text_to_speech as tts

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
