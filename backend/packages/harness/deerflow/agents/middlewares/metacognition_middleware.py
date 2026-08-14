"""Metacognition middleware: deterministic think-first enforcement.

Skills teach, middlewares enforce. This middleware enforces one rule:
complex requests must be answered with reasoning; trivial requests must not
be lectured about it.

Contract:
  - Classification is deterministic from the latest visible user message:
    length >= min_complexity_chars, a question mark with length >=
    min_question_chars, a trigger word with length >= min_trigger_chars, or
    multi-part shape (repeated conjunctions / multiple lines).
  - Thinking evidence follows the marker contract pinned by
    ``PatchedChatOpenAI``: ``additional_kwargs["reasoning_content"]`` on
    AIMessage (non-empty string). Explicit reasoning text in the answer
    (numbered steps, "reasoning:", etc.) also counts, so models without
    API-level thinking can still satisfy the gate by writing it out.
  - Gate A (pre-answer): a complex prompt gets ONE hidden nudge requiring
    reasoning before the final answer. Only when the model has not yet
    answered the latest user message.
  - Gate B (post-answer): when the very last message is an AI answer to a
    complex prompt with no thinking evidence, ONE correction nudge asks for
    a reasoned re-answer. A newer user message ends the obligation, so the
    gate cannot nag across turns.

Design notes:
  - Hidden HumanMessage nudges (hide_from_ui), the same pattern as all
    skill gates: self-correction, no hard rejections, no per-turn API
    toggling.
  - No state writes; everything derives from message history.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from deerflow.config.metacognition_config import get_metacognition_config

if TYPE_CHECKING:
    from deerflow.config.app_config import AppConfig
    from deerflow.config.metacognition_config import MetacognitionConfig

logger = logging.getLogger(__name__)

MAX_NUDGES_PER_CALL = 1

# Reasoning markers the model may write as visible text (thinking-off mode).
_EXPLICIT_REASONING_MARKERS = (
    "step 1",
    "step-by-step",
    "reasoning:",
    "## reasoning",
    "let me think",
    "thought process",
    "analysis:",
    "## analysis",
    "first,",
)

_MULTIPART_MIN_OCCURRENCES = 2


class MetacognitionMiddleware(AgentMiddleware[AgentState]):
    """Enforce think-first for complex prompts, stay silent for trivial ones."""

    def __init__(
        self,
        *,
        app_config: AppConfig | None = None,
        metacognition_config: MetacognitionConfig | None = None,
    ) -> None:
        super().__init__()
        self._app_config = app_config
        self._metacognition_config = metacognition_config

    def _get_config(self) -> MetacognitionConfig:
        if self._metacognition_config is not None:
            return self._metacognition_config
        if self._app_config is not None:
            section = getattr(self._app_config, "metacognition", None)
            if section is not None:
                return section
        return get_metacognition_config()

    # ── History-derived state ──

    @staticmethod
    def _latest_user_message(messages: list) -> HumanMessage | None:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return msg
        return None

    @staticmethod
    def _last_message_is_ai(messages: list) -> bool:
        return bool(messages) and isinstance(messages[-1], AIMessage)

    @staticmethod
    def _user_before_last_ai(messages: list) -> HumanMessage | None:
        """The visible HumanMessage immediately preceding the trailing AI message."""
        for msg in reversed(messages[:-1]):
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return msg
        return None

    def _classify_complex(self, content: str) -> bool:
        config = self._get_config()
        content = content.strip()
        if not content:
            return False
        if len(content) >= config.min_complexity_chars:
            return True
        lowered = content.lower()
        if "?" in content and len(content) >= config.min_question_chars:
            return True
        if len(content) >= config.min_trigger_chars and any(t in lowered for t in config.triggers):
            return True
        if len(content) >= config.min_trigger_chars and (
            lowered.count(" and ") >= _MULTIPART_MIN_OCCURRENCES or lowered.count("\n") >= _MULTIPART_MIN_OCCURRENCES
        ):
            return True
        return False

    def _is_complex(self, messages: list) -> bool:
        latest = self._latest_user_message(messages)
        if latest is None:
            return False
        return self._classify_complex(str(getattr(latest, "content", "") or ""))

    @staticmethod
    def _has_thinking_evidence(message: AIMessage) -> bool:
        """True when the answer carries reasoning per the PatchedChatOpenAI contract."""
        additional_kwargs = getattr(message, "additional_kwargs", None) or {}
        reasoning = additional_kwargs.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            return True
        content = str(getattr(message, "content", "") or "").lower()
        return any(marker in content for marker in _EXPLICIT_REASONING_MARKERS)

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list) -> list[HumanMessage]:
        config = self._get_config()
        if not config.enabled:
            return []
        nudges: list[HumanMessage] = []

        # Gate B — post-answer correction. Only while an un-reasoned answer to
        # a complex prompt is still the latest message; a newer user message
        # ends the obligation so this can never nag across turns.
        if self._last_message_is_ai(messages):
            last_ai = messages[-1]
            if not self._has_thinking_evidence(last_ai):
                user_before = self._user_before_last_ai(messages)
                if user_before is not None and self._classify_complex(str(getattr(user_before, "content", "") or "")):
                    nudges.append(
                        self._nudge(
                            "[METACOGNITION REMINDER] Your previous answer to a complex request "
                            "contained no visible reasoning. Re-answer with explicit step-by-step "
                            "reasoning before the conclusion — the user asked for depth, not a guess."
                        )
                    )
                    return nudges[:MAX_NUDGES_PER_CALL]
            # A reasoned answer (or an unanswered non-complex question): stay quiet.
            return []

        # Gate A — pre-answer. The upcoming answer must reason.
        if self._is_complex(messages):
            nudges.append(
                self._nudge(
                    "[METACOGNITION REMINDER] This is a complex request. Think step-by-step and "
                    "include your reasoning before the final answer — do not jump straight to a "
                    "conclusion. If thinking mode is on, let the reasoning stream; if not, write "
                    "a short explicit reasoning section first."
                )
            )

        return nudges[:MAX_NUDGES_PER_CALL]

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
            logger.info("MetacognitionMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

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
