"""Tests for MetacognitionMiddleware's deterministic think-first gate."""

import asyncio
from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.metacognition_middleware import MetacognitionMiddleware
from deerflow.config.metacognition_config import MetacognitionConfig


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _run(messages: list, config: MetacognitionConfig | None = None) -> ModelRequest:
    middleware = MetacognitionMiddleware(metacognition_config=config or MetacognitionConfig())
    return middleware.wrap_model_call(_request(messages), lambda req: req)


def _injected_nudges(result: ModelRequest) -> list[HumanMessage]:
    """Extract hidden nudge messages injected by the middleware."""
    nudges: list[HumanMessage] = []
    for message in result.messages:
        if not isinstance(message, HumanMessage):
            continue
        additional_kwargs = message.additional_kwargs or {}
        if additional_kwargs.get("hide_from_ui") and not additional_kwargs.get("slash_skill_activation"):
            nudges.append(message)
    return nudges


def _complex_prompt() -> HumanMessage:
    return HumanMessage(
        content=(
            "Can you analyze the tradeoffs between SQLite and PostgreSQL for a "
            "multi-user note sync system and explain which one I should pick and "
            "why, including backup considerations?"
        )
    )


def _long_flat_prompt() -> HumanMessage:
    """Long (>= min_complexity_chars), no trigger words, no question mark."""
    return HumanMessage(
        content=(
            "I would like a walkthrough of how caching works in distributed systems "
            "and how invalidation strategies differ across read-heavy workloads and "
            "write-heavy workloads in practice."
        )
    )


# ── Gate A: pre-answer classification ──


def test_trivial_prompt_gets_no_nudge() -> None:
    result = _run([HumanMessage(content="hello there")])
    assert _injected_nudges(result) == []


def test_complex_by_length_gets_think_nudge() -> None:
    result = _run([_long_flat_prompt()])
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "METACOGNITION REMINDER" in content
    assert "step-by-step" in content


def test_question_mark_classifies_complex() -> None:
    result = _run([HumanMessage(content="Why does the sky appear blue?")])
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "METACOGNITION REMINDER" in str(nudges[0].content)


def test_trigger_word_classifies_complex() -> None:
    result = _run([HumanMessage(content="Can you analyze this dataset please")])
    nudges = _injected_nudges(result)
    assert len(nudges) == 1


def test_short_trigger_word_not_complex() -> None:
    result = _run([HumanMessage(content="analyze this")])
    assert _injected_nudges(result) == []


def test_multipart_shape_classifies_complex() -> None:
    result = _run([HumanMessage(content="Add user auth and add file uploads and add search")])
    nudges = _injected_nudges(result)
    assert len(nudges) == 1


def test_hidden_messages_ignored_for_classification() -> None:
    hidden = HumanMessage(content="a very long complex hidden message", additional_kwargs={"hide_from_ui": True})
    result = _run([hidden, HumanMessage(content="ok")])
    # The hidden fixture message must be the only hidden message: the
    # middleware itself injected nothing for the trivial visible prompt.
    assert len(result.messages) == 2


# ── Gate B: post-answer correction ──


def test_unreasoned_answer_to_complex_prompt_gets_reanswer_nudge() -> None:
    messages = [_complex_prompt(), AIMessage(content="SQLite.")]
    result = _run(messages)
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "Re-answer" in str(nudges[0].content)


def test_reasoning_content_kwarg_satisfies_gate() -> None:
    messages = [
        _complex_prompt(),
        AIMessage(content="SQLite.", additional_kwargs={"reasoning_content": "thinking about tradeoffs..."}),
    ]
    result = _run(messages)
    assert _injected_nudges(result) == []


def test_explicit_reasoning_markers_satisfy_gate() -> None:
    messages = [
        _complex_prompt(),
        AIMessage(content="Step 1: compare durability. Step 2: pick SQLite for single-box."),
    ]
    result = _run(messages)
    assert _injected_nudges(result) == []


def test_newer_user_message_ends_reanswer_obligation() -> None:
    messages = [_complex_prompt(), AIMessage(content="SQLite."), HumanMessage(content="ok thanks")]
    result = _run(messages)
    assert _injected_nudges(result) == []


def test_trivial_answer_not_flagged() -> None:
    messages = [HumanMessage(content="hi"), AIMessage(content="Hello!")]
    result = _run(messages)
    assert _injected_nudges(result) == []


# ── Configuration and lifecycle ──


def test_disabled_config_passes_through() -> None:
    config = MetacognitionConfig(enabled=False)
    result = _run([_complex_prompt()], config=config)
    assert _injected_nudges(result) == []


def test_awrap_model_call_injects_nudges() -> None:
    middleware = MetacognitionMiddleware(metacognition_config=MetacognitionConfig())

    async def handler(req: ModelRequest) -> ModelRequest:
        return req

    result = asyncio.run(middleware.awrap_model_call(_request([_complex_prompt()]), handler))
    assert len(_injected_nudges(result)) == 1


def test_config_defaults() -> None:
    config = MetacognitionConfig()
    assert config.enabled is True
    assert config.min_complexity_chars == 60
    assert config.min_trigger_chars == 30
    assert config.min_question_chars == 20
    assert "analyze" in config.triggers
    assert "build" in config.triggers
