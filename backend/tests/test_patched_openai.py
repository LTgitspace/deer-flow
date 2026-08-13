"""Tests for deerflow.models.patched_openai.PatchedChatOpenAI.

These tests verify that _restore_tool_call_signatures correctly re-injects
``thought_signature`` onto tool-call objects stored in
``additional_kwargs["tool_calls"]``, covering id-based matching, positional
fallback, camelCase keys, and several edge-cases.
"""

from __future__ import annotations

import openai
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from deerflow.models.patched_openai import PatchedChatOpenAI, _restore_tool_call_signatures

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RAW_TC_SIGNED = {
    "id": "call_1",
    "type": "function",
    "function": {"name": "web_fetch", "arguments": '{"url":"http://example.com"}'},
    "thought_signature": "SIG_A==",
}

RAW_TC_UNSIGNED = {
    "id": "call_2",
    "type": "function",
    "function": {"name": "bash", "arguments": '{"cmd":"ls"}'},
}

PAYLOAD_TC_1 = {
    "type": "function",
    "id": "call_1",
    "function": {"name": "web_fetch", "arguments": '{"url":"http://example.com"}'},
}

PAYLOAD_TC_2 = {
    "type": "function",
    "id": "call_2",
    "function": {"name": "bash", "arguments": '{"cmd":"ls"}'},
}


def _ai_msg_with_raw_tool_calls(raw_tool_calls: list[dict]) -> AIMessage:
    return AIMessage(content="", additional_kwargs={"tool_calls": raw_tool_calls})


# ---------------------------------------------------------------------------
# Core: signed tool-call restoration
# ---------------------------------------------------------------------------


def test_tool_call_signature_restored_by_id():
    """thought_signature is copied to the payload tool-call matched by id."""
    payload_msg = {"role": "assistant", "content": None, "tool_calls": [PAYLOAD_TC_1.copy()]}
    orig = _ai_msg_with_raw_tool_calls([RAW_TC_SIGNED])

    _restore_tool_call_signatures(payload_msg, orig)

    assert payload_msg["tool_calls"][0]["thought_signature"] == "SIG_A=="


def test_tool_call_signature_for_parallel_calls():
    """For parallel function calls, only the first has a signature (per Gemini spec)."""
    payload_msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [PAYLOAD_TC_1.copy(), PAYLOAD_TC_2.copy()],
    }
    orig = _ai_msg_with_raw_tool_calls([RAW_TC_SIGNED, RAW_TC_UNSIGNED])

    _restore_tool_call_signatures(payload_msg, orig)

    assert payload_msg["tool_calls"][0]["thought_signature"] == "SIG_A=="
    assert "thought_signature" not in payload_msg["tool_calls"][1]


def test_tool_call_signature_camel_case():
    """thoughtSignature (camelCase) from some gateways is also handled."""
    raw_camel = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "web_fetch", "arguments": "{}"},
        "thoughtSignature": "SIG_CAMEL==",
    }
    payload_msg = {"role": "assistant", "content": None, "tool_calls": [PAYLOAD_TC_1.copy()]}
    orig = _ai_msg_with_raw_tool_calls([raw_camel])

    _restore_tool_call_signatures(payload_msg, orig)

    assert payload_msg["tool_calls"][0]["thought_signature"] == "SIG_CAMEL=="


def test_tool_call_signature_positional_fallback():
    """When ids don't match, falls back to positional matching."""
    raw_no_id = {
        "type": "function",
        "function": {"name": "web_fetch", "arguments": "{}"},
        "thought_signature": "SIG_POS==",
    }
    payload_tc = {
        "type": "function",
        "id": "call_99",
        "function": {"name": "web_fetch", "arguments": "{}"},
    }
    payload_msg = {"role": "assistant", "content": None, "tool_calls": [payload_tc]}
    orig = _ai_msg_with_raw_tool_calls([raw_no_id])

    _restore_tool_call_signatures(payload_msg, orig)

    assert payload_tc["thought_signature"] == "SIG_POS=="


# ---------------------------------------------------------------------------
# Edge cases: no-op scenarios for tool-call signatures
# ---------------------------------------------------------------------------


def test_tool_call_no_raw_tool_calls_is_noop():
    """No change when additional_kwargs has no tool_calls."""
    payload_msg = {"role": "assistant", "content": None, "tool_calls": [PAYLOAD_TC_1.copy()]}
    orig = AIMessage(content="", additional_kwargs={})

    _restore_tool_call_signatures(payload_msg, orig)

    assert "thought_signature" not in payload_msg["tool_calls"][0]


def test_tool_call_no_payload_tool_calls_is_noop():
    """No change when payload has no tool_calls."""
    payload_msg = {"role": "assistant", "content": "just text"}
    orig = _ai_msg_with_raw_tool_calls([RAW_TC_SIGNED])

    _restore_tool_call_signatures(payload_msg, orig)

    assert "tool_calls" not in payload_msg


def test_tool_call_unsigned_raw_entries_is_noop():
    """No signature added when raw tool-calls have no thought_signature."""
    payload_msg = {"role": "assistant", "content": None, "tool_calls": [PAYLOAD_TC_2.copy()]}
    orig = _ai_msg_with_raw_tool_calls([RAW_TC_UNSIGNED])

    _restore_tool_call_signatures(payload_msg, orig)

    assert "thought_signature" not in payload_msg["tool_calls"][0]


