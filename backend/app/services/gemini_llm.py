"""Client for the Google Gemini API (hosted language model).

Used when LOCAL_AI_PROVIDER=gemini. It has the same contract as local_llm's Ollama path (same LLMResult/LLMError,
JSON schema, streamed `on_delta`), so ai.py doesn't know which one answered. local_llm.chat_json dispatches here and
falls back to Ollama when Gemini fails and AI_FALLBACK_TO_OLLAMA=true.

Speed: Gemini Flash generates far faster than qwen3:4b on the 4 GB laptop GPU (~20 tokens/s), and thinking is turned
down (GEMINI_THINKING=minimal), since our prompts are scoring/chat with a fixed JSON schema.
Reliability: rate limits (429) and Google-side errors (5xx) are retried with backoff before the first token; a
configured model this key cannot use is replaced by the newest available Flash model.

Privacy: prompts contain resumes and interview answers, and they are sent to Google. Like local_llm, this module never
logs prompt or response text, and it never logs the API key (sent as a header, not in the URL).
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from typing import Callable

import httpx

from ..config import get_settings
from .local_llm import LLMError, LLMResult

log = logging.getLogger("hiresense.gemini_llm")

_RETRY_STATUS = {429, 500, 502, 503, 504}
_status_cache: dict = {"at": 0.0, "value": None}
_status_lock = threading.Lock()
_STATUS_TTL = 300.0  # seconds; the model list rarely changes

_client: httpx.Client | None = None
_client_lock = threading.Lock()
_sem: threading.BoundedSemaphore | None = None

# Which thinkingConfig form each model accepted ("level", "level_low", "budget" or "none"). Gemini 3+ takes
# thinkingLevel (some, e.g. 3.8 Flash, reject "minimal" -> "low"), 2.5 takes thinkingBudget, older models reject both;
# for an alias such as gemini-flash-latest we find out on first use.
_thinking_form: dict[str, str] = {}


def _http() -> httpx.Client:
    """One shared client: keeps the TLS connection to Google open between requests."""
    global _client, _sem
    with _client_lock:
        if _client is None:
            s = get_settings()
            _client = httpx.Client(timeout=httpx.Timeout(s.gemini_timeout_seconds, connect=5.0),
                                   limits=httpx.Limits(max_keepalive_connections=8, keepalive_expiry=120))
            _sem = threading.BoundedSemaphore(max(1, s.gemini_max_concurrent))
        return _client


def _headers() -> dict:
    return {"x-goog-api-key": get_settings().gemini_api_key.strip(), "Content-Type": "application/json"}


def _short(name: str) -> str:
    return name.removeprefix("models/")


def _version(name: str) -> float:
    m = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(m.group(1)) if m else 0.0


def _best_flash(names: list[str]) -> str | None:
    """Newest stable general-purpose Flash model (a preview only if there is no stable one); None if none."""
    skip = ("lite", "image", "tts", "audio", "live", "embedding", "exp", "thinking", "computer")
    flash = [n for n in names if "flash" in n and not any(x in n for x in skip) and _version(n) > 0]
    if not flash:
        return None
    return max(flash, key=lambda n: ("preview" not in n, _version(n), -len(n)))


def _api_error(status_code: int, body: str) -> LLMError:
    detail = ""
    try:
        detail = str(json.loads(body).get("error", {}).get("message", ""))[:300]
    except (ValueError, AttributeError):
        pass
    log.warning("gemini returned HTTP %s: %s", status_code, detail)
    if status_code in (401, 403) or (status_code == 400 and "API key" in detail):
        _status_cache["at"] = 0.0
        return LLMError("The Gemini API key was rejected. Check GEMINI_API_KEY in backend/.env.",
                        kind="not_running")
    if status_code == 404:
        _status_cache["at"] = 0.0
        return LLMError("The configured Gemini model is not available. Check GEMINI_MODEL in backend/.env.",
                        kind="model_missing")
    if status_code == 429:
        return LLMError("The Gemini API rate limit or quota was reached. Please try again in a minute.",
                        kind="timeout", status_code=429)
    return LLMError(f"The Gemini API returned an error ({status_code}). {detail}".strip(), kind="http_error")


def runtime_status(force: bool = False) -> dict:
    """{"provider", "model", "running", "model_ready", "error", "installed"} - cached for a few minutes."""
    s = get_settings()
    base = {"provider": "gemini", "model": s.gemini_model}
    if not s.gemini_api_key.strip():
        return {**base, "running": False, "model_ready": False,
                "error": "GEMINI_API_KEY is not set in backend/.env (get a key at https://aistudio.google.com/apikey)."}
    with _status_lock:
        cached = _status_cache["value"]
        if cached and not force and time.monotonic() - _status_cache["at"] < _STATUS_TTL:
            return cached
    try:
        r = _http().get(f"{s.gemini_base_url.rstrip('/')}/models", params={"pageSize": 1000}, headers=_headers(),
                        timeout=8.0)
        if r.status_code != 200:
            err = _api_error(r.status_code, r.text)
            value = {**base, "running": False, "model_ready": False, "error": err.message}
        else:
            names = [_short(m.get("name", "")) for m in r.json().get("models", [])
                     if "generateContent" in (m.get("supportedGenerationMethods") or [])]
            model = s.gemini_model if s.gemini_model in names else _best_flash(names)
            if model and model != s.gemini_model:
                log.warning("gemini model '%s' is not available to this key; using '%s'", s.gemini_model, model)
            value = {**base, "model": model or s.gemini_model, "running": True, "model_ready": bool(model),
                     "installed": names,
                     "error": None if model else f"The Gemini model '{s.gemini_model}' is not available to this key."}
    except (httpx.HTTPError, ValueError):
        value = {**base, "running": False, "model_ready": False,
                 "error": "Could not reach the Gemini API. Check the internet connection."}
    with _status_lock:
        _status_cache.update(at=time.monotonic(), value=value)
    return value


def _thinking_config(model: str, form: str) -> dict | None:
    level = get_settings().gemini_thinking.strip().lower()
    if form == "level":
        return {"thinkingLevel": "minimal" if level == "off" else level}
    if form == "level_low":
        return {"thinkingLevel": "low"}
    if form == "budget":
        # 0 turns thinking off on 2.5 Flash; Pro models need some budget
        budget = {"off": 0, "minimal": 0, "low": 512, "medium": 2048, "high": 8192}.get(level, 0)
        return {"thinkingBudget": 128 if "pro" in model and budget == 0 else budget}
    return None


def _initial_form(model: str) -> str:
    if model in _thinking_form:
        return _thinking_form[model]
    v = _version(model)
    if 0 < v < 2.5:
        return "none"
    return "budget" if v == 2.5 else "level"


def _body(system: str, prompt: str, schema: dict, max_tokens: int, temperature: float, model: str,
          form: str, use_schema: bool) -> dict:
    gen: dict = {"temperature": temperature, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}
    if schema and use_schema:
        gen["responseJsonSchema"] = schema
    elif schema:  # schema rejected by the API: describe it in the instructions instead
        system += "\n\nThe JSON object must match this JSON Schema:\n" + json.dumps(schema)
    thinking = _thinking_config(model, form)
    if thinking:
        gen["thinkingConfig"] = thinking
    return {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen}


def chat_json(system: str, prompt: str, schema: dict, *, max_tokens: int | None = None,
              temperature: float | None = None, priority: str = "interactive",
              on_delta: Callable[[str], None] | None = None, model: str | None = None) -> LLMResult:
    """Ask Gemini for JSON matching `schema`. Raises LLMError on any failure (same kinds as local_llm).

    `priority` is accepted for compatibility: hosted requests don't compete for this computer's GPU/CPU, so
    background work is never paused for interactive work here."""
    s = get_settings()
    status = runtime_status()
    if not status["running"]:
        raise LLMError(status["error"], kind="not_running")
    if not status["model_ready"]:
        raise LLMError(status["error"], kind="model_missing")
    primary = model if model and model in status.get("installed", []) else status["model"]
    candidates = candidate_models(primary, status.get("installed") or [primary])
    max_out = min(max_tokens or s.ai_max_output_tokens, s.ai_max_output_tokens)
    temp = s.ai_temperature if temperature is None else temperature

    _http()
    queued = time.monotonic()
    if not _sem.acquire(timeout=s.ai_timeout_seconds):
        raise LLMError("The AI is busy with other requests. Please try again in a minute.", kind="timeout",
                       status_code=429)
    parts: list[str] = []
    usage: dict = {}
    finish: str | None = None
    first_token: float | None = None
    started = time.monotonic()
    retries = max(0, s.gemini_retries)
    attempt = 0
    switched: list[str] = []
    try:
        for idx, use_model in enumerate(candidates):
            last = idx == len(candidates) - 1
            try:
                attempt = _stream_one(s, system, prompt, schema, max_out, temp, use_model, on_delta, parts, usage,
                                      retries if last else 0, last)
            except _Overloaded as ov:
                _mark_busy(use_model, s.gemini_model_cooldown_seconds)
                switched.append(use_model)
                log.warning("gemini model %s %s; switching to %s", use_model, ov.reason, candidates[idx + 1])
                continue
            finish = usage.pop("_finish", None)
            first_token = usage.pop("_first_token", None)
            # Measured 2026-11-04: gemini-3.5-flash sometimes ends the stream early (finish STOP, ~600 of ~1500
            # tokens), leaving cut-off JSON. When nothing was shown to the user yet (no on_delta), ask the next model
            # instead of letting the caller retry the same, struggling one.
            if not last and on_delta is None and not _is_json("".join(parts)):
                _mark_busy(use_model, 60.0)
                switched.append(use_model)
                log.warning("gemini model %s returned incomplete JSON; switching to %s", use_model, candidates[idx + 1])
                parts.clear()
                usage.clear()
                continue
            break
    finally:
        _sem.release()
    done_at = time.monotonic()
    if finish == "MAX_TOKENS":
        raise LLMError("The AI's answer was cut off (output limit reached). Please try again.", kind="bad_output")
    if finish in ("SAFETY", "RECITATION", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"):
        raise LLMError("The AI declined to answer this request (content filter).", kind="bad_output")
    if not parts:
        raise LLMError("The Gemini API returned an empty answer.", kind="bad_output")
    timings = {"queue_ms": round((started - queued) * 1000), "load_ms": 0, "prompt_ms": 0,
               "generate_ms": round(((done_at - (first_token or done_at))) * 1000),
               "first_token_ms": round(((first_token or done_at) - started) * 1000),
               "attempts": attempt + len(switched)}
    return LLMResult(content="".join(parts).strip(), prompt_tokens=usage.get("promptTokenCount"),
                     output_tokens=usage.get("candidatesTokenCount"), latency_ms=int((done_at - started) * 1000),
                     timings={**timings, "model": f"gemini:{use_model}"})


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except ValueError:
        return False


class _Overloaded(Exception):
    """This model is overloaded or slow to start; the caller moves on to the next candidate model."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


