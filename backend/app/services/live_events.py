"""In-process fan-out of "something changed" signals to the browser (Server-Sent Events).

Used by GET /api/notifications/stream. `publish()` can be called from any thread (sync endpoints run in a thread
pool, AI feedback runs in background threads); each subscriber is an asyncio queue on the event loop that serves
its stream, so delivery goes through `loop.call_soon_threadsafe`.

Signals carry no content: the browser re-fetches /api/notifications when it gets one, so the normal access checks
and serializers stay the single source of truth.

LIMIT: subscribers live in this process's memory. With more than one API worker/process a notification created in
worker A never reaches a stream held open by worker B. Those browsers still catch up (the client also re-fetches on
reconnect and every few minutes), but for multi-worker deployments replace this module's publish/subscribe with
Redis pub/sub or MongoDB change streams.
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager

MAX_STREAMS_PER_USER = 5  # a few tabs; more is a leak or abuse
QUEUE_SIZE = 32  # signals are idempotent "re-fetch" hints, so dropping extras when a queue is full is harmless

_lock = threading.Lock()
_subs: dict[int, list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}


class TooManyStreams(Exception):
    pass


def _put(q: asyncio.Queue, event: dict) -> None:
    try:
        q.put_nowait(event)
    except asyncio.QueueFull:
        pass


def publish(user_id: int, event: dict) -> int:
    """Send `event` to every open stream of `user_id`. Returns how many streams it was queued for."""
    with _lock:
        targets = list(_subs.get(user_id, ()))
    sent = 0
    for loop, q in targets:
        try:
            loop.call_soon_threadsafe(_put, q, event)
            sent += 1
        except RuntimeError:  # that stream's loop is closed (server shutting down)
            pass
    return sent


@contextmanager
def subscribe(user_id: int):
    """Register a queue for `user_id` on the running event loop; always unregistered on exit."""
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    entry = (loop, q)
    with _lock:
        lst = _subs.setdefault(user_id, [])
        if len(lst) >= MAX_STREAMS_PER_USER:
            raise TooManyStreams()
        lst.append(entry)
    try:
        yield q
    finally:
        with _lock:
            lst = _subs.get(user_id, [])
            if entry in lst:
                lst.remove(entry)
            if not lst:
                _subs.pop(user_id, None)


def stream_count(user_id: int | None = None) -> int:
    with _lock:
        if user_id is not None:
            return len(_subs.get(user_id, ()))
        return sum(len(v) for v in _subs.values())
