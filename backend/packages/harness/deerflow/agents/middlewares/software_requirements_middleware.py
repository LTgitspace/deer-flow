"""Deterministic gate middleware for the software-requirements skill.

Enforces the 6-phase SRS contract from the software-requirements SKILL.md
in code. This is NOT a prompt - it nudges, counts, and validates regardless
of what the model decides to do.

Phases enforced:
  Phase 1: Context discovery - one question at a time via ask_clarification
    (no batching) until the user's answers contain >= 3 context signals
    (target user, problem, stakeholders, business goal, timeline, platform).
  Phase 2: User stories (As a / I want / So that) with checkbox acceptance
    criteria, testable targets, and explicit MoSCoW priorities.
  Phase 3: Functional specification - step flows, edge cases, validation
    rules, and error states (not just the happy path). At least one mermaid
    diagram for a non-trivial flow or state machine.
  Phase 4: Data dictionary - core entities with fields, constraints, and
    enumerations.
  Phase 5: Validation and traceability - requirement IDs with source and
    test case, plus the review checklist (testability, contradictions,
    measurable NFRs, error states, external dependencies, privacy).
  Phase 6: Deliver the final SRS document with the required sections.

Forced context gate: the middleware only activates when the
software-requirements skill is active in the thread (slash-activated or
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
_SKILL_NAME = "software-requirements"

# Generic context signals (BRD-style context discovery: keep asking until a
# visible user message matches >= 3 signals).
_SRS_CONTEXT_SIGNALS = (
    "user", "users", "persona", "problem", "solve", "stakeholder",
    "business goal", "goal", "revenue", "retention", "timeline", "month",
    "week", "platform", "web", "mobile", "desktop", "api", "integrate",
    "existing system", "migration", "replace", "new system", "greenfield",
)

_QUESTION_SEQUENCE = (
    "Who is the target user, and what problem does this solve?",
    "Is this a new system or replacing an existing one?",
    "Who are the stakeholders, and what is the business goal?",
    "What is the timeline and target platform (web / mobile / desktop / API)?",
    "Are there existing systems to integrate with?",
)

# Vague words that must never appear in acceptance criteria or NFR targets.
_VAGUE_WORDS = ("fast", "easy", "reliable", "robust", "user-friendly", "intuitive", "seamless", "scalable")

# Measurable-target markers: at least one must be present for ACs to count as testable.
_MEASURABLE_MARKERS = ("seconds", "minutes", "ms", "%", "<", ">", "within", "uptime", "wcag", "lighthouse", "bcrypt", "encrypt")


class SoftwareRequirementsMiddleware(AgentMiddleware[AgentState]):
    """Enforce the software-requirements phases deterministically."""

    # ── Detection helpers ──

    @staticmethod
    def _context_answered(messages: list) -> bool:
        """True when a recent visible user message carries >= 3 context signals.

        Scoped to the recent exchange (re-arming behavior): old context from a
        previous topic in a long thread must not permanently satisfy the gate.
        """
        signals = [
            "user", "persona", "problem", "solve", "stakeholder",
            "business goal", "goal", "timeline", "platform", "integrate",
            "existing system", "migration", "replace", "new",
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
    def _has_functional_spec(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "edge case" in content or ("flow" in content and "validation" in content)

    @classmethod
    def _has_error_states(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "error state" in content or content.count("error") >= 2

    @classmethod
    def _has_data_dictionary(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages)
        lowered = content.lower()
        return "data dictionary" in lowered or "| field |" in lowered or "| field " in lowered

    @classmethod
    def _has_traceability(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "traceability" in content or "| requirement id |" in content

    @classmethod
    def _has_validation(cls, messages: list) -> bool:
        content = cls._latest_ai_content(messages).lower()
        return "review checklist" in content or "contradict" in content

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
                        "[SRS REMINDER] The user has not answered your last question yet. "
                        "Do NOT guess their answers or proceed with requirements - wait for "
                        "their reply, then ask the next context question."
                    )
                ]
            asks = self._count_clarification_asks(messages)
            question = _QUESTION_SEQUENCE[min(asks, len(_QUESTION_SEQUENCE) - 1)]
            return [
                self._nudge(
                    "[SRS REMINDER] Gather full requirements context. No guessing. Ask ONE "
                    "question at a time via ask_clarification - do not batch questions. "
                    f"Next question: {question} Keep asking until you have: target user, "
                    "problem, stakeholders, business goal, timeline, and platform. "
                    "Do not write any requirements before context is established."
                )
            ]

        # Phase 2 - user stories with acceptance criteria.
        if not self._has_stories(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Write user stories in the 'As a / I want / So that' format. "
                    "Start with the 3 core stories. Each story needs checkbox acceptance "
                    "criteria and a MoSCoW priority. No requirements without stories."
                )
            ]

        if not self._has_acceptance_criteria(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Every user story needs acceptance criteria as a checkbox "
                    "list ('- [ ] criterion'). Each criterion must be verifiable - no vague "
                    "words. Include concrete examples for the core stories."
                )
            ]

        if not self._has_testable_criteria(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Acceptance criteria are not testable yet. Remove vague words "
                    f"(fast, easy, reliable, intuitive, seamless). Each criterion needs a "
                    "measurable target: '< 2 seconds', 'within 60 seconds', '99.9% uptime', "
                    "a specific error message, or an exact state transition. "
                    f"Minimum {MIN_AC_CHECKBOXES} checkbox criteria with at least one "
                    "measurable marker."
                )
            ]

        if not self._has_priorities(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Assign explicit MoSCoW priorities to every story and NFR "
                    "(Must-have / Should-have / Could-have / Won't have). Not everything can "
                    "be P0 - priorities drive MVP scoping."
                )
            ]

        # Mermaid gate - at least one flow or state diagram.
        if not self._has_mermaid(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Include at least one mermaid diagram (```mermaid ... ``` "
                    "code block) for a non-trivial flow or state machine - e.g. the core "
                    "feature flow or the order state transitions. Requirements documents "
                    "need visual flows, not just prose."
                )
            ]

        # Phase 3 - functional specification.
        if not self._has_functional_spec(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] For each feature, produce the functional spec: numbered "
                    "step flow, edge cases with expected behavior, and validation rules "
                    "(field / rule / error message table). Link each feature back to its "
                    "story ID."
                )
            ]

        if not self._has_error_states(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Document error states per feature, not just the happy "
                    "path: empty state, loading state, error state with message and retry, "
                    "success state, and edge cases (empty results / rate limited / offline)."
                )
            ]

        # Phase 4 - data dictionary.
        if not self._has_data_dictionary(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Add the data dictionary: core entities with a field "
                    "table (Field / Type / Required / Default / Constraints / Notes) and "
                    "enumerations with their allowed values and where they are used. "
                    "Minimum 2 core entities."
                )
            ]

        # Phase 5 - traceability and validation.
        if not self._has_traceability(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Produce the traceability matrix: Requirement ID / Type "
                    "(Functional, Non-functional) / Source (story or stakeholder) / Test "
                    "Case / Status. Every requirement must trace to a source - nothing "
                    "unattributed."
                )
            ]

        if not self._has_validation(messages):
            return [
                self._nudge(
                    "[SRS REMINDER] Run the review checklist before delivering: every "
                    "requirement testable with no vague words, NFRs have concrete targets, "
                    "no two requirements contradict each other, all roles/permissions "
                    "defined, error states documented, external dependencies identified, "
                    "and data retention / privacy addressed."
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
            logger.info("SoftwareRequirementsMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

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
