"""Tests for EmojiGateMiddleware's emoji-free technical output enforcement."""

import asyncio
from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.emoji_gate_middleware import EmojiGateMiddleware
from deerflow.config.emoji_gate_config import EmojiGateConfig


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _run(messages: list, config: EmojiGateConfig | None = None) -> ModelRequest:
    middleware = EmojiGateMiddleware(emoji_gate_config=config or EmojiGateConfig())
    return middleware.wrap_model_call(_request(messages), lambda req: req)


def _injected(result: ModelRequest) -> list[HumanMessage]:
    return [
        msg
        for msg in result.messages
        if isinstance(msg, HumanMessage) and "EMOJI GATE REMINDER" in str(msg.content)
    ]


def _pending_emoji_write(call_id: str = "call-1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "write_file",
                "args": {"path": "notes.md", "content": "# Notes\n- do the thing \U0001f680 now"},
                "id": call_id,
            }
        ],
    )


def _clean_write(call_id: str = "call-1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {"name": "write_file", "args": {"path": "notes.md", "content": "# Notes\n- do the thing now"}, "id": call_id}
        ],
    )


# ── Silence ──


def test_no_messages_passes_through() -> None:
    result = _run([HumanMessage(content="hello there")])
    assert _injected(result) == []


def test_disabled_config_stays_silent() -> None:
    config = EmojiGateConfig(enabled=False)
    result = _run([_pending_emoji_write()], config=config)
    assert _injected(result) == []


def test_chat_emojis_allowed_by_default() -> None:
    result = _run([HumanMessage(content="hi"), AIMessage(content="Hey! \U0001f44b How can I help?")])
    assert _injected(result) == []


# ── Gate A: pending emoji write ──


def test_pending_emoji_write_gets_strip_nudge() -> None:
    result = _run([_pending_emoji_write()])
    nudges = _injected(result)
    assert len(nudges) == 1
    assert "Strip all emojis" in str(nudges[0].content)


def test_clean_write_passes_through() -> None:
    result = _run([_clean_write()])
    assert _injected(result) == []


def test_completed_emoji_write_does_not_trigger_gate_a() -> None:
    messages = [
        _pending_emoji_write(),
        ToolMessage(content="OK", name="write_file", tool_call_id="call-1"),
    ]
    # Write already executed: falls to Gate B only if code fences carry emoji.
    assert _injected(_run(messages)) == []


def test_str_replace_with_emoji_also_gated() -> None:
    call = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "str_replace",
                "args": {"path": "app.py", "old_str": "x", "new_str": "print('ok') \u2b50"},
                "id": "call-sr",
            }
        ],
    )
    nudges = _injected(_run([call]))
    assert len(nudges) == 1


# ── Gate B: emojis in code blocks ──


def test_emoji_in_code_block_gets_reemit_nudge() -> None:
    ai = AIMessage(content="Here is the fix:\n```python\nprint('hi')  # \U0001f680 launch\n```")
    nudges = _injected(_run([HumanMessage(content="show me the code"), ai]))
    assert len(nudges) == 1
    assert "Re-emit" in str(nudges[0].content)


def test_clean_code_block_passes_through() -> None:
    ai = AIMessage(content="Here is the fix:\n```python\nprint('hi')\n```")
    assert _injected(_run([HumanMessage(content="show me the code"), ai])) == []


def test_emoji_outside_code_block_allowed_by_default() -> None:
    ai = AIMessage(content="Sure thing! \U0001f600 The code is below:\n```python\nprint('hi')\n```")
    assert _injected(_run([HumanMessage(content="show me the code"), ai])) == []


# ── Gate C: strict mode ──


def test_strict_mode_gates_all_emoji_chat() -> None:
    config = EmojiGateConfig(allow_in_chat=False)
    ai = AIMessage(content="Hey! \U0001f44b How can I help?")
    nudges = _injected(_run([HumanMessage(content="hi"), ai], config=config))
    assert len(nudges) == 1
    assert "disabled in all output" in str(nudges[0].content)


# ── Re-arm and lifecycle ──


def test_new_user_message_ends_obligation() -> None:
    ai = AIMessage(content="```python\nprint('hi')  # \U0001f680\n```")
    messages = [HumanMessage(content="show me the code"), ai, HumanMessage(content="ok next task")]
    assert _injected(_run(messages)) == []


def test_awrap_model_call_injects_nudge() -> None:
    middleware = EmojiGateMiddleware(emoji_gate_config=EmojiGateConfig())

    async def handler(req: ModelRequest) -> ModelRequest:
        return req

    result = asyncio.run(middleware.awrap_model_call(_request([_pending_emoji_write()]), handler))
    assert len(_injected(result)) == 1


def test_config_defaults() -> None:
    config = EmojiGateConfig()
    assert config.enabled is True
    assert config.allow_in_chat is True