def test_tool_call_multiple_sequential_signatures():
    """Sequential tool calls each carry their own signature."""
    raw_tc_a = {
        "id": "call_a",
        "type": "function",
        "function": {"name": "check_flight", "arguments": "{}"},
        "thought_signature": "SIG_STEP1==",
    }
    raw_tc_b = {
        "id": "call_b",
        "type": "function",
        "function": {"name": "book_taxi", "arguments": "{}"},
        "thought_signature": "SIG_STEP2==",
    }
    payload_tc_a = {"type": "function", "id": "call_a", "function": {"name": "check_flight", "arguments": "{}"}}
    payload_tc_b = {"type": "function", "id": "call_b", "function": {"name": "book_taxi", "arguments": "{}"}}
    payload_msg = {"role": "assistant", "content": None, "tool_calls": [payload_tc_a, payload_tc_b]}
    orig = _ai_msg_with_raw_tool_calls([raw_tc_a, raw_tc_b])

    _restore_tool_call_signatures(payload_msg, orig)

    assert payload_tc_a["thought_signature"] == "SIG_STEP1=="
    assert payload_tc_b["thought_signature"] == "SIG_STEP2=="


# Integration behavior for PatchedChatOpenAI is validated indirectly via
# _restore_tool_call_signatures unit coverage above.


# ---------------------------------------------------------------------------
# Reasoning content capture (streaming and non-streaming)
# ---------------------------------------------------------------------------


def _model() -> PatchedChatOpenAI:
    return PatchedChatOpenAI(model="test-model", api_key="test-key")


def _stream_chunk(delta: dict) -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "test-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
    }


def test_stream_chunk_captures_reasoning_content():
    """reasoning_content from a stream delta lands in additional_kwargs."""
    model = _model()
    generation_chunk = model._convert_chunk_to_generation_chunk(
        _stream_chunk({"content": "hi", "reasoning_content": "thinking..."}),
        AIMessageChunk,
        None,
    )
    assert generation_chunk is not None
    assert generation_chunk.message.additional_kwargs["reasoning_content"] == "thinking..."


def test_stream_chunk_captures_reasoning_fallback():
    """OpenRouter-style `reasoning` delta is mapped to reasoning_content."""
    model = _model()
    generation_chunk = model._convert_chunk_to_generation_chunk(
        _stream_chunk({"content": "hi", "reasoning": "thinking..."}),
        AIMessageChunk,
        None,
    )
    assert generation_chunk is not None
    assert generation_chunk.message.additional_kwargs["reasoning_content"] == "thinking..."


def test_stream_chunk_without_reasoning_has_no_reasoning_key():
    """Plain content deltas do not get a reasoning_content key."""
    model = _model()
    generation_chunk = model._convert_chunk_to_generation_chunk(
        _stream_chunk({"content": "hi"}),
        AIMessageChunk,
        None,
    )
    assert generation_chunk is not None
    assert "reasoning_content" not in generation_chunk.message.additional_kwargs


def test_non_streaming_result_captures_reasoning_content():
    """Non-streaming responses attach reasoning_content to the AIMessage."""
    response = openai.types.chat.ChatCompletion(
        id="chatcmpl-1",
        choices=[
            openai.types.chat.chat_completion.Choice(
                finish_reason="stop",
                index=0,
                logprobs=None,
                message=openai.types.chat.ChatCompletionMessage(
                    role="assistant",
                    content="answer",
                    reasoning_content="thinking...",
                ),
            )
        ],
        created=0,
        model="test-model",
        object="chat.completion",
    )
    result = _model()._create_chat_result(response)
    message = result.generations[0].message
    assert message.additional_kwargs["reasoning_content"] == "thinking..."


def test_non_streaming_result_captures_model_extra_reasoning():
    """Gateways that stash reasoning in model_extra (e.g. OpenRouter) are handled."""
    response = openai.types.chat.ChatCompletion(
        id="chatcmpl-1",
        choices=[
            openai.types.chat.chat_completion.Choice(
                finish_reason="stop",
                index=0,
                logprobs=None,
                message=openai.types.chat.ChatCompletionMessage(
                    role="assistant",
                    content="answer",
                    reasoning="thinking...",
                ),
            )
        ],
        created=0,
        model="test-model",
        object="chat.completion",
    )
    result = _model()._create_chat_result(response)
    message = result.generations[0].message
    assert message.additional_kwargs["reasoning_content"] == "thinking..."


def test_request_payload_restores_reasoning_content():
    """Multi-turn payloads replay reasoning_content on assistant messages."""
    model = _model()
    payload = model._get_request_payload(
        [
            HumanMessage(content="question"),
            AIMessage(content="answer", additional_kwargs={"reasoning_content": "rc"}),
        ]
    )
    assistant_payloads = [m for m in payload["messages"] if m.get("role") == "assistant"]
    assert len(assistant_payloads) == 1
    assert assistant_payloads[0]["reasoning_content"] == "rc"
