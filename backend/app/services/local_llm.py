"""Client for the language model: local Ollama, or Google Gemini via services/gemini_llm.py.

Ollama runs the model as a separate process on this computer and keeps it loaded in memory between
requests (`keep_alive`), so nothing here loads model weights. This module only:
  * checks whether Ollama is running and the configured model has been downloaded (cached briefly),
  * sends one chat request with a JSON schema so the model must reply with matching JSON,
  * limits concurrent generations, input size and output length, and applies a timeout.

It never logs prompt or response text, because those contain resumes and interview answers.

Latency (measured on the test laptop, see tests_perf/): generating output tokens is the bottleneck (~17-25 tokens/s
with qwen3:4b split between a 4 GB GPU and the CPU); reading the prompt takes 0.1-0.5 s. So:
  * interactive requests (the candidate is waiting) go before background ones (detailed feedback), and a running
    background generation is cancelled when an interactive request arrives, then retried later;
  * `chat_json_stream` hands out the reply as it is generated, so speech can start at the first sentence.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable

import httpx

from ..config import get_settings

log = logging.getLogger("hiresense.local_llm")


class LLMError(Exception):
    """The local model could not produce a response. `message` is safe to show to users."""

    def __init__(self, message: str, *, kind: str, status_code: int = 503):
        super().__init__(message)
        self.message = message
        self.kind = kind  # not_running | model_missing | timeout | http_error | bad_output | disabled | preempted
        self.status_code = status_code


@dataclass
class LLMResult:
    content: str
    prompt_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    # Ollama's own split (ms): queue (waiting for a free slot), load, prompt, generation, first token
    timings: dict = field(default_factory=dict)


_status_cache: dict = {"at": 0.0, "value": None}
_status_lock = threading.Lock()
_STATUS_TTL = 20.0  # seconds

_client: httpx.Client | None = None
_client_lock = threading.Lock()


def _base_url() -> str:
    """Ollama's URL with "localhost" replaced by 127.0.0.1. Measured on the test laptop (Windows): "localhost"
    resolves to IPv6 ::1 first, Ollama listens on IPv4 only, and every new connection waited ~2.1 s before
    falling back - on every AI request."""
    url = get_settings().ollama_base_url.rstrip("/")
    return re.sub(r"^(https?://)localhost(?=[:/]|$)", r"\g<1>127.0.0.1", url)


def _http() -> httpx.Client:
    """One shared client: keeps the connection to Ollama open between requests (no new TCP setup per call)."""
    global _client
    with _client_lock:
        if _client is None:
            _client = httpx.Client(timeout=httpx.Timeout(get_settings().ai_timeout_seconds, connect=5.0),
                                   limits=httpx.Limits(max_keepalive_connections=4, keepalive_expiry=120))
        return _client


class PriorityGate:
    """At most `slots` generations at a time. Interactive requests are served before background ones, and
    `interactive_waiting()` lets a running background generation give way (it is cancelled and retried).

    `holds` counts candidate-facing work that is not an LLM call but shares the CPU (speech synthesis and
    transcription during a turn). Measured in the browser E2E: a background feedback generation running next to
    Kokoro made one spoken sentence take 122 s instead of ~1 s. While a hold is active, background generations
    neither start nor continue."""

    def __init__(self, slots: int):
        self.slots = max(1, slots)
        self.running = 0
        self.waiting_interactive = 0
        self.holds = 0
        self.cond = threading.Condition()

    def acquire(self, interactive: bool, timeout: float) -> bool:
        end = time.monotonic() + timeout
        with self.cond:
            if interactive:
                self.waiting_interactive += 1
            try:
                while self.running >= self.slots or (not interactive and (self.waiting_interactive or self.holds)):
                    left = end - time.monotonic()
                    if left <= 0:
                        return False
                    self.cond.wait(left)
                self.running += 1
                return True
            finally:
                if interactive:
                    self.waiting_interactive -= 1

    def release(self) -> None:
        with self.cond:
            self.running -= 1
            self.cond.notify_all()

    def interactive_waiting(self) -> bool:
        return self.waiting_interactive > 0 or self.holds > 0

    def hold(self, delta: int) -> None:
        with self.cond:
            self.holds = max(0, self.holds + delta)
            self.cond.notify_all()


@contextmanager
def interactive_hold():
    """with interactive_hold(): ...  - a candidate is waiting on this work; background generations pause."""
    gate = _gate()
    gate.hold(+1)
    try:
        yield
    finally:
        gate.hold(-1)


_gate_obj: PriorityGate | None = None
_gate_lock = threading.Lock()


def _gate() -> PriorityGate:
    global _gate_obj
    with _gate_lock:
        if _gate_obj is None:
            _gate_obj = PriorityGate(get_settings().ai_max_concurrent)
        return _gate_obj


def _model_matches(wanted: str, available: str) -> bool:
    if ":" not in wanted:
        wanted += ":latest"
    return available == wanted


def provider() -> str:
    return get_settings().local_ai_provider.strip().lower()


def runtime_status(force: bool = False) -> dict:
    """{"provider", "model", "running", "model_ready", "error"} - cheap enough to call on every page load.

    With LOCAL_AI_PROVIDER=gemini this is Gemini's status; if Gemini can't be used and AI_FALLBACK_TO_OLLAMA is on,
    a ready Ollama is reported instead (with "fallback_for": "gemini" and Gemini's problem in "primary_error")."""
    s = get_settings()
    if provider() == "gemini":
        from . import gemini_llm
        st = gemini_llm.runtime_status(force)
        if st["running"] and st["model_ready"] or not s.ai_fallback_to_ollama:
            return st
        ol = _ollama_status(force)
        if ol["running"] and ol["model_ready"]:
            return {**ol, "fallback_for": "gemini", "primary_error": st["error"]}
        return st
    if provider() != "ollama":
        return {"provider": s.local_ai_provider, "model": s.ollama_model, "running": False, "model_ready": False,
                "error": "No AI provider is configured."}
    return _ollama_status(force)


def _ollama_status(force: bool = False) -> dict:
    s = get_settings()
    base = {"provider": "ollama", "model": s.ollama_model}
    with _status_lock:
        cached = _status_cache["value"]
        if cached and not force and time.monotonic() - _status_cache["at"] < _STATUS_TTL:
            return cached
    try:
        r = _http().get(f"{_base_url()}/api/tags", timeout=2.0)
        r.raise_for_status()
        names = [m.get("name") or m.get("model") or "" for m in r.json().get("models", [])]
        ready = any(_model_matches(s.ollama_model, n) for n in names)
        value = {**base, "running": True, "model_ready": ready, "installed": names,
                 "error": None if ready else f"The model '{s.ollama_model}' has not been downloaded. "
                                             f"Run: ollama pull {s.ollama_model}"}
    except (httpx.HTTPError, ValueError):
        value = {**base, "running": False, "model_ready": False,
                 "error": "Ollama is not running. Start the Ollama app (or run 'ollama serve') and try again."}
    with _status_lock:
        _status_cache.update(at=time.monotonic(), value=value)
    return value


def _strip_think(text: str) -> str:
    # Some reasoning models prepend <think>...</think> even when thinking is off.
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _http_error(status_code: int, body: str) -> LLMError:
    s = get_settings()
    detail = ""
    try:
        detail = str(json.loads(body).get("error", ""))[:300]
    except (ValueError, AttributeError):
        pass
    log.warning("ollama returned HTTP %s: %s", status_code, detail)
    if status_code == 404:
        _status_cache["at"] = 0.0
        return LLMError(f"The model '{s.ollama_model}' is not available in Ollama. "
                        f"Run: ollama pull {s.ollama_model}", kind="model_missing")
    return LLMError(f"The local AI returned an error ({status_code}). {detail}".strip(), kind="http_error")


_gpu_override_failed = False  # set when loading with OLLAMA_NUM_GPU failed: Ollama then places the layers itself


def _load_options(s) -> dict:
    """Options that decide how the model is loaded. They must be the same for every request (and the warm-up),
    otherwise Ollama reloads the model."""
    opts = {"num_ctx": s.ollama_num_ctx}
    if s.ollama_num_gpu >= 0 and not _gpu_override_failed:
        opts["num_gpu"] = s.ollama_num_gpu
    return opts


def _options(s, max_tokens: int | None, temperature: float | None) -> dict:
    return {"temperature": s.ai_temperature if temperature is None else temperature,
            "num_predict": min(max_tokens or s.ai_max_output_tokens, s.ai_max_output_tokens),
            **_load_options(s)}


_active_model: str | None = None


def _switch_model(model: str) -> None:
    """Unload the previously used model when a different one is requested (called while holding the gate).

    Measured on the test laptop (4 GB GPU): with the 4B and 1.7B models both resident, Ollama placed the second one
    on the CPU only ("100% CPU") and it generated at ~19 tokens/s instead of fitting on the GPU. Unloading first costs
    one model load (5-8 s) but lets the new model use the GPU. Best effort: a failure here never fails the request."""
    global _active_model
    previous, _active_model = _active_model, model
    if previous and previous != model:
        try:
            _http().post(f"{_base_url()}/api/generate", json={"model": previous, "keep_alive": 0}, timeout=15.0)
        except httpx.HTTPError:
            log.warning("could not unload model '%s' before switching to '%s'", previous, model)


def chat_json(system: str, prompt: str, schema: dict, *, max_tokens: int | None = None,
              temperature: float | None = None, priority: str = "interactive",
              on_delta: Callable[[str], None] | None = None, model: str | None = None) -> LLMResult:
    """Ask the language model for JSON matching `schema`. Raises LLMError on any failure.

    priority: "interactive" (a person is waiting) or "background" (may be cancelled with kind="preempted" when an
    interactive request arrives). on_delta(text_so_far) is called as the reply is generated.
    model: a tier model chosen by services/model_router.py; if it is not available, the main model is used instead.

    With LOCAL_AI_PROVIDER=gemini the request goes to Gemini; if that fails before any text was streamed and
    AI_FALLBACK_TO_OLLAMA is on, the same request is answered by the local Ollama model."""
    kw = dict(max_tokens=max_tokens, temperature=temperature, priority=priority, on_delta=on_delta)
    if provider() != "gemini":
        return _chat_ollama(system, prompt, schema, model=model, status=runtime_status(), **kw)
    global _gemini_down_until
    from . import gemini_llm
    s = get_settings()
    if s.ai_fallback_to_ollama and time.monotonic() < _gemini_down_until:
        status = _ollama_status()
        if status["running"] and status["model_ready"]:
            return _chat_ollama(system, prompt, schema, model=None, status=status, **kw)
    streamed = False

    def track(text: str) -> None:
        nonlocal streamed
        streamed = True
        if on_delta:
            on_delta(text)

    try:
        # only stream through when the caller streams: lets gemini_llm switch models on cut-off JSON otherwise
        return gemini_llm.chat_json(system, prompt, schema, model=model, **{**kw, "on_delta": track if on_delta else None})
    except LLMError as exc:
        if exc.kind in ("timeout", "not_running", "http_error", "model_missing"):
            _gemini_down_until = time.monotonic() + s.gemini_cooldown_seconds
        if streamed or not s.ai_fallback_to_ollama:
            raise
        status = _ollama_status()
        if not (status["running"] and status["model_ready"]):
            raise
        log.warning("gemini failed (%s); answering with ollama", exc.kind)
        return _chat_ollama(system, prompt, schema, model=None, status=status, **kw)


_gemini_down_until = 0.0  # monotonic time until which Gemini is skipped (see GEMINI_COOLDOWN_SECONDS)


def _chat_ollama(system: str, prompt: str, schema: dict, *, max_tokens: int | None, temperature: float | None,
                 priority: str, on_delta: Callable[[str], None] | None, model: str | None,
                 status: dict) -> LLMResult:
    global _gpu_override_failed
    s = get_settings()
    if not status["running"]:
        raise LLMError(status["error"], kind="not_running")
    if not status["model_ready"]:
        raise LLMError(status["error"], kind="model_missing")
    use_model = s.ollama_model
    if model and model != s.ollama_model:
        if any(_model_matches(model, n) for n in status.get("installed", [])):
            use_model = model
        else:
            log.warning("routed model '%s' is not downloaded; using '%s'", model, s.ollama_model)

    payload = {
        "model": use_model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        "format": schema,
        "stream": True,
        "think": False,
        "keep_alive": s.ollama_keep_alive,
        "options": _options(s, max_tokens, temperature),
    }
    interactive = priority != "background"
    gate = _gate()
    queued = time.monotonic()
    if not gate.acquire(interactive, timeout=s.ai_timeout_seconds):
        # A background job that waited this long is simply retried later (candidates kept the model busy).
        raise LLMError("The local AI is busy with other requests. Please try again in a minute.",
                       kind="timeout" if interactive else "preempted", status_code=429)
    try:
        _switch_model(use_model)
    except BaseException:
        gate.release()
        raise
    started = time.monotonic()
    parts: list[str] = []
    final: dict | None = None
    first_token: float | None = None
    try:
        for attempt in (1, 2):
            with _http().stream("POST", f"{_base_url()}/api/chat", json=payload,
                              timeout=httpx.Timeout(s.ai_timeout_seconds, connect=5.0)) as r:
                if r.status_code != 200:
                    body = r.read().decode("utf-8", "replace")
                    # Ollama's model runner occasionally crashes while (re)loading the model onto the GPU (seen on
                    # the test laptop as a CUDA init error, exit 0xc0000409). A second attempt reloads it.
                    if r.status_code == 500 and "process has terminated" in body and attempt == 1:
                        log.warning("ollama runner crashed while loading; retrying once")
                        continue
                    # All layers on the GPU did not fit (e.g. another program holds VRAM): let Ollama choose.
                    if r.status_code == 500 and attempt == 1 and "num_gpu" in payload["options"]:
                        _gpu_override_failed = True
                        log.warning("loading with num_gpu=%s failed; letting Ollama place the layers",
                                    s.ollama_num_gpu)
                        payload["options"] = {k: v for k, v in payload["options"].items() if k != "num_gpu"}
                        continue
                    raise _http_error(r.status_code, body)
                for line in r.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except ValueError:
                        raise LLMError("The local AI returned an unreadable response.", kind="bad_output")
                    if chunk.get("error"):
                        raise LLMError(f"The local AI returned an error. {str(chunk['error'])[:300]}",
                                       kind="http_error")
                    piece = (chunk.get("message") or {}).get("content") or ""
                    if piece:
                        if first_token is None:
                            first_token = time.monotonic()
                        parts.append(piece)
                        if on_delta:
                            on_delta("".join(parts))
                    if chunk.get("done"):
                        final = chunk
                        break
                    if not interactive and gate.interactive_waiting():
                        # Closing the connection makes Ollama stop generating; the caller retries later.
                        raise LLMError("Paused for an interactive request.", kind="preempted")
            break
    except httpx.TimeoutException:
        raise LLMError("The local AI model took too long to respond. Try again, or use a smaller model "
                       "(see README).", kind="timeout", status_code=504)
    except httpx.HTTPError:
        _status_cache["at"] = 0.0
        raise LLMError("Could not connect to Ollama. Make sure it is running.", kind="not_running")
    finally:
        gate.release()
    done_at = time.monotonic()
    if final is None:
        raise LLMError("The local AI stopped before finishing its answer.", kind="bad_output")
    content = _strip_think("".join(parts))
    if final.get("done_reason") == "length":
        raise LLMError("The local AI's answer was cut off (output limit reached). Please try again.",
                       kind="bad_output")
    ns = 1_000_000
    timings = {"queue_ms": round((started - queued) * 1000),
               "load_ms": round((final.get("load_duration") or 0) / ns),
               "prompt_ms": round((final.get("prompt_eval_duration") or 0) / ns),
               "generate_ms": round((final.get("eval_duration") or 0) / ns),
               "first_token_ms": round(((first_token or done_at) - started) * 1000)}
    return LLMResult(content=content, prompt_tokens=final.get("prompt_eval_count"),
                     output_tokens=final.get("eval_count"), latency_ms=int((done_at - started) * 1000),
                     timings={**timings, "model": use_model})


def warmup() -> dict:
    """Load the model into memory ahead of time (an empty request), so the first question doesn't pay the
    30-70 s load. Uses the same load options as real requests. Safe to call often: cheap when already loaded."""
    s = get_settings()
    if not s.ai_enabled or provider() not in ("ollama", "gemini"):
        return {"ok": False, "reason": "AI disabled"}
    if provider() == "gemini":
        from . import gemini_llm
        r = gemini_llm.warmup()
        # Only load the local model when it will actually be used (Gemini can't be reached / has no key).
        if r["ok"] or not s.ai_fallback_to_ollama:
            return r
    base = _base_url()
    try:
        loaded = _http().get(f"{base}/api/ps", timeout=2.0).json().get("models", [])
        # loaded with other settings (e.g. an older num_ctx) counts as not loaded: the first question would reload it
        if any(_model_matches(s.ollama_model, m.get("name") or m.get("model") or "")
               and m.get("context_length", s.ollama_num_ctx) == s.ollama_num_ctx for m in loaded):
            global _active_model
            _active_model = _active_model or s.ollama_model
            return {"ok": True, "already_loaded": True, "load_ms": 0}
        t = time.monotonic()
        r = _http().post(f"{base}/api/generate", json={"model": s.ollama_model, "keep_alive": s.ollama_keep_alive,
                                                     "options": _load_options(s)},
                       timeout=httpx.Timeout(s.ai_timeout_seconds, connect=3.0))
        return {"ok": r.status_code == 200, "already_loaded": False, "load_ms": round((time.monotonic() - t) * 1000)}
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "reason": type(exc).__name__}
