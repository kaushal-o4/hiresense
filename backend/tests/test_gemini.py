"""Gemini provider (services/gemini_llm.py) and the Ollama fallback in local_llm. No real API is called: the HTTP
client is replaced by a fake that replays Server-Sent Events."""
import json

import pytest

from app.config import get_settings
from app.services import gemini_llm, local_llm, model_router


def sse(*chunks) -> list[str]:
    return [f"data: {json.dumps(c)}" for c in chunks]


def text_chunk(text, finish=None, thought=False):
    cand = {"content": {"parts": [{"text": text, **({"thought": True} if thought else {})}]}}
    if finish:
        cand["finishReason"] = finish
    return {"candidates": [cand]}


class FakeResponse:
    def __init__(self, status, lines=(), body="", headers=None):
        self.status_code, self.lines, self.body, self.headers = status, list(lines), body, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body.encode()

    def iter_lines(self):
        return iter(self.lines)


class FakeHttp:
    def __init__(self, responses):
        self.responses = list(responses)
        self.bodies = []

    def stream(self, method, url, params=None, headers=None, json=None, timeout=None):
        self.bodies.append({"url": url, "json": json, "key": headers["x-goog-api-key"],
                            "model": url.split("/models/")[1].split(":")[0], "timeout": timeout})
        return self.responses.pop(0)


