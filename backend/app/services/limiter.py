"""Sliding-window counters for the login lockout, the password-reset limiter and the voice/monitoring rate limits.

Two backends with the same behaviour:
  memory - a dict of timestamp deques in this process (default). Resets when the server restarts and is not shared
           between workers, so run ONE API worker with it.
  redis  - used when REDIS_URL is set (and the `redis` package is installed). Every worker and every restart sees
           the same counters. One sorted set per key, members are timestamps; keys expire on their own.
If Redis is configured but unreachable, the memory backend is used and a warning is logged (once per minute), so a
Redis outage never locks everyone out or turns the limits off.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque

from ..config import get_settings

log = logging.getLogger("hiresense.limiter")

KEY_PREFIX = "hs:rl:"


class MemoryBackend:
    name = "memory"

    def __init__(self) -> None:
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque:
        q = self._hits.setdefault(key, deque())
        while q and now - q[0] > window:
            q.popleft()
        return q

    def count(self, key: str, window: float) -> int:
        with self._lock:
            n = len(self._prune(key, window, time.time()))
            if not n:
                self._hits.pop(key, None)
            return n

    def add(self, key: str, window: float) -> int:
        with self._lock:
            now = time.time()
            q = self._prune(key, window, now)
            q.append(now)
            if len(self._hits) > 20000:  # forget idle keys
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 3600]:
                    self._hits.pop(k, None)
            return len(q)

    def hit(self, key: str, limit: int, window: float) -> bool:
        with self._lock:
            now = time.time()
            q = self._prune(key, window, now)
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def clear(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class RedisBackend:
    name = "redis"

    def __init__(self, client) -> None:
        self.r = client

    def _k(self, key: str) -> str:
        return KEY_PREFIX + key

    def count(self, key: str, window: float) -> int:
        k, now = self._k(key), time.time()
        p = self.r.pipeline()
        p.zremrangebyscore(k, 0, now - window)
        p.zcard(k)
        return int(p.execute()[1])

    def add(self, key: str, window: float) -> int:
        k, now = self._k(key), time.time()
        p = self.r.pipeline()
        p.zremrangebyscore(k, 0, now - window)
        p.zadd(k, {f"{now:.6f}:{uuid.uuid4().hex[:8]}": now})
        p.zcard(k)
        p.expire(k, int(window) + 1)
        return int(p.execute()[2])

    def hit(self, key: str, limit: int, window: float) -> bool:
        # Add first, then undo if over the limit: two workers racing can't both slip past the limit.
        k, now = self._k(key), time.time()
        member = f"{now:.6f}:{uuid.uuid4().hex[:8]}"
        p = self.r.pipeline()
        p.zremrangebyscore(k, 0, now - window)
        p.zadd(k, {member: now})
        p.zcard(k)
        p.expire(k, int(window) + 1)
        n = int(p.execute()[2])
        if n > limit:
            self.r.zrem(k, member)
            return False
        return True

    def clear(self, key: str) -> None:
        self.r.delete(self._k(key))

    def reset(self) -> None:
        keys = list(self.r.scan_iter(match=KEY_PREFIX + "*"))
        if keys:
            self.r.delete(*keys)


_memory = MemoryBackend()
_redis: RedisBackend | None = None
_redis_url: str | None = None
_redis_down_until = 0.0
_init_lock = threading.Lock()


def _connect(url: str):
    import redis  # optional dependency (requirements-cloud.txt)
    return redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2, decode_responses=True)


def set_redis_client(client) -> None:
    """Use this client (tests pass a fakeredis instance); None goes back to REDIS_URL / memory."""
    global _redis, _redis_url, _redis_down_until
    with _init_lock:
        _redis = RedisBackend(client) if client is not None else None
        _redis_url = "<injected>" if client is not None else None
        _redis_down_until = 0.0


def backend():
    """The backend to use right now (Redis when configured and reachable, else memory)."""
    global _redis, _redis_url
    url = get_settings().redis_url.strip()
    if _redis is not None and (_redis_url == "<injected>" or _redis_url == url):
        pass
    elif url:
        with _init_lock:
            if _redis is None or _redis_url != url:
                try:
                    _redis, _redis_url = RedisBackend(_connect(url)), url
                except ImportError:
                    log.warning("REDIS_URL is set but the 'redis' package is not installed; using in-memory limits")
                    _redis, _redis_url = None, None
    if _redis is None or time.monotonic() < _redis_down_until:
        return _memory
    return _redis


def _run(op: str, *args):
    global _redis_down_until
    b = backend()
    try:
        return getattr(b, op)(*args)
    except Exception as exc:  # noqa: BLE001 - redis.ConnectionError, timeouts, ...
        if b is _memory:
            raise
        log.warning("Redis rate limiter unavailable (%s); using in-memory limits for 60 s", type(exc).__name__)
        _redis_down_until = time.monotonic() + 60
        return getattr(_memory, op)(*args)


def count(key: str, window: float) -> int:
    """Events recorded for `key` within the last `window` seconds."""
    return _run("count", key, window)


def add(key: str, window: float) -> int:
    """Record one event; returns the count including it."""
    return _run("add", key, window)


def hit(key: str, limit: int, window: float) -> bool:
    """Record one event if fewer than `limit` happened in the window. False (nothing recorded) when over."""
    return _run("hit", key, limit, window)


def clear(key: str) -> None:
    _run("clear", key)


def reset() -> None:
    """Forget every counter (tests)."""
    _memory.reset()
    if _redis is not None:
        try:
            _redis.reset()
        except Exception:  # noqa: BLE001
            pass


def status() -> dict:
    b = backend()
    return {"backend": b.name, "redis_configured": bool(get_settings().redis_url.strip())}
