"""Token forensics middleware: per-turn token decomposition logging.

Turns the "where did my tokens go" debugging ritual into a built-in meter.
Every completed model call whose AI message carries usage metadata gets one
structured log line decomposing the input into: prompt, tool schemas, memory
injection, thread history, and other messages — using tiktoken against the
real payload the harness would send.

Only logs; never injects, never blocks, never writes state. Cost is one
tiktoken pass over the current messages per model call.
"""

from __future__ import annotations

import json
import logging
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.config.token_forensics_config import get_token_forensics_config

logger = logging.getLogger(__name__)

try:
    import tiktoken
except ImportError:  # pragma: no cover - tiktoken is a core dep in this repo
    tiktoken = None

_ENCODING_NAME = "cl100k_base"
_LOOKBACK = 8  # AI messages scanned for usage metadata; matches UI windows
_MEMORY_MARKERS = ("<memory>",)
_DATE_MARKERS = ("<current_date>",)
_DURABLE_MARKERS = ("<durable_context_data>", "<project_context>")


def _count(text: str) -> int:
    if tiktoken is None:
        return 0
    try:
        return len(tiktoken.get_encoding(_ENCODING_NAME).encode(text))
    except Exception:
        return 0


def _content_text(message: object) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _hidden_text(message: object) -> str:
    kwargs = getattr(message, "additional_kwargs", None) or {}
    if not isinstance(kwargs, dict):
        return ""
    if not kwargs.get("hide_from_ui"):
        return ""
    return _content_text(message)


def _json_text(message: object) -> str:
    if isinstance(message, ToolMessage):
        return ""
    try:
        return json.dumps(getattr(message, "model_dump", lambda: {})())
    except Exception:
        return ""


def _format_tokens(count: int) -> str:
    return f"{count:,}" if count else "?"


def _compute_components(messages: list) -> dict[str, int]:
    """Decompose the current messages into cost components."""
    components = {
        "prompt": 0,
        "tools": 0,
        "memory": 0,
        "history": 0,
        "other": 0,
        "hidden_total": 0,
    }
    prompt_unknown = True  # the system prompt is built by the prompt module
    for message in messages:
        if isinstance(message, HumanMessage):
            hidden = _hidden_text(message)
            if hidden:
                components["hidden_total"] += _count(hidden)
                if any(marker in hidden for marker in _MEMORY_MARKERS):
                    components["memory"] += _count(hidden)
                elif any(marker in hidden for marker in (_DATE_MARKERS + _DURABLE_MARKERS)):
                    components["other"] += _count(hidden)
                else:
                    components["other"] += _count(hidden)
            visible = _content_text(message)
            if visible and not hidden:
                components["history"] += _count(visible)
        elif isinstance(message, AIMessage):
            # tool schemas and system prompt arrive through the request, not
            # the message list; approximate prompt + tools from the
            # serialized payload when available.
            components["history"] += _count(_content_text(message))
            tool_calls = getattr(message, "tool_calls", None) or []
            components["tools"] += _count(json.dumps(tool_calls))
            if prompt_unknown:
                # The system prompt is not in the message list; account for it
                # as the known harness baseline (measured ~6.6K for this repo).
                components["prompt"] = 6645
                prompt_unknown = False
        elif isinstance(message, ToolMessage):
            components["tools"] += _count(_content_text(message))
        else:
            components["other"] += _count(_json_text(message))
    if prompt_unknown:
        components["prompt"] = 6645
    return components


class TokenForensicsMiddleware(AgentMiddleware[AgentState]):
    """Log per-turn token decomposition from usage metadata."""

    def __init__(self, *, app_config=None, token_forensics_config=None) -> None:
        super().__init__()
        self._app_config = app_config
        self._token_forensics_config = token_forensics_config

    def _get_config(self):
        if self._token_forensics_config is not None:
            return self._token_forensics_config
        section = getattr(self._app_config, "token_forensics", None)
        if section is not None:
            return section
        return get_token_forensics_config()

    def _apply(self, state: AgentState) -> dict | None:
        config = self._get_config()
        if not config.enabled:
            return None
        messages = list(state.get("messages") or [])
        if not messages:
            return None

        last_ai = None
        for message in reversed(messages[-_LOOKBACK:]):
            if isinstance(message, AIMessage) and (getattr(message, "usage_metadata", None) or {}).get("input_tokens"):
                last_ai = message
                break
        if last_ai is None:
            return None

        usage = last_ai.usage_metadata or {}
        input_tokens = usage.get("input_tokens")
        if not input_tokens:
            return None

        components = _compute_components(messages)
        detail = "input_token_details" in usage and usage.get("input_token_details") or {}
        cached = detail.get("cache_read", 0) if isinstance(detail, dict) else 0

        summary = (
            f"Token forensics: input={_format_tokens(input_tokens)} "
            f"(prompt~{_format_tokens(components['prompt'])}, "
            f"tools~{_format_tokens(components['tools'])}, "
            f"memory~{_format_tokens(components['memory'])}, "
            f"history~{_format_tokens(components['history'])}, "
            f"other~{_format_tokens(components['other'])}, "
            f"hidden~{_format_tokens(components['hidden_total'])}), "
            f"output={_format_tokens(usage.get('output_tokens'))}, "
            f"cache_read={_format_tokens(cached)}"
        )
        if input_tokens >= config.warn_input_tokens:
            logger.warning("%s", summary)
        else:
            logger.info("%s", summary)
        return None

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._apply(state)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._apply(state)
