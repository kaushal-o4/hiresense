"""Health endpoints, request IDs and per-task model routing. No real model is used."""
from app.config import get_settings
from app.services import local_llm, model_router


def test_liveness_needs_nothing(client):
    r = client.get("/api/health/live")
    assert r.status_code == 200 and r.json() == {"status": "alive"}


def test_readiness_reports_components_and_never_fails_for_missing_ai(client, monkeypatch):
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": "m", "running": False, "model_ready": False, "error": "Ollama is not running."})
    r = client.get("/api/health/ready")
    body = r.json()
    assert r.status_code == 200  # the database works, so the app is ready - with reduced AI
    assert body["status"] == "degraded" and "language_model" in body["degraded"]
    assert body["components"]["database"]["ok"] is True
    assert "password" not in r.text.lower() and "secret" not in r.text.lower()


def test_request_id_is_returned_and_unsafe_ids_are_replaced(client):
    assert len(client.get("/api/health/live").headers["x-request-id"]) >= 8
    assert client.get("/api/health/live", headers={"X-Request-ID": "abcdef123456"}).headers["x-request-id"] \
        == "abcdef123456"
    bad = client.get("/api/health/live", headers={"X-Request-ID": "x y\tz"}).headers["x-request-id"]
    assert bad != "x y\tz" and bad.isalnum()


def test_placeholder_secret_key_is_refused_only_when_served_securely(monkeypatch):
    import pytest

    from app import main
    monkeypatch.setattr(main.settings, "secret_key", "change-me-in-production-please-use-a-long-random-string")
    monkeypatch.setattr(main.settings, "cookie_secure", False)
    main.check_secret_key()  # development: warning only
    monkeypatch.setattr(main.settings, "cookie_secure", True)
    with pytest.raises(RuntimeError):
        main.check_secret_key()
    monkeypatch.setattr(main.settings, "secret_key", "x" * 48)
    main.check_secret_key()


def test_router_defaults_to_the_main_model_and_follows_tier_settings(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "main:1b")
    monkeypatch.setenv("OLLAMA_MODEL_FAST", "")  # an empty environment value beats backend/.env
    monkeypatch.setenv("OLLAMA_MODEL_STRONG", "")
    get_settings.cache_clear()
    try:
        assert model_router.configured_model("english_chat") == "main:1b"
        monkeypatch.setenv("OLLAMA_MODEL_FAST", "small:1b")
        monkeypatch.setenv("OLLAMA_MODEL_STRONG", "big:8b")
        get_settings.cache_clear()
        assert model_router.configured_model("english_chat") == "small:1b"
        assert model_router.configured_model("answer_scoring") == "big:8b"
        assert model_router.configured_model("job_match") == "main:1b"  # not in any tier
    finally:
        get_settings.cache_clear()


def test_a_routed_model_that_is_not_downloaded_falls_back_to_the_main_model(monkeypatch):
    seen = {}

    class FakeStream:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def iter_lines(self):
            yield '{"message":{"content":"{}"},"done":true,"done_reason":"stop"}'

    unloaded = []

    class FakeHttp:
        def stream(self, method, url, json=None, timeout=None):
            seen["model"] = json["model"]
            return FakeStream()

        def post(self, url, json=None, timeout=None):
            unloaded.append((json["model"], json["keep_alive"]))

    monkeypatch.setattr(local_llm, "_http", lambda: FakeHttp())
    monkeypatch.setattr(local_llm, "_active_model", None)
    main = get_settings().ollama_model
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": main, "running": True, "model_ready": True, "error": None,
        "installed": [main]})
    local_llm.chat_json("s", "p", {}, model="not-installed:9b")
    assert seen["model"] == main
    monkeypatch.setattr(local_llm, "runtime_status", lambda force=False: {
        "provider": "ollama", "model": main, "running": True, "model_ready": True, "error": None,
        "installed": [main, "small:1b"]})
    assert unloaded == []  # same model as before: nothing to unload
    local_llm.chat_json("s", "p", {}, model="small:1b")
    assert seen["model"] == "small:1b"
    assert unloaded == [(main, 0)]  # switching frees the GPU for the new model first
