"""Tests for TokenForensicsMiddleware's decomposition logging."""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.token_forensics_middleware import (
    TokenForensicsMiddleware,
    _compute_components,
    _content_text,
)
from deerflow.config.token_forensics_config import TokenForensicsConfig


def _state(messages: list) -> dict:
    return {"messages": messages}


# ── Component decomposition ──


def test_memory_injection_counted() -> None:
    memory = HumanMessage(
        content="<memory>\nUser Context: works on deer-flow and robotics.\n</memory>",
        additional_kwargs={"hide_from_ui": True},
    )
    messages = [memory, HumanMessage(content="hi")]
    components = _compute_components(messages)
    assert components["memory"] > 0
    assert components["history"] > 0


def test_date_reminder_lands_in_other() -> None:
    date_msg = HumanMessage(
        content="<system-reminder>\n<current_date>2026-08-16</current_date>\n</system-reminder>",
        additional_kwargs={"hide_from_ui": True},
    )
    messages = [date_msg, HumanMessage(content="hi")]
    components = _compute_components(messages)
    assert components["other"] > 0
    assert components["memory"] == 0


def test_tool_messages_counted_as_tools() -> None:
    messages = [
        HumanMessage(content="search for something"),
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {}, "id": "c1"}]),
        ToolMessage(content="result one result two", name="web_search", tool_call_id="c1"),
    ]
    components = _compute_components(messages)
    assert components["tools"] > 0


def test_hidden_total_tracks_all_hidden() -> None:
    memory = HumanMessage(
        content="<memory>\nfacts here\n</memory>",
        additional_kwargs={"hide_from_ui": True},
    )
    messages = [memory, HumanMessage(content="hi")]
    components = _compute_components(messages)
    assert components["hidden_total"] >= components["memory"]


def test_list_content_normalized() -> None:
    message = AIMessage(content=[{"type": "text", "text": "hello world"}])
    assert "hello world" in _content_text(message)


# ── Lifecycle gating ──


def test_no_usage_metadata_no_logging() -> None:
    middleware = TokenForensicsMiddleware(token_forensics_config=TokenForensicsConfig())
    messages = [HumanMessage(content="hi"), AIMessage(content="hey")]
    assert middleware._apply(_state(messages)) is None


def test_usage_metadata_triggers_logging(caplog) -> None:
    import logging

    middleware = TokenForensicsMiddleware(token_forensics_config=TokenForensicsConfig())
    ai = AIMessage(
        content="hey",
        usage_metadata={"input_tokens": 1200, "output_tokens": 30, "total_tokens": 1230, "input_token_details": {"cache_read": 0}},
    )
    messages = [HumanMessage(content="hi"), ai]
    with caplog.at_level(logging.INFO, logger="deerflow.agents.middlewares.token_forensics_middleware"):
        result = middleware._apply(_state(messages))
    assert result is None
    assert any("Token forensics" in record.message for record in caplog.records)


def test_high_input_logs_at_warning(caplog) -> None:
    import logging

    middleware = TokenForensicsMiddleware(token_forensics_config=TokenForensicsConfig(warn_input_tokens=1000))
    ai = AIMessage(
        content="hey",
        usage_metadata={"input_tokens": 28085, "output_tokens": 33, "total_tokens": 28118, "input_token_details": {"cache_read": 0}},
    )
    messages = [HumanMessage(content="hi"), ai]
    with caplog.at_level(logging.WARNING, logger="deerflow.agents.middlewares.token_forensics_middleware"):
        middleware._apply(_state(messages))
    assert any(record.levelno >= logging.WARNING and "Token forensics" in record.message for record in caplog.records)


def test_disabled_config_no_logging(caplog) -> None:
    import logging

    middleware = TokenForensicsMiddleware(token_forensics_config=TokenForensicsConfig(enabled=False))
    ai = AIMessage(content="hey", usage_metadata={"input_tokens": 1200, "output_tokens": 30, "total_tokens": 1230})
    with caplog.at_level(logging.INFO):
        middleware._apply(_state([HumanMessage(content="hi"), ai]))
    assert not any("Token forensics" in record.message for record in caplog.records)


def test_config_defaults() -> None:
    config = TokenForensicsConfig()
    assert config.enabled is True
    assert config.warn_input_tokens == 15000


def test_after_model_returns_none_never_writes_state() -> None:
    middleware = TokenForensicsMiddleware(token_forensics_config=TokenForensicsConfig())
    ai = AIMessage(content="hey", usage_metadata={"input_tokens": 10, "output_tokens": 2, "total_tokens": 12})
    state = {"messages": [HumanMessage(content="hi"), ai]}
    assert middleware.after_model(state, Runtime(context={})) is None
