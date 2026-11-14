# HIRESENSE COMMENT INDEX - START
# ------------------------------------------------------------
# FILE NAME:
# backend/app/services/platform_support/background_jobs.py
#
# FILE PURPOSE:
# Runs background jobs (feedback, question prefetch, emails) in tracked threads and lets them finish
# on shutdown.
#
# WHAT THIS FILE DOES:
# 1. spawn(): start a tracked daemon thread.
# 2. drain(): wait for running jobs at shutdown.
#
# IMPORTANT FUNCTIONS:
#    - spawn()
#        Start `target(*args)` in a tracked daemon thread.
#    - drain()
#        Signal shutdown and wait up to `timeout` seconds for the running jobs.
#    - started()
#        Called at startup (a test client starts and stops the app many times in one process).
#    Other helper functions: stopping, running
#
# INPUT:
# Functions to run.
#
# OUTPUT:
# Running threads.
#
# FILES CONNECTED TO THIS FILE:
#    Used by: app/main.py, app/routers/english_practice_routes.py, app/routers/interview_routes.py,
#    app/routers/live_voice_interview_routes.py, app/services/platform_support/email_sender.py
#    Tested by: tests/conftest.py, tests/test_deploy.py
#
# EXECUTION FLOW:
#    spawn()
#       |
#       v
#    Job runs
#       |
#       v
#    drain() at shutdown
#
# ------------------------------------------------------------
# HIRESENSE COMMENT INDEX - END

"""Background jobs (answer feedback, question prefetch, streamed replies, emails) with a graceful shutdown.

Every job runs in its own daemon thread, as before, but is registered here, so that when the server is asked to stop
(SIGTERM from Docker/Render, Ctrl+C) `drain()` waits up to SHUTDOWN_GRACE_SECONDS for running jobs to finish their
database writes. Jobs started after shutdown began still run (a request already accepted is not dropped) but the
wait does not grow past the deadline. Jobs that want to stop early can check `stopping()`.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

log = logging.getLogger("hiresense.background")

_threads: set[threading.Thread] = set()
_lock = threading.Lock()
_stopping = threading.Event()


def spawn(target: Callable, *args, name: str | None = None) -> threading.Thread:
    """Start `target(*args)` in a tracked daemon thread."""
    def run():
        try:
            target(*args)
        finally:
            with _lock:
                _threads.discard(threading.current_thread())

    t = threading.Thread(target=run, daemon=True, name=name)
    with _lock:
        _threads.add(t)
    t.start()
    return t


def stopping() -> bool:
    return _stopping.is_set()


def running() -> int:
    with _lock:
        return sum(1 for t in _threads if t.is_alive())


def drain(timeout: float) -> int:
    """Signal shutdown and wait up to `timeout` seconds for the running jobs. Returns how many were still running."""
    _stopping.set()
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        with _lock:
            alive = [t for t in _threads if t.is_alive()]
        if not alive:
            return 0
        left = deadline - time.monotonic()
        if left <= 0:
            log.warning("shutdown: %d background job(s) still running after %.0f s: %s", len(alive), timeout,
                        ", ".join(t.name or "?" for t in alive[:10]))
            return len(alive)
        alive[0].join(min(left, 0.5))


def started() -> None:
    """Called at startup (a test client starts and stops the app many times in one process)."""
    _stopping.clear()
