"""Tests for the nudge capture ring buffer."""

import logging

from deerflow.agents.middlewares import nudge_log
from deerflow.agents.middlewares.nudge_log import (
    _NUDGE_TRIGGER_MARKER,
    _NudgeCaptureHandler,
    _record,
    install_nudge_capture,
    recent_nudges,
)


def test_record_and_recent(tmp_path, monkeypatch):
    nudge_log._threads.clear()
    _record("thread-a", "PlannerMiddleware", "plan first please", logging.INFO)
    _record("thread-a", "EmojiGateMiddleware", "strip emojis", logging.WARNING)
    _record("thread-b", "PushbackMiddleware", "state tradeoff", logging.INFO)

    entries = recent_nudges("thread-a")
    assert [e["middleware"] for e in entries] == ["PlannerMiddleware", "EmojiGateMiddleware"]
    assert entries[1]["level"] == "WARNING"
    assert recent_nudges("missing") == []


def test_limit_respected():
    nudge_log._threads.clear()
    for i in range(5):
        _record("t", "M", f"nudge {i}", logging.INFO)
    entries = recent_nudges("t", limit=2)
    assert len(entries) == 2
    assert entries[-1]["text"] == "nudge 4"


def test_handler_matches_trigger_records(caplog, monkeypatch):
    nudge_log._threads.clear()

    class _Config(dict):
        def get(self, key, default=None):
            return {"configurable": {"thread_id": "cfg-thread"}}.get(key, default)

    monkeypatch.setattr(nudge_log, "_resolve_thread_id", lambda: "cfg-thread")
    handler = _NudgeCaptureHandler()
    record = logging.LogRecord(
        name="deerflow.agents.middlewares.planner_middleware",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="PlannerMiddleware" + _NUDGE_TRIGGER_MARKER + "plan first please",
        args=(),
        exc_info=None,
    )
    handler.emit(record)
    assert recent_nudges("cfg-thread")[-1]["middleware"] == "PlannerMiddleware"


def test_handler_ignores_non_trigger_records():
    nudge_log._threads.clear()
    handler = _NudgeCaptureHandler()
    record = logging.LogRecord(
        name="some.module",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="ordinary log line",
        args=(),
        exc_info=None,
    )
    handler.emit(record)
    assert recent_nudges("unknown") == []


def test_install_is_idempotent():
    first = install_nudge_capture()
    second = install_nudge_capture()
    assert first is second


def test_text_truncated_to_500_chars():
    nudge_log._threads.clear()
    _record("t", "M", "x" * 1000, logging.INFO)
    assert len(recent_nudges("t")[-1]["text"]) == 500
