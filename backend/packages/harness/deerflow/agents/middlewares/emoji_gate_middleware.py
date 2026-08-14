"""Emoji gate middleware: keep code, file writes, and configs emoji-free.

Enforces the operator's standing rule deterministically: no emojis in
generated code or technical configuration blocks. Casual visible chat is
allowed by default — this gate polices artifacts, not personality.

Contract:
  - Gate A (pre-edit): the model is about to write a file (write_file /
    str_replace) containing emojis -> one correction nudge to strip them
    before the write executes.
  - Gate B (post-output): an AI message containing fenced code blocks with
    emojis -> one correction nudge to re-emit the block emoji-free.
  - Gate C (config content): visible chat with emojis is passed when
    allow_in_chat=True; with allow_in_chat=False everything is gated.

Mechanics:
  - Emoji detection is a Unicode range scan (no dependency on an emoji
    library): pictographs, emoticons, symbols, dingbats, variation
    selectors, regional indicators.
  - Hidden HumanMessage nudges (hide_from_ui), self-correction only.
  - Exchange-scoped: a newer visible user message ends the obligation, so
    the gate cannot nag across unrelated turns.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.config.emoji_gate_config import get_emoji_gate_config

logger = logging.getLogger(__name__)

MAX_NUDGES_PER_CALL = 1

# Unicode ranges covering emoji: pictographs, emoticons, symbols/pictographs
# extended, dingbats, variation selectors, regional indicators, and the
# supplementary symbols blocks (0x1F300-0x1FAFF).
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE00-\uFE0F\U0001F1E6-\U0001F1FF]"
)

_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)

_WRITE_TOOLS = ("write_file", "str_replace")


def _has_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


def _has_emoji_in_code_blocks(content: str) -> bool:
    return any(_has_emoji(block) for block in _CODE_FENCE_RE.findall(content))


class EmojiGateMiddleware(AgentMiddleware[AgentState]):
    """Keep code, file writes, and configs emoji-free."""

    def __init__(self, *, app_config=None, emoji_gate_config=None) -> None:
        super().__init__()
        self._app_config = app_config
        self._emoji_gate_config = emoji_gate_config

    def _get_config(self):
        if self._emoji_gate_config is not None:
            return self._emoji_gate_config
        section = getattr(self._app_config, "emoji_gate", None)
        if section is not None:
            return section
        return get_emoji_gate_config()

    # ── History-derived state ──

    @staticmethod
    def _latest_user_index(messages: list) -> int | None:
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return i
        return None

    def _exchange(self, messages: list) -> list:
        user_idx = self._latest_user_index(messages)
        if user_idx is None:
            # Tool-call-only turn (no visible user message): gate the full list.
            return list(messages)
        return list(messages[user_idx + 1 :])

    def _pending_emoji_write(self, exchange: list) -> bool:
        """True when a pending write_file / str_replace call carries emojis."""
        for msg in exchange:
            if not isinstance(msg, AIMessage):
                continue
            for tool_call in getattr(msg, "tool_calls", None) or []:
                if tool_call.get("name") not in _WRITE_TOOLS:
                    continue
                args = tool_call.get("args") or {}
                content = str(args.get("content") or args.get("new_str") or "")
                if _has_emoji(content):
                    completed = any(
                        isinstance(later, ToolMessage)
                        and getattr(later, "tool_call_id", None) == tool_call.get("id")
                        for later in exchange
                    )
                    if not completed:
                        return True
        return False

    def _unfixed_emoji_code(self, exchange: list) -> bool:
        """True when the latest AI message still carries emojis inside code fences."""
        for msg in reversed(exchange):
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if _has_emoji_in_code_blocks(content):
                return True
        return False

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list) -> list[HumanMessage]:
        config = self._get_config()
        if not config.enabled:
            return []
        exchange = self._exchange(messages)
        if not exchange:
            return []

        if self._pending_emoji_write(exchange):
            return [
                self._nudge(
                    "[EMOJI GATE REMINDER] You are about to write a file containing emojis. "
                    "Strip all emojis from the file content before writing — generated code and "
                    "technical files must be strictly emoji-free."
                )
            ]

        if self._unfixed_emoji_code(exchange):
            return [
                self._nudge(
                    "[EMOJI GATE REMINDER] A code block in your output contains emojis. "
                    "Re-emit the code block with all emojis removed — generated code and "
                    "technical configuration must stay strictly professional."
                )
            ]

        if not config.allow_in_chat:
            for msg in reversed(exchange):
                if isinstance(msg, AIMessage) and _has_emoji(str(getattr(msg, "content", "") or "")):
                    return [
                        self._nudge(
                            "[EMOJI GATE REMINDER] Emojis are disabled in all output. "
                            "Re-answer without emojis."
                        )
                    ]
        return []

    def _patch_messages(self, messages: list, nudges: list[HumanMessage]) -> list:
        patched = list(messages)
        insert_at = 0
        for i, msg in enumerate(patched):
            if isinstance(msg, HumanMessage) or isinstance(msg, AIMessage):
                insert_at = i
                break
        for nudge in reversed(nudges):
            patched.insert(insert_at, nudge)
        return patched

    @staticmethod
    def _log_nudges(nudges: list[HumanMessage]) -> None:
        """Log every injected nudge for observability."""
        for nudge in nudges:
            logger.info("EmojiGateMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        nudges = self._build_nudges(messages)
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        messages = list(request.messages)
        nudges = self._build_nudges(messages)
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
