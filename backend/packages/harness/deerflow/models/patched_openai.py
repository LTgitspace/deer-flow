"""Patched ChatOpenAI that preserves provider thinking metadata.

Two OpenAI-compatible extensions are handled here:

1. Gemini thinking via OpenAI-compatible gateways: the API requires the
   ``thought_signature`` field on tool-call objects to be echoed back verbatim
   in every subsequent request. Standard ``langchain_openai.ChatOpenAI`` only
   serialises the standard fields (``id``, ``type``, ``function``), silently
   dropping the signature and causing HTTP 400 ``INVALID_ARGUMENT`` errors.

2. Reasoning models behind OpenAI-compatible gateways (DeepSeek-style
   ``reasoning_content``, OpenRouter-style ``reasoning``): base ChatOpenAI
   drops these fields from both stream deltas and final responses, so
   thinking never reaches the frontend. This patched class captures them
   into ``additional_kwargs["reasoning_content"]`` (the same contract
   ``ChatDeepSeek`` uses) and replays them back on assistant messages in
   multi-turn payloads when thinking mode is enabled.
"""

from __future__ import annotations

from typing import Any

import openai
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_openai import ChatOpenAI

from deerflow.models.assistant_payload_replay import restore_assistant_payloads, restore_reasoning_content


class PatchedChatOpenAI(ChatOpenAI):
    """ChatOpenAI with thinking-metadata preservation for OpenAI-compatible gateways.

    Extends the base client with two behaviors:

    - Restores ``thought_signature`` onto tool-call objects for Gemini thinking
      through OpenAI-compatible gateways (multi-turn requirement).
    - Captures ``reasoning_content`` / ``reasoning`` from stream deltas and
      final responses into ``additional_kwargs["reasoning_content"]`` so
      thinking streams to the frontend, and replays it on assistant messages
      in subsequent payloads (multi-turn requirement for reasoning APIs).

    Usage in ``config.yaml``::

        - name: gemini-2.5-pro-thinking
          display_name: Gemini 2.5 Pro (Thinking)
          use: deerflow.models.patched_openai:PatchedChatOpenAI
          model: google/gemini-2.5-pro-preview
          api_key: $GEMINI_API_KEY
          base_url: https://<your-openai-compat-gateway>/v1
          max_tokens: 16384
          supports_thinking: true
          supports_vision: true
          when_thinking_enabled:
            extra_body:
              thinking:
                type: enabled
    """

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        """Get request payload with ``thought_signature`` and ``reasoning_content`` preserved.

        Overrides the parent method to re-inject ``thought_signature`` fields
        on tool-call objects and ``reasoning_content`` on assistant messages
        that were stored in ``additional_kwargs`` by LangChain but dropped
        during serialisation.
        """
        # Capture the original LangChain messages *before* conversion so we can
        # access fields that the serialiser might drop.
        original_messages = self._convert_input(input_).to_messages()

        # Obtain the base payload from the parent implementation.
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)

        restore_assistant_payloads(payload.get("messages", []), original_messages, _restore_tool_call_signatures)
        restore_assistant_payloads(payload.get("messages", []), original_messages, restore_reasoning_content)

        return payload

    def _convert_chunk_to_generation_chunk(
        self,
        chunk: dict,
        default_chunk_class: type,
        base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        """Convert a stream delta to a generation chunk, preserving reasoning content.

        Base ``ChatOpenAI`` drops ``reasoning_content`` from stream deltas;
        this override attaches it to ``additional_kwargs`` so chunk merging
        accumulates thinking and the SSE stream carries it to the frontend.
        """
        generation_chunk = super()._convert_chunk_to_generation_chunk(
            chunk,
            default_chunk_class,
            base_generation_info,
        )
        if (choices := chunk.get("choices")) and generation_chunk:
            top = choices[0]
            if isinstance(generation_chunk.message, AIMessageChunk):
                delta = top.get("delta") or {}
                if (reasoning_content := delta.get("reasoning_content")) is not None:
                    generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning_content
                elif (reasoning := delta.get("reasoning")) is not None:
                    generation_chunk.message.additional_kwargs["reasoning_content"] = reasoning

        return generation_chunk

    def _create_chat_result(
        self,
        response: dict | openai.BaseModel,
        generation_info: dict | None = None,
    ) -> ChatResult:
        """Attach reasoning content to the final message for non-streaming responses.

        Handles DeepSeek-style ``message.reasoning_content`` and gateways that
        stash it in ``model_extra`` (e.g. OpenRouter ``reasoning``).
        """
        rtn = super()._create_chat_result(response, generation_info)

        if not isinstance(response, openai.BaseModel):
            return rtn

        choices = getattr(response, "choices", None)
        if not choices or not rtn.generations:
            return rtn

        message = choices[0].message
        reasoning: str | None = None
        if hasattr(message, "reasoning_content") and isinstance(message.reasoning_content, str):
            reasoning = message.reasoning_content
        if reasoning is None:
            model_extra = getattr(message, "model_extra", None)
            if isinstance(model_extra, dict):
                candidate = model_extra.get("reasoning") or model_extra.get("reasoning_content")
                if isinstance(candidate, str):
                    reasoning = candidate
        if reasoning:
            rtn.generations[0].message.additional_kwargs["reasoning_content"] = reasoning

        return rtn


def _restore_tool_call_signatures(payload_msg: dict, orig_msg: AIMessage) -> None:
    """Re-inject ``thought_signature`` onto tool-call objects in *payload_msg*.

    When the Gemini OpenAI-compatible gateway returns a response with function
    calls, each tool-call object may carry a ``thought_signature``.  LangChain
    stores the raw tool-call dicts in ``additional_kwargs["tool_calls"]`` but
    only serialises the standard fields (``id``, ``type``, ``function``) into
    the outgoing payload, silently dropping the signature.

    This function matches raw tool-call entries (by ``id``, falling back to
    positional order) and copies the signature back onto the serialised
    payload entries.
    """
    raw_tool_calls: list[dict] = orig_msg.additional_kwargs.get("tool_calls") or []
    payload_tool_calls: list[dict] = payload_msg.get("tool_calls") or []

    if not raw_tool_calls or not payload_tool_calls:
        return

    # Build an id → raw_tc lookup for efficient matching.
    raw_by_id: dict[str, dict] = {}
    for raw_tc in raw_tool_calls:
        tc_id = raw_tc.get("id")
        if tc_id:
            raw_by_id[tc_id] = raw_tc

    for idx, payload_tc in enumerate(payload_tool_calls):
        # Try matching by id first, then fall back to positional.
        raw_tc = raw_by_id.get(payload_tc.get("id", ""))
        if raw_tc is None and idx < len(raw_tool_calls):
            raw_tc = raw_tool_calls[idx]

        if raw_tc is None:
            continue

        # The gateway may use either snake_case or camelCase.
        sig = raw_tc.get("thought_signature") or raw_tc.get("thoughtSignature")
        if sig:
            payload_tc["thought_signature"] = sig
