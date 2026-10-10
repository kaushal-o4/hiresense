"""Client for the local language model (Ollama).

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


class PriorityGate:
    """At most `slots` generations at a time. Interactive requests are served before background ones, and
    `interactive_waiting()` lets a running background generation give way (it is cancelled and retried)."""

    def __init__(self, slots: int):
        self.slots = max(1, slots)
        self.running = 0
        self.waiting_interactive = 0
        self.cond = threading.Condition()

    def acquire(self, interactive: bool, timeout: float) -> bool:
        end = time.monotonic() + timeout
        with self.cond:
            if interactive:
                self.waiting_interactive += 1
            try:
                while self.running >= self.slots or (not interactive and self.waiting_interactive):
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
        return self.waiting_interactive > 0


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


def runtime_status(force: bool = False) -> dict:
    """{"provider", "model", "running", "model_ready", "error"} - cheap enough to call on every page load."""
    s = get_settings()
    base = {"provider": s.local_ai_provider, "model": s.ollama_model}
    if s.local_ai_provider.lower() != "ollama":
        return {**base, "running": False, "model_ready": False, "error": "No local AI provider is configured."}
    with _status_lock:
        cached = _status_cache["value"]
        if cached and not force and time.monotonic() - _status_cache["at"] < _STATUS_TTL:
            return cached
    try:
        r = httpx.get(f"{s.ollama_base_url.rstrip('/')}/api/tags", timeout=2.0)
        r.raise_for_status()
        names = [m.get("name") or m.get("model") or "" for m in r.json().get("models", [])]
        ready = any(_model_matches(s.ollama_model, n) for n in names)
        value = {**base, "running": True, "model_ready": ready,
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


def _options(s, max_tokens: int | None, temperature: float | None) -> dict:
    # num_ctx must be the same for every request (and the warm-up), otherwise Ollama reloads the model.
    return {"temperature": s.ai_temperature if temperature is None else temperature,
            "num_predict": min(max_tokens or s.ai_max_output_tokens, s.ai_max_output_tokens),
            "num_ctx": s.ollama_num_ctx}


def chat_json(system: str, prompt: str, schema: dict, *, max_tokens: int | None = None,
              temperature: float | None = None, priority: str = "interactive",
              on_delta: Callable[[str], None] | None = None) -> LLMResult:
    """Ask the local model for JSON matching `schema`. Raises LLMError on any failure.

    priority: "interactive" (a person is waiting) or "background" (may be cancelled with kind="preempted" when an
    interactive request arrives). on_delta(text_so_far) is called as the reply is generated."""
    s = get_settings()
    status = runtime_status()
    if not status["running"]:
        raise LLMError(status["error"], kind="not_running")
    if not status["model_ready"]:
        raise LLMError(status["error"], kind="model_missing")

    payload = {
        "model": s.ollama_model,
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
        raise LLMError("The local AI is busy with other requests. Please try again in a minute.",
                       kind="timeout", status_code=429)
    started = time.monotonic()
    parts: list[str] = []
    final: dict | None = None
    first_token: float | None = None
    try:
        for attempt in (1, 2):
            with httpx.stream("POST", f"{s.ollama_base_url.rstrip('/')}/api/chat", json=payload,
                              timeout=httpx.Timeout(s.ai_timeout_seconds, connect=5.0)) as r:
                if r.status_code != 200:
                    body = r.read().decode("utf-8", "replace")
                    # Ollama's model runner occasionally crashes while (re)loading the model onto the GPU (seen on
                    # the test laptop as a CUDA init error, exit 0xc0000409). A second attempt reloads it.
                    if r.status_code == 500 and "process has terminated" in body and attempt == 1:
                        log.warning("ollama runner crashed while loading; retrying once")
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
                     timings=timings)


def warmup() -> dict:
    """Load the model into memory ahead of time (an empty request), so the first question doesn't pay the
    30-70 s load. Uses the same num_ctx as real requests. Safe to call often: cheap when already loaded."""
    s = get_settings()
    if not s.ai_enabled or s.local_ai_provider.lower() != "ollama":
        return {"ok": False, "reason": "AI disabled"}
    base = s.ollama_base_url.rstrip("/")
    try:
        loaded = httpx.get(f"{base}/api/ps", timeout=2.0).json().get("models", [])
        if any(_model_matches(s.ollama_model, m.get("name") or m.get("model") or "") for m in loaded):
            return {"ok": True, "already_loaded": True, "load_ms": 0}
        t = time.monotonic()
        r = httpx.post(f"{base}/api/generate", json={"model": s.ollama_model, "keep_alive": s.ollama_keep_alive,
                                                     "options": {"num_ctx": s.ollama_num_ctx}},
                       timeout=httpx.Timeout(s.ai_timeout_seconds, connect=3.0))
        return {"ok": r.status_code == 200, "already_loaded": False, "load_ms": round((time.monotonic() - t) * 1000)}
    except (httpx.HTTPError, ValueError) as exc:
        return {"ok": False, "reason": type(exc).__name__}
