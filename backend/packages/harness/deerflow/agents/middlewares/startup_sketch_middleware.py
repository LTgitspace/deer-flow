"""Startup-sketch middleware: deterministic gate for the lean sketching flow.

Enforces the startup-sketch SKILL.md contract: idea core first (one
question at a time), mermaid sketch before any description, product
description before business description (product-first ordering), and a
plain HTML/CSS landing page at the end.

Activation: the gate only fires when the startup-sketch skill is active
(slash-activated or loaded into skill_context). Sketch-shaped but inactive
conversations get a single activation nudge.

All state is derived from message history; hidden HumanMessage nudges only.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

from deerflow.agents.middlewares.skill_context import skill_is_active

logger = logging.getLogger(__name__)

MAX_NUDGES_PER_CALL = 1

_SKILL_NAME = "startup-sketch"

_SKETCH_TRIGGERS = (
    "startup",
    "startup idea",
    "landing page",
    "pitch",
    "mvp",
    "business idea",
    "product idea",
    "sketch",
    "side project idea",
)

_IDEA_SIGNALS = (
    "problem", "customer", "vision", "user", "who", "target", "audience",
    "solve", "pain", "alternative", "idea",
)

_QUESTION_SEQUENCE = (
    "What problem does it solve?",
    "Who has this problem (the target customer)?",
    "What do they do today instead?",
    "What is the one-sentence product vision?",
)

# Framework markers that must never appear in the landing page deliverable.
_LANDING_FRAMEWORK_MARKERS = (
    "react", "next.js", "nextjs", "tailwind", "bootstrap", "vite",
    "webpack", "node_modules", "npm install", "create-next-app",
    "<script src", "cdn",
)


class StartupSketchMiddleware(AgentMiddleware[AgentState]):
    """Enforce the product-first lean sketching contract deterministically."""

    # ── History-derived state ──

    @staticmethod
    def _latest_user_message(messages: list) -> HumanMessage | None:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return msg
        return None

    def _is_sketch_shaped(self, messages: list) -> bool:
        latest = self._latest_user_message(messages)
        if latest is None:
            return False
        content = str(getattr(latest, "content", "") or "").lower()
        return any(trigger in content for trigger in _SKETCH_TRIGGERS)

    def _idea_answered(self, messages: list) -> bool:
        """True when a recent user message carries >= 3 idea-core signals."""
        for msg in reversed(messages[-12:]):
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if sum(1 for signal in _IDEA_SIGNALS if signal in content) >= 3:
                return True
        return False

    @staticmethod
    def _user_replied_after_last_ask(messages: list, lookback: int = 12) -> bool:
        recent = messages[-lookback:]
        for i in range(len(recent) - 1, -1, -1):
            msg = recent[i]
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "").strip()
            has_tool_ask = any(
                "clarif" in (tc.get("name", "") or "") for tc in getattr(msg, "tool_calls", None) or []
            )
            if has_tool_ask or (content and content.endswith("?") and len(content) < 600):
                for later in recent[i + 1 :]:
                    if isinstance(later, HumanMessage) and not (
                        (getattr(later, "additional_kwargs", None) or {}).get("hide_from_ui")
                    ):
                        return True
                return False
        return True

    @staticmethod
    def _count_clarification_asks(messages: list) -> int:
        count = 0
        for msg in messages[-12:]:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                if any("clarif" in (tc.get("name", "") or "") for tc in msg.tool_calls):
                    count += 1
        return count

    @staticmethod
    def _ai_content(messages: list, lookback: int = 10) -> str:
        chunks: list[str] = []
        for msg in reversed(messages[-lookback:]):
            if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                chunks.append(str(getattr(msg, "content", "") or "").lower())
        return "\n".join(chunks)

    def _has_mermaid(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(m in c for m in ("```mermaid", "graph td", "graph lr", "flowchart"))

    def _has_product_description(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "## product description" in c or ("mvp scope" in c and "vision" in c)

    def _has_business_description(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "## business description" in c or ("revenue model" in c and "value proposition" in c)

    def _has_landing_page(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "<!doctype html>" in c or "<html" in c

    def _landing_uses_framework(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(marker in c for marker in _LANDING_FRAMEWORK_MARKERS)

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list) -> list[HumanMessage]:
        # Phase 0 — idea core, one question at a time.
        if not self._idea_answered(messages):
            if not self._user_replied_after_last_ask(messages):
                return [
                    self._nudge(
                        "[SKETCH REMINDER] The user has not answered your last idea question yet. "
                        "Wait for their reply, then ask the next question."
                    )
                ]
            asks = self._count_clarification_asks(messages)
            question = _QUESTION_SEQUENCE[min(asks, len(_QUESTION_SEQUENCE) - 1)]
            return [
                self._nudge(
                    "[SKETCH REMINDER] Gather the idea core before sketching. Ask ONE question at "
                    f"a time via ask_clarification. Next question: {question} Keep asking until "
                    "you have the problem, the customer, and the product vision. Never invent "
                    "answers."
                )
            ]

        # Phase 1 — sketch before prose.
        if not self._has_mermaid(messages):
            return [
                self._nudge(
                    "[SKETCH REMINDER] Visualize before describing: produce the mermaid sketch "
                    "first — a concept map (graph TD) and a user flow. No written descriptions "
                    "until the diagrams exist."
                )
            ]

        # Phase 2 — product description before business.
        if not self._has_product_description(messages):
            return [
                self._nudge(
                    "[SKETCH REMINDER] Write the Product Description next: vision, core features "
                    "(3-5 prioritized), MVP scope, and what is explicitly out of scope. Product "
                    "before business — the user's ordering."
                )
            ]

        # Phase 3 — business description after product.
        if not self._has_business_description(messages):
            return [
                self._nudge(
                    "[SKETCH REMINDER] Now the Business Description: problem, solution, value "
                    "proposition, customer, and revenue model. Keep it a one-pager."
                )
            ]

        # Phase 4 — landing page, plain HTML only.
        if not self._has_landing_page(messages):
            return [
                self._nudge(
                    "[SKETCH REMINDER] Finish with the landing page: a single self-contained "
                    "HTML file with inline CSS. Hero, problem, features, how it works, footer. "
                    "No frameworks, no build tools, no external scripts."
                )
            ]

        if self._landing_uses_framework(messages):
            return [
                self._nudge(
                    "[SKETCH REMINDER] The landing page references frameworks or external "
                    "resources (React/Next/Tailwind/CDN). Rebuild it as pure HTML with inline "
                    "CSS — one file, zero dependencies."
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
            logger.info("StartupSketchMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        if not self._is_sketch_shaped(messages):
            return handler(request)

        state = getattr(request, "state", None) or {}
        if not skill_is_active(messages, state, _SKILL_NAME):
            # Inactive-skill fast exit: do NOT inject an activation nudge on
            # casual queries that merely contain sketch-shaped words. The
            # contract gates only fire once the skill is explicitly active
            # (slash-activated or loaded into skill_context).
            return handler(request)

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
        if not self._is_sketch_shaped(messages):
            return await handler(request)

        state = getattr(request, "state", None) or {}
        if not skill_is_active(messages, state, _SKILL_NAME):
            # Inactive-skill fast exit: see wrap_model_call.
            return await handler(request)

        nudges = self._build_nudges(messages)
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