@pytest.fixture()
def gemini(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_ai_provider", "gemini")
    monkeypatch.setattr(s, "gemini_api_key", "test-key")
    monkeypatch.setattr(s, "gemini_model", "gemini-flash-latest")
    monkeypatch.setattr(gemini_llm, "runtime_status", lambda force=False: {
        "provider": "gemini", "model": "gemini-flash-latest", "running": True, "model_ready": True, "error": None,
        "installed": ["gemini-flash-latest", "gemini-9.0-pro"]})
    monkeypatch.setattr(gemini_llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(gemini_llm, "_thinking_form", {})
    monkeypatch.setattr(local_llm, "_gemini_down_until", 0.0)
    monkeypatch.setattr(s, "gemini_backup_models", "")  # single-model behaviour unless a test adds backups
    monkeypatch.setattr(gemini_llm, "_busy_until", {})
    gemini_llm._http()  # creates the semaphore

    def install(*responses):
        fake = FakeHttp(responses)
        monkeypatch.setattr(gemini_llm, "_http", lambda: fake)
        return fake
    return install


def test_streams_json_and_skips_thought_parts(gemini):
    fake = gemini(FakeResponse(200, sse(text_chunk("hidden reasoning", thought=True), text_chunk('{"score":'),
                                        {**text_chunk(" 7}", finish="STOP"),
                                         "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 4}})))
    seen = []
    r = local_llm.chat_json("sys", "prompt", {"type": "object"}, on_delta=seen.append, max_tokens=100)
    assert json.loads(r.content) == {"score": 7}
    assert seen == ['{"score":', '{"score": 7}']
    assert (r.prompt_tokens, r.output_tokens) == (12, 4)
    assert r.timings["model"] == "gemini:gemini-flash-latest"
    body = fake.bodies[0]
    assert fake.bodies[0]["key"] == "test-key" and "key=" not in body["url"]  # key in a header, never the URL
    gen = body["json"]["generationConfig"]
    assert gen["responseMimeType"] == "application/json" and gen["responseJsonSchema"] == {"type": "object"}
    assert gen["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert body["json"]["systemInstruction"]["parts"][0]["text"] == "sys"


def test_retries_rate_limit_and_server_errors(gemini):
    fake = gemini(FakeResponse(429, body="{}"), FakeResponse(503, body="{}"),
                  FakeResponse(200, sse(text_chunk("{}", finish="STOP"))))
    assert local_llm.chat_json("s", "p", {}).content == "{}"
    assert len(fake.bodies) == 3


def test_unsupported_thinking_option_is_downgraded(gemini):
    # real message from gemini-3.8-flash (2026-10-29), then a model that takes no thinkingLevel at all
    minimal = json.dumps({"error": {"message": "Thinking level MINIMAL is not supported for this model."}})
    level = json.dumps({"error": {"message": "thinking_level is not supported for this model"}})
    fake = gemini(FakeResponse(400, body=minimal), FakeResponse(400, body=level),
                  FakeResponse(200, sse(text_chunk("{}", finish="STOP"))))
    local_llm.chat_json("s", "p", {})
    sent = [b["json"]["generationConfig"]["thinkingConfig"] for b in fake.bodies]
    assert sent == [{"thinkingLevel": "minimal"}, {"thinkingLevel": "low"}, {"thinkingBudget": 0}]
    assert gemini_llm._thinking_form["gemini-flash-latest"] == "budget"  # remembered for the next request


def test_timeout_is_not_retried_and_starts_cooldown(gemini, monkeypatch):
    import httpx

    class Slow(FakeResponse):
        def __enter__(self):
            raise httpx.ReadTimeout("timed out")
    fake = gemini(Slow(200), FakeResponse(200, sse(text_chunk("{}", finish="STOP"))))
    monkeypatch.setattr(local_llm, "_ollama_status", lambda force=False: {
        "provider": "ollama", "model": "m", "running": True, "model_ready": True, "error": None, "installed": ["m"]})
    calls = []
    monkeypatch.setattr(local_llm, "_chat_ollama", lambda *a, **k: calls.append(1) or local_llm.LLMResult(
        content="{}", prompt_tokens=1, output_tokens=1, latency_ms=1))
    local_llm.chat_json("s", "p", {})
    assert len(fake.bodies) == 1 and calls == [1]  # no second wait on Gemini; Ollama answered
    local_llm.chat_json("s", "p", {})
    assert len(fake.bodies) == 1 and calls == [1, 1]  # cooling down: Gemini skipped entirely


def test_cut_off_answer_is_an_error(gemini, monkeypatch):
    gemini(FakeResponse(200, sse(text_chunk('{"a": ', finish="MAX_TOKENS"))))
    monkeypatch.setattr(get_settings(), "ai_fallback_to_ollama", False)
    with pytest.raises(local_llm.LLMError) as e:
        local_llm.chat_json("s", "p", {})
    assert e.value.kind == "bad_output"


def test_falls_back_to_ollama_when_gemini_fails(gemini, monkeypatch):
    gemini(FakeResponse(403, body=json.dumps({"error": {"message": "API key not valid"}})))
    used = {}
    monkeypatch.setattr(local_llm, "_ollama_status", lambda force=False: {
        "provider": "ollama", "model": "test-model:latest", "running": True, "model_ready": True, "error": None,
        "installed": ["test-model:latest"]})

    def fake_ollama(system, prompt, schema, **kw):
        used.update(kw)
        return local_llm.LLMResult(content="{}", prompt_tokens=1, output_tokens=1, latency_ms=1)
    monkeypatch.setattr(local_llm, "_chat_ollama", fake_ollama)
    assert local_llm.chat_json("s", "p", {}, model="gemini-9.0-pro").content == "{}"
    assert used["model"] is None  # a Gemini model name means nothing to Ollama


def test_no_fallback_after_text_was_streamed(gemini, monkeypatch):
    import httpx

    class Broken(FakeResponse):
        def iter_lines(self):
            yield from sse(text_chunk("Hello, "))
            raise httpx.ReadError("connection reset")
    gemini(Broken(200))
    monkeypatch.setattr(local_llm, "_chat_ollama", lambda *a, **k: pytest.fail("must not restart a spoken reply"))
    with pytest.raises(local_llm.LLMError):
        local_llm.chat_json("s", "p", {}, on_delta=lambda t: None)


def test_status_picks_newest_flash_when_configured_model_is_missing(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_api_key", "k")
    monkeypatch.setattr(s, "gemini_model", "gemini-1.0-flash")
    models = [{"name": f"models/{n}", "supportedGenerationMethods": ["generateContent"]} for n in
              ("gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.6-flash-preview", "gemini-3.5-flash-lite",
               "gemini-3.5-pro")]

    class R:
        status_code = 200

        def json(self):
            return {"models": models}

    class H:
        def get(self, *a, **k):
            return R()
    monkeypatch.setattr(gemini_llm, "_http", lambda: H())
    st = gemini_llm.runtime_status(force=True)
    assert st["model_ready"] and st["model"] == "gemini-3.5-flash"  # stable beats a newer preview


def test_missing_key_reports_setup_hint(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_api_key", "")
    st = gemini_llm.runtime_status(force=True)
    assert not st["running"] and "GEMINI_API_KEY" in st["error"]


def test_routing_uses_gemini_tier_models(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "local_ai_provider", "gemini")
    monkeypatch.setattr(s, "gemini_model", "g-main")
    monkeypatch.setattr(s, "gemini_model_strong", "g-strong")
    assert model_router.configured_model("answer_scoring") == "g-strong"
    assert model_router.configured_model("english_chat") == "g-main"


# ---------------------------------------------------------------- switching to a backup model (2026-11-04)

def _with_backup(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "gemini_backup_models", "gemini-backup, gemini-not-offered")
    monkeypatch.setattr(gemini_llm, "runtime_status", lambda force=False: {
        "provider": "gemini", "model": "gemini-flash-latest", "running": True, "model_ready": True, "error": None,
        "installed": ["gemini-flash-latest", "gemini-backup"]})


def test_overloaded_model_switches_to_backup_without_waiting(gemini, monkeypatch):
    _with_backup(monkeypatch)
    slept = []
    monkeypatch.setattr(gemini_llm.time, "sleep", slept.append)
    fake = gemini(FakeResponse(503, body="{}"), FakeResponse(200, sse(text_chunk("{}", finish="STOP"))),
                  FakeResponse(200, sse(text_chunk("{}", finish="STOP"))))
    r = local_llm.chat_json("s", "p", {})
    assert [b["model"] for b in fake.bodies] == ["gemini-flash-latest", "gemini-backup"]
    assert slept == [] and r.timings["model"] == "gemini:gemini-backup"
    assert fake.bodies[0]["timeout"].read == get_settings().gemini_switch_after_seconds  # shorter wait while a backup is left
    # the overloaded model is tried last for a while
    local_llm.chat_json("s", "p", {})
    assert fake.bodies[2]["model"] == "gemini-backup"


def test_slow_model_switches_to_backup(gemini, monkeypatch):
    import httpx
    _with_backup(monkeypatch)

    class Slow(FakeResponse):
        def __enter__(self):
            raise httpx.ReadTimeout("timed out")
    fake = gemini(Slow(200), FakeResponse(200, sse(text_chunk('{"a": 1}', finish="STOP"))))
    monkeypatch.setattr(local_llm, "_chat_ollama", lambda *a, **k: pytest.fail("a backup Gemini model answers first"))
    assert json.loads(local_llm.chat_json("s", "p", {}).content) == {"a": 1}
    assert [b["model"] for b in fake.bodies] == ["gemini-flash-latest", "gemini-backup"]


def test_backup_not_offered_to_key_is_skipped(monkeypatch):
    monkeypatch.setattr(get_settings(), "gemini_backup_models", "b, c, a")
    monkeypatch.setattr(gemini_llm, "_busy_until", {})
    assert gemini_llm.candidate_models("a", ["a", "b"]) == ["a", "b"]  # "c" not offered, "a" not repeated


def test_cut_off_json_retries_on_backup_model(gemini, monkeypatch):
    _with_backup(monkeypatch)
    fake = gemini(FakeResponse(200, sse(text_chunk('{"skills": ["Pyth', finish="STOP"))),
                  FakeResponse(200, sse(text_chunk('{"skills": []}', finish="STOP"))))
    r = local_llm.chat_json("s", "p", {})
    assert json.loads(r.content) == {"skills": []} and r.timings["model"] == "gemini:gemini-backup"
    assert [b["model"] for b in fake.bodies] == ["gemini-flash-latest", "gemini-backup"]


def test_streamed_reply_is_never_restarted_on_bad_json(gemini, monkeypatch):
    _with_backup(monkeypatch)
    fake = gemini(FakeResponse(200, sse(text_chunk('not json', finish="STOP"))))
    r = local_llm.chat_json("s", "p", {}, on_delta=lambda t: None)  # text already shown/spoken
    assert r.content == "not json" and len(fake.bodies) == 1
