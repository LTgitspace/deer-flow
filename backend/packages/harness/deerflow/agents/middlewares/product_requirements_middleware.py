"""Deterministic gate middleware for the product-requirements skill.

Enforces the 6-phase PRD contract from the product-requirements SKILL.md
in code. This is NOT a prompt - it nudges, counts, and validates regardless
of what the model decides to do.

Phases enforced:
  Phase 1: Context discovery - one question at a time via ask_clarification
    (no batching) until the user's answers contain >= 3 context signals
    (target user, problem, vision, success metric, timeline, platform).
  Phase 2: Problem statement, personas with pain points, product vision,
    and success metrics with numeric targets and measurement methods.
  Phase 3: Scope - explicit in/out of scope with reasons, open questions.
  Phase 4: Prioritized features - user stories with testable acceptance
    criteria, MoSCoW priorities, effort, dependencies, and a mermaid
    diagram for the core user journey.
  Phase 5: UX considerations, external dependencies, risks and open
    questions.
  Phase 6: Release criteria (testable definition of done) and a roadmap
    (MVP / V2 / later), then deliver the final PRD structure.

Forced context gate: the middleware only activates when the
product-requirements skill is active in the thread (slash-activated or
loaded into skill_context). All other conversations pass through untouched.
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

# ── Minimum thresholds ──

MAX_NUDGES_PER_CALL = 2
MIN_AC_CHECKBOXES = 2
MIN_CONTEXT_SIGNALS = 3

# Skill directory name this middleware enforces. The gate only fires when this
# skill is active in the thread (slash-activated or loaded into skill_context).
_SKILL_NAME = "product-requirements"

# Generic context signals (BRD-style context discovery: keep asking until a
# visible user message matches >= 3 signals).
_PRD_CONTEXT_SIGNALS = (
    "user", "users", "persona", "problem", "solve", "need", "vision",
    "goal", "metric", "kpi", "success", "timeline", "month", "week",
    "platform", "web", "mobile", "desktop", "mvp", "launch", "market",
)

_QUESTION_SEQUENCE = (
    "Who is the target user, and what core problem does the product solve?",
    "What is the product vision - what does the world look like when this succeeds?",
    "What does success look like in numbers (metrics and targets)?",
    "What is the timeline and target platform (web / mobile / desktop)?",
    "Which features are must-have for MVP, and which can wait?",
)

# Vague words that must never appear in acceptance criteria or metric targets.
_VAGUE_WORDS = ("fast", "easy", "reliable", "robust", "user-friendly", "intuitive", "seamless", "scalable")

# Measurable-target markers: at least one must be present for ACs to count as testable.
_MEASURABLE_MARKERS = ("seconds", "minutes", "ms", "%", "<", ">", "within", "uptime", "wcag", "lighthouse", "activate", "retention", "analytics")


class ProductRequirementsMiddleware(AgentMiddleware[AgentState]):
    """Enforce the product-requirements phases deterministically."""

    # ── Detection helpers ──

    @staticmethod
    def _context_answered(messages: list) -> bool:
        """True when a recent visible user message carries >= 3 context signals.

        Scoped to the recent exchange (re-arming behavior): old context from a
        previous topic in a long thread must not permanently satisfy the gate.
        """
        signals = [
            "user", "persona", "problem", "solve", "need", "vision",
            "metric", "kpi", "success", "timeline", "platform", "mvp",
            "launch", "market", "web", "mobile",
        ]
        for msg in reversed(messages[-12:]):
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            matched = sum(1 for s in signals if s in content)
            if matched >= MIN_CONTEXT_SIGNALS:
                return True
        return False

    @staticmethod
    def _user_replied_after_last_ask(messages: list, lookback: int = 12) -> bool:
        """True if a visible user message arrived after the model's most recent question.

        Returns True when there is no recent ask (nothing to wait on). Shared
        wait-gate semantics across all skill middlewares.
        """
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
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            for tc in getattr(msg, "tool_calls", None) or []:
                if isinstance(tc, dict) and tc.get("name") == "ask_clarification":
                    count += 1
        return count

    @staticmethod
    def _latest_ai_content(messages: list, lookback: int = 6) -> str:
        """Latest AI text in the recent window (excluding tool-call-only turns)."""
        for msg in reversed(messages[-lookback:]):
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if content.strip():
                return content
        return ""

    @classmethod
    def _has_personas(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "persona" in content and "pain point" in content

    @classmethod
    def _has_vision(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "vision" in content or "elevator pitch" in content

    @classmethod
    def _has_success_metrics(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        has_metric_section = "metric" in content or "kpi" in content
        has_measurable = any(m in content for m in _MEASURABLE_MARKERS)
        return has_metric_section and has_measurable

    @classmethod
    def _has_scope(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "in scope" in content or "out of scope" in content

    @classmethod
    def _has_stories(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "as a" in content and "i want" in content

    @classmethod
    def _has_acceptance_criteria(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages)
        lowered = content.lower()
        return "acceptance criteria" in lowered or content.count("- [ ]") >= 1

    @classmethod
    def _has_testable_criteria(cls, messages: list) -> bool:
        """ACs exist, are checkboxed, and carry at least one measurable target."""
        content = cls._latest_ai_content(messages)
        lowered = content.lower()
        if content.count("- [ ]") < MIN_AC_CHECKBOXES:
            return False
        if any(w in lowered for w in _VAGUE_WORDS):
            return False
        return any(m in lowered for m in _MEASURABLE_MARKERS)

    @classmethod
    def _has_priorities(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return any(p in content for p in ("must-have", "should-have", "could-have", "won't have", "moscow", "p0", "p1", "p2"))

    @classmethod
    def _has_mermaid(cls, messages: list) -> bool:
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if "```mermaid" in content or "flowchart" in content:
                return True
        return False

    @classmethod
    def _has_ux(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "ux consideration" in content or "user journey" in content

    @classmethod
    def _has_dependencies_risks(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "dependency" in content or "risk" in content

    @classmethod
    def _has_release_criteria(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "release criteria" in content or "definition of done" in content

    @classmethod
    def _has_roadmap(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "roadmap" in content

    # ── Nudge builder ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list) -> list[HumanMessage]:
        nudges: list[HumanMessage] = []

        # Phase 1 - context discovery, one question at a time.
        if not self._context_answered(messages):
            # Wait-gate: do not advance the question sequence while the user
            # has not answered the current question.
            if not self._user_replied_after_last_ask(messages):
                return [
                    self._nudge(
                        "[PRD REMINDER] The user has not answered your last question yet. "
                        "Do NOT guess their answers or proceed with the product definition - "
                        "wait for their reply, then ask the next context question."
                    )
                ]
            asks = self._count_clarification_asks(messages)
            question = _QUESTION_SEQUENCE[min(asks, len(_QUESTION_SEQUENCE) - 1)]
            return [
                self._nudge(
                    "[PRD REMINDER] Gather full product context. No guessing. Ask ONE "
                    "question at a time via ask_clarification - do not batch questions. "
                    f"Next question: {question} Keep asking until you have: target user, "
                    "problem, vision, success metrics, timeline, and platform. "
                    "Do not write any requirements before context is established."
                )
            ]

        # Phase 2 - problem, personas, vision, metrics.
        if not self._has_personas(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Define the problem statement and personas first: for "
                    "each persona, a description, goals, and pain points. A PRD without "
                    "clear personas is a solution in search of a user."
                )
            ]

        if not self._has_vision(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] State the product vision as an elevator pitch: For "
                    "{target user} who {need}, {product} is a {category} that {key "
                    "benefit}. Unlike {alternatives}, it {differentiator}. Every later "
                    "decision must trace back to this vision."
                )
            ]

        if not self._has_success_metrics(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Define success metrics with numeric targets and "
                    "measurement methods: current value, target value, timeframe, and "
                    "how it is measured (analytics event, funnel, cohort). No vague "
                    "goals - 'more engagement' is not a metric, 'activation rate 40% "
                    "in 3 months' is."
                )
            ]

        # Phase 3 - scope.
        if not self._has_scope(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Define scope explicitly: what is IN scope for MVP "
                    "and what is OUT of scope (with the reason for each - V2, later, "
                    "never). List open questions that need a decision. Without this "
                    "boundary the product will drift."
                )
            ]

        # Phase 4 - prioritized features.
        if not self._has_stories(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Write the prioritized features as user stories "
                    "('As a / I want / so that'). Each feature needs: acceptance "
                    "criteria, MoSCoW priority, effort (S/M/L), and dependencies. "
                    "Start with the 3 core MVP features."
                )
            ]

        if not self._has_acceptance_criteria(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Every feature needs acceptance criteria as a "
                    "checkbox list ('- [ ] criterion'). Each criterion must be "
                    "verifiable - no vague words. Concrete examples for the core "
                    "features."
                )
            ]

        if not self._has_testable_criteria(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Acceptance criteria are not testable yet. Remove "
                    f"vague words (fast, easy, reliable, intuitive, seamless). Each "
                    "criterion needs a measurable target: '< 5 seconds', 'within 60 "
                    "seconds', a specific percentage, or an exact state. "
                    f"Minimum {MIN_AC_CHECKBOXES} checkbox criteria with at least one "
                    "measurable marker."
                )
            ]

        if not self._has_priorities(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Assign explicit MoSCoW priorities to every feature "
                    "(Must-have / Should-have / Could-have / Won't have). Not "
                    "everything can be Must-have - priorities drive the MVP cut."
                )
            ]

        # Mermaid gate - core user journey.
        if not self._has_mermaid(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Include at least one mermaid diagram (```mermaid "
                    "... ``` code block) for the core user journey or product flow. "
                    "A PRD needs a visual journey map, not just prose."
                )
            ]

        # Phase 5 - UX, dependencies, risks.
        if not self._has_ux(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Add UX considerations: navigation model, key "
                    "screens, empty/loading/error states, accessibility, and the "
                    "user journey through the core flow."
                )
            ]

        if not self._has_dependencies_risks(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Identify external dependencies (services, teams, "
                    "data, contracts) and risks / open questions with impact and "
                    "owner. A PRD without dependencies is not actionable."
                )
            ]

        # Phase 6 - release criteria and roadmap.
        if not self._has_release_criteria(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Define release criteria - the testable definition "
                    "of done for launch (e.g. 'checkout flow completes in < 5 "
                    "seconds', 'activation rate >= 40%'). The team must know what "
                    "'done' means."
                )
            ]

        if not self._has_roadmap(messages):
            return [
                self._nudge(
                    "[PRD REMINDER] Add the roadmap: MVP scope with target date, V2 "
                    "(promoted out-of-scope items), and later ideas. End with the "
                    "review checklist: testable ACs, numeric metrics, explicit "
                    "scope, priorities, journey diagram, release criteria, "
                    "dependencies - then deliver the final PRD structure."
                )
            ]

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
            logger.info("ProductRequirementsMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)

        state = getattr(request, "state", None) or {}
        if not skill_is_active(messages, state, _SKILL_NAME):
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

        state = getattr(request, "state", None) or {}
        if not skill_is_active(messages, state, _SKILL_NAME):
            return await handler(request)

        nudges = self._build_nudges(messages)
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
