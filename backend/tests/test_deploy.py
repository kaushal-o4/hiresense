"""Deployment features: shared rate limiter (memory / Redis), cross-site cookies, hosted-AI consent, Gemini speech
recognition and the graceful-shutdown drain. Uses only the standard library and the slim cloud requirements, so it
also runs in a requirements-cloud.txt environment (the Redis tests need `fakeredis`, otherwise they are skipped)."""
import io
import math
import struct
import threading
import time
import wave

import pytest

from app.config import get_settings
from app.services import background, consent, gemini_llm, limiter, stt
from conftest import register_student


def pcm_wav(seconds=2.0, amp=0.3, sr=16000, silent=False):
    n = int(sr * seconds)
    frames = b"".join(struct.pack("<h", 0 if silent else int(amp * 32767 * math.sin(2 * math.pi * 220 * i / sr)))
                      for i in range(n))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(frames)
    return buf.getvalue()


# ------------------------------------------------------------------ limiter

def _exercise(backend_obj):
    assert backend_obj.count("k", 60) == 0
    assert backend_obj.add("k", 60) == 1
    assert backend_obj.add("k", 60) == 2
    assert backend_obj.count("k", 60) == 2
    backend_obj.clear("k")
    assert backend_obj.count("k", 60) == 0
    assert [backend_obj.hit("h", 3, 60) for _ in range(5)] == [True, True, True, False, False]
    assert backend_obj.count("h", 60) == 3  # refused hits are not recorded
    assert backend_obj.count("h", 0.0) == 0  # outside the window


def test_memory_limiter():
    _exercise(limiter.MemoryBackend())


def test_redis_limiter_and_shared_state():
    fakeredis = pytest.importorskip("fakeredis")
    server = fakeredis.FakeServer()
    a = limiter.RedisBackend(fakeredis.FakeRedis(server=server, decode_responses=True))
    _exercise(a)
    b = limiter.RedisBackend(fakeredis.FakeRedis(server=server, decode_responses=True))  # a second API worker
    a.add("shared", 60)
    assert b.count("shared", 60) == 1


def test_login_lockout_uses_redis_when_configured(client):
    fakeredis = pytest.importorskip("fakeredis")
    r = fakeredis.FakeRedis(decode_responses=True)
    limiter.set_redis_client(r)
    try:
        register_student(client, "lock@test.dev")
        for _ in range(limiter_max()):
            assert client.post("/api/auth/login", json={"email": "lock@test.dev", "password": "wrong"}).status_code == 401
        assert client.post("/api/auth/login", json={"email": "lock@test.dev", "password": "Passw0rd!"}).status_code == 429
        assert r.zcard(limiter.KEY_PREFIX + "login:lock@test.dev") == limiter_max()
        assert limiter.status()["backend"] == "redis"
    finally:
        limiter.set_redis_client(None)


def limiter_max():
    from app.routers import auth
    return auth.MAX_FAILED


class _BrokenRedis:
    def pipeline(self):
        raise ConnectionError("redis is down")


def test_redis_outage_falls_back_to_memory():
    limiter.set_redis_client(_BrokenRedis())
    try:
        assert limiter.hit("x", 1, 60) is True  # answered from memory, no exception
        assert limiter.hit("x", 1, 60) is False
        assert limiter.backend() is limiter._memory  # Redis skipped for a while after the failure
    finally:
        limiter.set_redis_client(None)


def test_no_redis_url_means_memory():
    assert get_settings().redis_url == ""
    assert limiter.status() == {"backend": "memory", "redis_configured": False}


# ------------------------------------------------------------------ cookies

def test_cookie_is_lax_by_default(client):
    r = client.post("/api/auth/register/student", json={"full_name": "Ann Lee", "email": "c1@test.dev",
                                                          "password": "Passw0rd!"})
    cookie = r.headers["set-cookie"].lower()
    assert "samesite=lax" in cookie and "httponly" in cookie


def test_cross_site_cookie_is_samesite_none_and_secure(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "cookie_samesite", "none")
    r = client.post("/api/auth/register/student", json={"full_name": "Ann Lee", "email": "c2@test.dev",
                                                          "password": "Passw0rd!"})
    cookie = r.headers["set-cookie"].lower()
    assert "samesite=none" in cookie and "secure" in cookie
    out = client.post("/api/auth/logout").headers["set-cookie"].lower()
    assert "samesite=none" in out and "secure" in out  # browsers ignore a deletion without the same attributes


# ------------------------------------------------------------------ consent