_busy_until: dict[str, float] = {}


def _mark_busy(model: str, seconds: float) -> None:
    _busy_until[model] = time.monotonic() + max(0.0, seconds)


def candidate_models(primary: str, installed: list[str]) -> list[str]:
    """Models to try in order: the chosen one, then GEMINI_BACKUP_MODELS this key can use. Models that were
    overloaded recently go to the back of the list (they are still tried if everything else fails)."""
    s = get_settings()
    backups = [m.strip() for m in (s.gemini_backup_models or "").split(",") if m.strip()]
    seen, order = set(), []
    for m in [primary, *backups]:
        if m and m not in seen and (m == primary or m in installed):
            seen.add(m)
            order.append(m)
    now = time.monotonic()
    fresh = [m for m in order if _busy_until.get(m, 0) <= now]
    busy = [m for m in order if _busy_until.get(m, 0) > now]
    return fresh + busy


def _stream_one(s, system, prompt, schema, max_out, temp, use_model, on_delta, parts, usage, retries, last) -> int:
    """Stream one model's answer into `parts`/`usage`. Returns the attempt count. Raises _Overloaded (when another
    model is left to try and nothing was streamed yet) or LLMError."""
    url = f"{s.gemini_base_url.rstrip('/')}/models/{use_model}:streamGenerateContent"
    # wait less for the first piece when there is another model to switch to
    wait_first = s.gemini_timeout_seconds if last else min(s.gemini_timeout_seconds, s.gemini_switch_after_seconds)
    timeout = httpx.Timeout(wait_first, connect=5.0)
    form, use_schema = _initial_form(use_model), True
    attempt = 0
    while True:
        attempt += 1
        body = _body(system, prompt, schema, max_out, temp, use_model, form, use_schema)
        try:
            with _http().stream("POST", url, params={"alt": "sse"}, headers=_headers(), json=body,
                                timeout=timeout) as r:
                if r.status_code != 200:
                    text = r.read().decode("utf-8", "replace")
                    low = text.lower()
                    # Unsupported request options: adjust and resend (doesn't use up a retry)
                    if r.status_code == 400 and "thinking" in low and form != "none":
                        level = s.gemini_thinking.strip().lower()
                        form = {"level": "level_low" if level in ("minimal", "off") else "budget",
                                "level_low": "budget", "budget": "none"}[form]
                        attempt -= 1
                        continue
                    if r.status_code == 400 and use_schema and "schema" in low:
                        use_schema = False
                        attempt -= 1
                        continue
                    if (r.status_code in _RETRY_STATUS or r.status_code == 404) and not last:
                        raise _Overloaded(f"HTTP {r.status_code}")
                    if r.status_code in _RETRY_STATUS and attempt <= retries:
                        wait = min(8.0, 2 ** (attempt - 1))
                        try:
                            wait = min(8.0, max(wait, float(r.headers.get("retry-after", 0))))
                        except ValueError:
                            pass
                        log.warning("gemini HTTP %s; retry %s/%s in %.1fs", r.status_code, attempt, retries, wait)
                        time.sleep(wait)
                        continue
                    raise _api_error(r.status_code, text)
                _thinking_form[use_model] = form
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    try:
                        chunk = json.loads(line[5:].strip())
                    except ValueError:
                        raise LLMError("The Gemini API returned an unreadable response.", kind="bad_output")
                    if chunk.get("usageMetadata"):
                        usage.update(chunk["usageMetadata"])
                    if (chunk.get("promptFeedback") or {}).get("blockReason"):
                        raise LLMError("The AI declined to answer this request (content filter).",
                                       kind="bad_output")
                    cand = (chunk.get("candidates") or [{}])[0]
                    for p in (cand.get("content") or {}).get("parts") or []:
                        if p.get("text") and not p.get("thought"):
                            if "_first_token" not in usage:
                                usage["_first_token"] = time.monotonic()
                            parts.append(p["text"])
                            if on_delta:
                                on_delta("".join(parts))
                    if cand.get("finishReason"):
                        usage["_finish"] = cand["finishReason"]
            return attempt
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            # A dropped connection is retried if nothing was handed to the caller yet. A timeout is not: measured
            # 2026-10-29, when Gemini is overloaded the second try is just as slow, and the Ollama fallback
            # (local_llm) answers sooner.
            if not parts and not last:
                raise _Overloaded("timed out" if isinstance(exc, httpx.TimeoutException) else type(exc).__name__)
            if parts or attempt > retries or isinstance(exc, httpx.TimeoutException):
                if isinstance(exc, httpx.TimeoutException):
                    raise LLMError("The Gemini API took too long to respond. Please try again.",
                                   kind="timeout", status_code=504)
                _status_cache["at"] = 0.0
                raise LLMError("Could not reach the Gemini API. Check the internet connection.",
                               kind="not_running")
            log.warning("gemini %s; retry %s/%s", type(exc).__name__, attempt, retries)
            time.sleep(min(8.0, 2 ** (attempt - 1)))


