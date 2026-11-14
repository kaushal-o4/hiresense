# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/tests_integration/conftest.py
#
# FILE PURPOSE:
# Integration tests against the REAL local models (Ollama + Sentence Transformers).
#
# WHAT THIS FILE DOES:
# 1. Integration test against the REAL local AI models.
# 2. Run from backend/: pytest tests_integration -s (needs Ollama and the voice models).
#
# HOW THIS FILE WORKS:
# Run from the backend folder (Ollama must be running and the model pulled): .\venv\Scripts\python.exe
# -m pytest tests_integration -s -v Tests skip themselves (with the reason) when a model is not
# available. They are slow: a few minutes on CPU.
#
# IMPORTANT FUNCTIONS:
#    Other helper functions: db, llm_ready, embeddings_ready
#
# FILES CONNECTED TO THIS FILE:
#    Uses: app/application_configuration.py, app/database_connection.py, app/seed_initial_data.py,
#    app/services/ai_models/language_model_client.py,
#    app/services/ai_models/sentence_embedding_model.py
#
# IMPORTANT DEPENDENCIES:
#    pytest
#
# IMPORTANT NOTE:
# Test/tool file: it checks or measures the application and is not used by the running app.
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Integration tests against the REAL local models (Ollama + Sentence Transformers).

Run from the backend folder (Ollama must be running and the model pulled):
    .\\venv\\Scripts\\python.exe -m pytest tests_integration -s -v

Tests skip themselves (with the reason) when a model is not available. They are slow: a few minutes on CPU.
"""
import os

os.environ["MONGODB_DB"] = "hiresense_integration_test"

import pytest
from app import database_connection as database, seed_initial_data as seed_module
from app.application_configuration import get_settings

get_settings.cache_clear()


@pytest.fixture(scope="session")
def db():
    database.init_db()
    database.clear_database()  # a throwaway MongoDB database (MONGODB_DB set above), never the app's own
    seed_module.seed()
    factory = database.SessionLocal
    s = factory()
    yield s
    s.close()


@pytest.fixture(scope="session")
def llm_ready():
    from app.services.ai_models import language_model_client as local_llm
    st = local_llm.runtime_status(force=True)
    if not (st["running"] and st["model_ready"]):
        pytest.skip(f"Local LLM not available: {st['error']}")
    return st


@pytest.fixture(scope="session")
def embeddings_ready():
    from app.services.ai_models import sentence_embedding_model as embeddings
    try:
        embeddings.embed(["warm up"])
    except embeddings.EmbeddingUnavailable as exc:
        pytest.skip(f"Embedding model not available: {exc.message}")
    return embeddings