@pytest.fixture()
def hosted_ai(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_ai_provider", "gemini")
    monkeypatch.setattr(gemini_llm, "runtime_status", lambda force=False: {
        "provider": "gemini", "model": "gemini-x", "running": False, "model_ready": False,
        "error": "offline in tests"})


def test_privacy_info_local(client):
    info = client.get("/api/auth/privacy").json()
    assert info["provider"] == "ollama" and info["consent_required"] is False and info["notice"] is None


def test_consent_required_before_ai_features_with_gemini(client, hosted_ai):
    info = client.get("/api/auth/privacy").json()
    assert info["consent_required"] and info["data_leaves_server"] and "Google" in info["notice"]
    user = register_student(client, "nc@test.dev")
    assert user["ai_data_consent_at"] is None
    body = {"job_role": "Developer", "category": "technical", "mode": "text", "question_count": 3}
    r = client.post("/api/student/interviews", json=body)
    assert r.status_code == 428 and "Google" in r.json()["detail"]
    assert client.post("/api/student/english", json={"topic": "travel"}).status_code == 428
    assert client.post("/api/student/resumes", files={"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")}
                       ).status_code == 428

    r = client.post("/api/auth/ai-consent", json={"accept": True})
    assert r.status_code == 200 and r.json()["user"]["ai_data_consent_at"]
    assert client.post("/api/student/interviews", json=body).status_code == 201  # question bank (AI offline)

    client.post("/api/auth/ai-consent", json={"accept": False})
    assert client.get("/api/auth/me").json()["user"]["ai_data_consent_at"] is None
    assert client.post("/api/student/interviews", json=body).status_code == 428


def test_consent_at_registration_is_recorded(client, hosted_ai, db):
    user = register_student(client, "yes@test.dev", ai_consent=True)
    assert user["ai_data_consent_at"]
    from app.models import AuditLog
    from app.odm import select
    actions = [a.action for a in db.scalars(select(AuditLog).where(AuditLog.actor_id == user["id"]))]
    assert "user.ai_consent_given" in actions


def test_consent_not_needed_locally(client):
    register_student(client, "local@test.dev")
    assert consent.required() is False
    r = client.post("/api/student/interviews", json={"job_role": "Developer", "category": "technical",
                                                     "mode": "text", "question_count": 3})
    assert r.status_code == 201


# ------------------------------------------------------------------ hosted speech recognition

def test_wav_stats_without_numpy():
    d, voiced = stt.wav_stats(pcm_wav(2.0))
    assert d == pytest.approx(2.0) and voiced > 1.5
    d, voiced = stt.wav_stats(pcm_wav(1.0, silent=True))
    assert d == pytest.approx(1.0) and voiced == 0
    with pytest.raises(stt.BadAudio):
        stt.wav_stats(b"not a wav file at all, definitely not one........")


def test_gemini_stt_engine(monkeypatch):
    monkeypatch.setattr(get_settings(), "stt_engine", "gemini")
    monkeypatch.setattr(get_settings(), "stt_enabled", True)
    calls = []
    monkeypatch.setattr(gemini_llm, "transcribe", lambda data, prompt=None: calls.append(prompt) or "I built an API.")
    st = stt.status()
    assert st["engine"] == "gemini" and st["live_captions"] is False
    out = stt.transcribe(pcm_wav(2.0), prompt="What did you build?")
    assert out["text"] == "I built an API." and out["engine"] == "gemini" and calls == ["What did you build?"]
    assert stt.transcribe(pcm_wav(1.0, silent=True))["text"] == ""  # silence never reaches Google
    assert len(calls) == 1


def test_gemini_stt_errors_are_readable(monkeypatch):
    from app.services.local_llm import LLMError
    monkeypatch.setattr(get_settings(), "stt_engine", "gemini")
    monkeypatch.setattr(get_settings(), "stt_enabled", True)

    def boom(data, prompt=None):
        raise LLMError("The Gemini API rate limit or quota was reached.", kind="timeout")
    monkeypatch.setattr(gemini_llm, "transcribe", boom)
    with pytest.raises(stt.STTUnavailable) as e:
        stt.transcribe(pcm_wav(2.0))
    assert "quota" in e.value.message


def test_gemini_transcribe_request(monkeypatch):
    sent = {}

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"text": "hello there"}'}]}}]}

    class C:
        def post(self, url, headers, json, timeout):
            sent.update(url=url, body=json)
            return R()

    monkeypatch.setattr(gemini_llm, "runtime_status", lambda force=False: {
        "provider": "gemini", "model": "gemini-x", "running": True, "model_ready": True, "error": None,
        "installed": ["gemini-x"]})
    monkeypatch.setattr(gemini_llm, "_http", lambda: C())
    assert gemini_llm.transcribe(pcm_wav(0.5), "Explain REST") == "hello there"
    part = sent["body"]["contents"][0]["parts"][0]["inlineData"]
    assert part["mimeType"] == "audio/wav" and sent["url"].endswith("/models/gemini-x:generateContent")
    assert "Explain REST" in sent["body"]["systemInstruction"]["parts"][0]["text"]


# ------------------------------------------------------------------ graceful shutdown

def test_drain_waits_for_background_jobs():
    background.started()
    done = threading.Event()
    background.spawn(lambda: (time.sleep(0.3), done.set()), name="test-job")
    assert background.drain(5) == 0 and done.is_set()
    assert background.stopping()
    background.started()
    assert not background.stopping()


def test_drain_gives_up_after_the_deadline():
    background.started()
    release = threading.Event()
    background.spawn(release.wait, name="test-stuck")
    t = time.monotonic()
    assert background.drain(0.3) == 1
    assert time.monotonic() - t < 2
    release.set()
    background.started()
