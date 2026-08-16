"""Pushback middleware: deterministic informed-consent enforcement.

The deterministic version of the Architect's Protocol: when a user directive
contradicts a recorded commitment, the agent must voice the tradeoff before
executing. Execution is never blocked — the user's call is final; it is
simply informed.

Commitment sources (exchange-scoped, deterministic):
  - Prior visible user messages (within a lookback window).
  - Hidden memory / durable-context blocks carrying ``avoid:`` facts.

Detection:
  - Commitments carry a polarity: hard (``never``, ``do not``, ``avoid``...)
    or soft (``always``, ``must``, ``prefer``, ``keep``...).
  - A directive carries the opposite polarity: positive verbs (``add``,
    ``use``...) oppose negative commitments; negative verbs (``remove``,
    ``disable``...) oppose positive ones.
  - Conflict = the directive's object keyword reappears under opposing
    polarity. Direct contradictions only; replacements that never mention
    the old thing are invisible to the gate (documented limit).

Nudge semantics:
  - Hard conflict: state the consequence and ask for confirmation before
    proceeding.
  - Soft conflict: state the tradeoff, then proceed.
  - One nudge per user message. A reply containing tradeoff markers, or a
    newer user message, discharges the obligation.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from deerflow.config.pushback_config import get_pushback_config

logger = logging.getLogger(__name__)

MAX_NUDGES_PER_CALL = 1

_OBJECT_RE = re.compile(r"\b[a-z][a-z0-9\-_]{2,}\b", re.IGNORECASE)
_STOPWORDS = frozenset(
    {
        "the", "and", "for", "with", "that", "this", "have", "from", "your",
        "you", "are", "not", "was", "but", "all", "any", "can", "out",
        "just", "now", "about", "into", "them", "then", "its", "it's",
        "dont", "dont", "very", "really", "would", "could", "should", "okay",
        "please", "will", "when", "what", "which", "there", "here", "been",
    }
)

# Words that themselves encode object identity in commitments (so
# "don't disable the planner" -> object includes "planner").
_OBJECT_HINTS = ("planner", "gate", "mode", "feature", "emoji", "thinking")

# Generic domain words that rarely carry the contradiction's true subject.
# When the overlap contains anything more specific, the specific word wins.
_GENERIC_OBJECTS = frozenset(
    {"project", "deployment", "setup", "environment", "thing", "stuff", "part", "section"}
)


def _pick_subject(overlap: set[str], directive: str, commitment: str) -> str:
    """Choose the most distinctive overlapping object as the nudge subject."""
    specific = {word for word in overlap if word not in _GENERIC_OBJECTS}
    pool = specific or overlap
    scored = sorted(pool, key=lambda word: (directive.lower().count(word) + commitment.lower().count(word), len(word)), reverse=True)
    return scored[0]


class PushbackMiddleware(AgentMiddleware[AgentState]):
    """Voice tradeoffs before executing contradictory user decisions."""

    def __init__(self, *, app_config=None, pushback_config=None) -> None:
        super().__init__()
        self._app_config = app_config
        self._pushback_config = pushback_config

    def _get_config(self):
        if self._pushback_config is not None:
            return self._pushback_config
        section = getattr(self._app_config, "pushback", None)
        if section is not None:
            return section
        return get_pushback_config()

    # ── Text helpers ──

    @staticmethod
    def _hidden_text(message: HumanMessage) -> str:
        kwargs = getattr(message, "additional_kwargs", None) or {}
        if not isinstance(kwargs, dict) or not kwargs.get("hide_from_ui"):
            return ""
        content = getattr(message, "content", "")
        return content if isinstance(content, str) else ""

    @staticmethod
    def _objects(content: str) -> set[str]:
        words = {match.group(0).lower() for match in _OBJECT_RE.finditer(content)}
        words -= _STOPWORDS
        words |= {hint for hint in _OBJECT_HINTS if hint in content.lower()}
        return words

    def _has_hard(self, content: str) -> bool:
        return any(marker in content for marker in self._get_config().hard_markers)

    def _has_soft(self, content: str) -> bool:
        return any(marker in content for marker in self._get_config().soft_markers)

    @staticmethod
    def _is_negative(content: str, config) -> bool:
        lowered = content.lower()
        if any(verb in lowered for verb in config.negative_verbs):
            return True
        return any(marker in lowered for marker in config.hard_markers)

    @staticmethod
    def _is_positive(content: str, config) -> bool:
        return any(verb in content.lower() for verb in config.positive_verbs)

    def _commitments(self, messages: list) -> list[tuple[set, str]]:
        """Return (objects, polarity) commitments from prior user and hidden messages."""
        config = self._get_config()
        commitments: list[tuple[set, str]] = []
        for msg in messages[-config.lookback :]:
            if isinstance(msg, HumanMessage):
                hidden = self._hidden_text(msg)
                if hidden and "avoid:" in hidden:
                    commitments.append((self._objects(hidden), "hard"))
                    continue
                content = str(getattr(msg, "content", "") or "")
                if len(content) < config.min_chars:
                    continue
                if self._has_hard(content):
                    commitments.append((self._objects(content), "hard"))
                elif self._has_soft(content):
                    commitments.append((self._objects(content), "soft"))
        return commitments

    # ── History-derived state ──

    @staticmethod
    def _latest_user_index(messages: list) -> int | None:
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return i
        return None

    def _exchange(self, messages: list, user_idx: int) -> list:
        return list(messages[user_idx + 1 :])

    @staticmethod
    def _tradeoff_voiced(exchange: list, config) -> bool:
        for msg in exchange:
            if isinstance(msg, AIMessage):
                content = str(getattr(msg, "content", "") or "").lower()
                if any(marker in content for marker in config.tradeoff_markers):
                    return True
        return False

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list) -> list[HumanMessage]:
        config = self._get_config()
        if not config.enabled:
            return []

        user_idx = self._latest_user_index(messages)
        if user_idx is None:
            return []
        latest = messages[user_idx]
        directive = str(getattr(latest, "content", "") or "")
        if len(directive) < config.min_chars:
            return []

        prior = list(messages[:user_idx])
        commitments = self._commitments(prior)
        if not commitments:
            return []

        directive_objects = self._objects(directive)
        directive_negative = self._is_negative(directive, config)
        exchange = self._exchange(messages, user_idx)
        if self._tradeoff_voiced(exchange, config):
            return []

        for objects, polarity in reversed(commitments):
            overlap = directive_objects & objects
            if not overlap:
                continue
            conflict = (polarity == "hard" and not directive_negative) or (polarity == "soft" and directive_negative)
            if not conflict:
                continue
            # Recover the commitment's text for subject scoring.
            commitment_text = ""
            for msg in messages[:user_idx]:
                if isinstance(msg, HumanMessage):
                    content = str(getattr(msg, "content", "") or "") + " " + self._hidden_text(msg)
                    if objects <= self._objects(content):
                        commitment_text = content
                        break
            subject = _pick_subject(overlap, directive, commitment_text)
            if polarity == "hard":
                text = (
                    f"[PUSHBACK REMINDER] The user previously committed to avoiding or stopping "
                    f"'{subject}', and this directive contradicts that. Before executing, state "
                    "the consequence of reversing this decision and ask the user to confirm they "
                    "still want it. Their call is final — just make it an informed one."
                )
            else:
                text = (
                    f"[PUSHBACK REMINDER] The user previously committed to keeping or preferring "
                    f"'{subject}', and this directive conflicts with it. State the tradeoff "
                    "(what is gained, what is lost) in one or two sentences, then proceed with "
                    "the user's new direction. Their call is final."
                )
            return [self._nudge(text)]

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
            logger.info("PushbackMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

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
