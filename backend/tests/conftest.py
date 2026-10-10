import os

# Automated tests never call real models: Ollama points at a closed port and embeddings are off unless a test
# installs the deterministic FAKE embedding below. Real-model checks live in tests_integration/.
os.environ["OLLAMA_BASE_URL"] = "http://127.0.0.1:9"
os.environ["OLLAMA_MODEL"] = "test-model:latest"
os.environ["EMBEDDING_PROVIDER"] = "none"
os.environ["TTS_ENABLED"] = "false"
os.environ["STT_ENABLED"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database, seed as seed_module
from app.config import get_settings
from app.database import Base, get_db
from app.main import app

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_ai_caches():
    from app.services import local_llm
    local_llm._status_cache.update(at=0.0, value=None)
    yield


@pytest.fixture()
def db_session_factory(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(seed_module, "SessionLocal", factory)
    seed_module.seed(demo=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def client(db_session_factory):
    def override():
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    from app.routers import auth
    auth._failed.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def db(db_session_factory):
    s = db_session_factory()
    yield s
    s.close()


def make_client(client_fixture_app=app):
    return TestClient(client_fixture_app)


@pytest.fixture()
def new_client(client):
    """Factory for additional independent clients (separate cookie jars) sharing the same DB."""
    clients = []

    def _make():
        c = TestClient(app)
        clients.append(c)
        return c
    yield _make
    for c in clients:
        c.close()


def register_student(c, email="stu@test.dev", **extra):
    payload = {"full_name": "Test Student", "email": email, "password": "Passw0rd!", "college": "ABC College",
               "branch": "Computer Science", "graduation_year": 2027}
    payload.update(extra)
    r = c.post("/api/auth/register/student", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["user"]


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["user"]


def admin_login(c):
    return login(c, get_settings().admin_email, get_settings().admin_password)


def fake_embed(texts):
    """MOCK embedding: bag of hashed words + character trigrams, unit length. Deterministic, no model.

    Similar wording -> similar vectors, which is enough to exercise the matching logic, NOT to judge quality.
    """
    import hashlib

    import numpy as np
    out = np.zeros((len(texts), 256), dtype="float32")
    for i, t in enumerate(texts):
        words = t.lower().split()
        grams = words + [w[j:j + 3] for w in words for j in range(max(1, len(w) - 2))]
        for g in grams:
            out[i, int(hashlib.md5(g.encode()).hexdigest(), 16) % 256] += 1.0
        n = np.linalg.norm(out[i])
        out[i] = out[i] / n if n else out[i]
        if not n:
            out[i, 0] = 1.0
    return out


@pytest.fixture()
def fake_embeddings(monkeypatch):
    """MOCKED embedding model for semantic-matching tests."""
    from app.services import embeddings
    monkeypatch.setattr(embeddings, "embed", fake_embed)
    return fake_embed


@pytest.fixture()
def fake_ai(monkeypatch):
    """MOCKED local LLM: deterministic stand-in used to test the AI-dependent workflows end to end."""
    from app.services import ai

    monkeypatch.setattr(ai, "ai_status", lambda db: {"configured": True, "enabled": True, "available": True, "model": "stub"})
    counter = {"q": 0}

    def next_q(db, user_id, **kw):
        counter["q"] += 1
        return {"question": f"Stub question {counter['q']} about {kw['job_role']}?", "question_type": "technical",
                "is_followup": counter["q"] > 1}

    def evaluate(db, user_id, **kw):
        return {"relevance": 8, "correctness": 7, "clarity": 8, "communication": 9, "feedback": "Good answer.",
                "better_answer_hint": "Add an example.", "score": 79.0}

    def score(db, user_id, **kw):
        return {"relevance": 8, "correctness": 7, "clarity": 8, "communication": 9, "score": 79.0,
                "details": {"completeness": 7, "next_difficulty": "medium"}, "feedback": ""}

    def feedback(db, user_id, **kw):
        return {"strengths": ["clear"], "missing_concepts": [], "improvements": ["Add an example."],
                "feedback": "Good answer.", "better_answer_hint": "Add an example.", "sample_answer": "Sample."}

    def report(db, user_id, **kw):
        return {"summary": "Solid.", "strengths": ["clarity"], "weaknesses": ["depth"], "suggestions": ["practise"],
                "recommended_practice": ["SQL"]}

    def analyze(db, user_id, text, role):
        return {"candidate_summary": "CS student", "education": [], "skills": [{"name": "Python", "category": "programming_language"},
                {"name": "Docker", "category": "tool"}], "projects": [], "experience": [], "certifications": [],
                "strengths": ["Python"], "missing_skills": ["Kubernetes"], "improvement_areas": ["Add metrics"],
                "resume_score": 72, "suggested_interview_questions": ["Tell me about Python"]}

    def eng_reply(db, user_id, **kw):
        return {"reply": "Great, tell me more?", "avatar_mode": "speaking", "encouragement": "",
                "corrections": [], "suggested_followups": []}

    def eng_eval(db, user_id, **kw):
        return {"grammar": 7, "vocabulary": 6, "fluency": 7, "sentence_formation": 8, "summary": "ok",
                "strengths": ["a"], "suggestions": ["b"]}

    monkeypatch.setattr(ai, "next_interview_question", next_q)
    monkeypatch.setattr(ai, "evaluate_answer", evaluate)
    monkeypatch.setattr(ai, "score_answer", score)
    monkeypatch.setattr(ai, "answer_feedback", feedback)
    monkeypatch.setattr(ai, "interview_report", report)
    monkeypatch.setattr(ai, "analyze_resume", analyze)
    monkeypatch.setattr(ai, "english_reply", eng_reply)
    monkeypatch.setattr(ai, "english_evaluate", eng_eval)
    return ai
