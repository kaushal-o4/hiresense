"""Integration tests against the REAL local models (Ollama + Sentence Transformers).

Run from the backend folder (Ollama must be running and the model pulled):
    .\\venv\\Scripts\\python.exe -m pytest tests_integration -s -v

Tests skip themselves (with the reason) when a model is not available. They are slow: a few minutes on CPU.
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, seed as seed_module
from app.config import get_settings
from app.database import Base

get_settings.cache_clear()


@pytest.fixture(scope="session")
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    database.SessionLocal = factory
    seed_module.SessionLocal = factory
    seed_module.seed(demo=False)
    s = factory()
    yield s
    s.close()


@pytest.fixture(scope="session")
def llm_ready():
    from app.services import local_llm
    st = local_llm.runtime_status(force=True)
    if not (st["running"] and st["model_ready"]):
        pytest.skip(f"Local LLM not available: {st['error']}")
    return st


@pytest.fixture(scope="session")
def embeddings_ready():
    from app.services import embeddings
    try:
        embeddings.embed(["warm up"])
    except embeddings.EmbeddingUnavailable as exc:
        pytest.skip(f"Embedding model not available: {exc.message}")
    return embeddings
