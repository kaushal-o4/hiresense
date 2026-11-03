"""MongoDB connection and session setup (see odm.py for the data layer).
"""

from . import odm
from .config import get_settings
from .odm import Base, Session  # noqa: F401 - re-exported for the rest of the app


def get_database():
    """The app's MongoDB database (MONGODB_URL / MONGODB_DB in backend/.env)."""
    s = get_settings()
    return odm.connect(s.mongodb_url)[s.mongodb_db]


def SessionLocal() -> Session:  # noqa: N802 - called everywhere as a session factory
    return Session(get_database())


odm.fallback_session_factory = lambda: SessionLocal()

_indexes_ready: set[str] = set()


def init_db() -> None:
    """Create indexes once per database per process (called at startup and by the seed)."""
    from . import models  # noqa: F401 - registers every model

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