def warmup() -> dict:
    """Check the key and resolve the model ahead of time, and open the TLS connection (no model to load)."""
    t = time.monotonic()
    st = runtime_status(force=True)
    return {"ok": bool(st["running"] and st["model_ready"]), "already_loaded": True,
            "load_ms": round((time.monotonic() - t) * 1000), "reason": st.get("error")}


TRANSCRIBE_SYSTEM = ("You are a speech-to-text engine. Write down exactly what the speaker says in this recording, in "
                     "English, with normal punctuation. Do not answer, summarise, translate or correct it. If nothing "
                     "is said, return an empty string.")


def transcribe(wav: bytes, prompt: str | None = None) -> str:
    """Speech-to-text with Gemini (STT_ENGINE=gemini, for hosts without the Whisper packages). The WAV goes to Google
    with the request and is not stored here. Moves on to the backup models on overload. Raises LLMError."""
    import base64
    s = get_settings()
    status = runtime_status()
    if not (status["running"] and status["model_ready"]):
        raise LLMError(status["error"] or "Gemini is not available.", kind="not_running")
    system = TRANSCRIBE_SYSTEM
    if prompt:
        system += ("\n\nThe speaker is answering this interview question (use it only to spell technical words): "
                   + prompt[:500])
    schema = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    audio = base64.b64encode(wav).decode()
    last_err: LLMError | None = None
    _http()
    for use_model in candidate_models(status["model"], status.get("installed") or [status["model"]]):
        gen: dict = {"temperature": 0.0, "maxOutputTokens": 2048, "responseMimeType": "application/json",
                     "responseJsonSchema": schema}
        thinking = _thinking_config(use_model, _initial_form(use_model))
        if thinking:
            gen["thinkingConfig"] = thinking
        body = {"systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"inlineData": {"mimeType": "audio/wav", "data": audio}}]}],
                "generationConfig": gen}
        url = f"{s.gemini_base_url.rstrip('/')}/models/{use_model}:generateContent"
        try:
            r = _http().post(url, headers=_headers(), json=body,
                             timeout=httpx.Timeout(s.gemini_timeout_seconds, connect=5.0))
        except (httpx.TimeoutException, httpx.TransportError):
            _mark_busy(use_model, s.gemini_model_cooldown_seconds)
            last_err = LLMError("The Gemini API took too long to transcribe the recording.", kind="timeout",
                                status_code=504)
            continue
        if r.status_code in _RETRY_STATUS or r.status_code == 404:
            _mark_busy(use_model, s.gemini_model_cooldown_seconds)
            last_err = _api_error(r.status_code, r.text)
            continue
        if r.status_code != 200:
            raise _api_error(r.status_code, r.text)
        try:
            cand = (r.json().get("candidates") or [{}])[0]
            raw = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts") or []
                          if not p.get("thought"))
            return str(json.loads(raw).get("text", "")).strip() if raw.strip() else ""
        except (ValueError, AttributeError):
            raise LLMError("The Gemini API returned an unreadable transcription.", kind="bad_output")
    raise last_err or LLMError("Gemini could not transcribe the recording.", kind="http_error")
