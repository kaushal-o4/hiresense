# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/database_connection.py
#
# FILE PURPOSE:
# Connects the backend to MongoDB and gives each API request its own database session.
#
# MAIN RESPONSIBILITY:
# Database connection and per-request session handling.
#
# WHAT THIS FILE DOES:
# 1. Opens the MongoDB client using MONGODB_URL / MONGODB_DB.
# 2. Creates sessions (SessionLocal) from the project's MongoDB data layer.
# 3. Creates the indexes and unique constraints at startup (init_db).
# 4. Provides get_db(), a FastAPI dependency that opens a session per request and closes it
#    afterwards.
# 5. Provides clear_database() for tests (refuses to wipe the main database).
#
# HOW THIS FILE WORKS:
# get_db() is a generator: FastAPI calls it before a route function, passes the session in as `db`,
# and closes it when the request ends. Routes then read/write documents through that session.
#
# IMPORTANT FUNCTIONS:
#    - get_db()
#        FastAPI dependency: yields a Session for one request and always closes it.
#    - init_db()
#        Creates indexes declared on the models (run at startup and by the seed script).
#    - SessionLocal()
#        Creates a new Session object (used by background jobs that run outside a request).
#    - get_database()
#        The app's MongoDB database (MONGODB_URL / MONGODB_DB in backend/.env).
#    - clear_database()
#        Delete every document but keep the collections and indexes.
#
# INPUT:
# Connection settings from application_configuration.py.
#
# OUTPUT:
# Session objects used by routers and services to query MongoDB.
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py, app/database_models.py,
#    app/mongodb_data_layer/__init__.py
#    Used by: app/authentication_dependencies.py, app/main.py, app/reset_admin_password.py,
#    app/routers/admin/admin_analytics_routes.py, app/routers/admin/admin_content_routes.py,
#    app/routers/admin/admin_operations_routes.py,
#    app/routers/admin/admin_user_management_routes.py, app/routers/authentication_routes.py,
#    app/routers/english_practice_routes.py, app/routers/interview_monitoring_routes.py,
#    app/routers/interview_routes.py, app/routers/jobs/recruiter_job_routes.py,
#    app/routers/jobs/recruiter_screening_routes.py, app/routers/jobs/student_job_routes.py,
#    app/routers/live_voice_interview_routes.py, app/routers/mentor_portal_routes.py,
#    app/routers/profile_and_notification_routes.py, app/routers/skill_assessment_routes.py,
#    app/routers/student_portal_routes.py, app/routers/voice_speech_routes.py,
#    app/seed_initial_data.py, app/seed_sample_jobs.py,
#    app/services/monitoring/performance_timing.py
#    Tested by: eval/calibrate_scoring.py, eval/run_eval.py, tests/conftest.py,
#    tests/test_integrity_detectors.py, tests/test_latency_and_monitoring.py,
#    tests/test_live_notifications_and_recruiter.py, tests_e2e/account_browser.py,
#    tests_integration/conftest.py, tests_perf/bench_interview_latency.py,
#    tests_perf/bench_models.py, tests_perf/bench_prompts.py
#
# EXECUTION FLOW:
#    Request arrives
#       |
#       v
#    get_db() creates a Session
#       |
#       v
#    Route reads/writes data
#       |
#       v
#    Session closed
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""MongoDB connection and session setup (see the odm package for the data layer).
"""

from . import mongodb_data_layer as odm
from .application_configuration import get_settings
from .mongodb_data_layer import Base, Session  # noqa: F401 - re-exported for the rest of the app


def get_database():
    """The app's MongoDB database (MONGODB_URL / MONGODB_DB in backend/.env)."""
    s = get_settings()
    return odm.connect(s.mongodb_url)[s.mongodb_db]


def SessionLocal() -> Session:  # noqa: N802 - called everywhere as a session factory
    return Session(get_database())


odm.set_fallback_session_factory(lambda: SessionLocal())

_indexes_ready: set[str] = set()


def init_db() -> None:
    """Create indexes once per database per process (called at startup and by the seed)."""
    from . import database_models as models  # noqa: F401 - registers every model

    db = get_database()
    if db.name not in _indexes_ready:
        odm.ensure_indexes(db)
        _indexes_ready.add(db.name)


def clear_database() -> None:
    """Delete every document but keep the collections and indexes. For tests and throwaway benchmark databases;
    refuses to touch the main database."""
    db = get_database()
    if not any(tag in db.name for tag in ("test", "bench", "eval")):
        raise RuntimeError(f"clear_database() refused: {db.name!r} does not look like a test database")
    for name in db.list_collection_names():
        db[name].delete_many({})


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
