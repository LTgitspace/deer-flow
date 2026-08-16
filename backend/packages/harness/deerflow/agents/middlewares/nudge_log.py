"""Nudge capture: per-thread ring buffer of gate triggers.

Every deterministic gate logs its triggers as ``logger.info("<Name> trigger:
<text>")``. A single logging handler installed by this module matches those
records, resolves the current thread id from the LangGraph config contextvar,
and appends to a bounded per-thread deque. Zero per-middleware changes.

Read by the gateway's nudge endpoint so the frontend can show *why* the
agent behaved the way it did — which gate fired, when, and what it said.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Any

_NUDGE_TRIGGER_MARKER = " trigger: "
_MAX_ENTRIES_PER_THREAD = 100
_MAX_THREADS = 256

_lock = threading.Lock()
_threads: collections.OrderedDict[str, collections.deque] = collections.OrderedDict()


class _NudgeCaptureHandler(logging.Handler):
    """Match gate-trigger log records and buffer them per thread."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
            if _NUDGE_TRIGGER_MARKER not in message:
                return
            middleware, _, text = message.partition(_NUDGE_TRIGGER_MARKER)
            middleware = middleware.strip()
            text = text.strip()
            if not middleware or not text:
                return
            thread_id = _resolve_thread_id() or "unknown"
            _record(thread_id, middleware, text, record.levelno)
        except Exception:
            # Observation-only: never let capture failures touch the run.
            return


def _resolve_thread_id() -> str | None:
    try:
        from langgraph.config import get_config

        config = get_config()
        configurable = config.get("configurable") if isinstance(config, dict) else None
        thread_id = configurable.get("thread_id") if isinstance(configurable, dict) else None
        return str(thread_id) if thread_id else None
    except Exception:
        return None


def _record(thread_id: str, middleware: str, text: str, level: int) -> None:
    with _lock:
        if thread_id not in _threads:
            while len(_threads) >= _MAX_THREADS:
                _threads.popitem(last=False)
            _threads[thread_id] = collections.deque(maxlen=_MAX_ENTRIES_PER_THREAD)
        _threads[thread_id].append(
            {
                "thread_id": thread_id,
                "middleware": middleware,
                "text": text[:500],
                "level": logging.getLevelName(level),
                "ts": time.time(),
            }
        )


def recent_nudges(thread_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent nudges for a thread (newest last)."""
    with _lock:
        entries = _threads.get(thread_id)
        if not entries:
            return []
        return list(entries)[-limit:]


def install_nudge_capture(level: int = logging.INFO) -> logging.Handler:
    """Install the capture handler on the root logger. Idempotent."""
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, _NudgeCaptureHandler):
            return handler
    handler = _NudgeCaptureHandler(level=level)
    root.addHandler(handler)
    return handler
