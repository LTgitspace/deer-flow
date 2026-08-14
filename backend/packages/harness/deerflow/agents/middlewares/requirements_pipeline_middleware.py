"""Pipeline middleware chaining BRD -> PRD -> SRS.

The three requirements middlewares enforce their own documents in isolation.
This middleware chains them deterministically:

  - Ordering: a PRD must not be produced before the business case exists
    (BRD) and an SRS must not be produced before the product definition
    (PRD) exists. A user waiver ("skip the BRD", "no PRD needed") releases
    the gate - the chain is a nudge, not a hard block.
  - Traceability: once the predecessor document exists in the thread, the
    successor must reference it (PRD maps to BRD objectives, SRS maps to
    PRD stories). A document that ignores its predecessor gets a correction
    nudge until it traces back.

Activation: only when at least one of the three skills is active in the
thread context. The business-requirement skill is the root of the chain and
gets no pipeline nudges; product-requirements and software-requirements are
the chained stages. All state is derived from message history and
skill_context - no custom_data writes, deterministic across runs.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

logger = logging.getLogger(__name__)

# ── Chain definition ──

_BRD_SKILL = "business-requirement"
_PRD_SKILL = "product-requirements"
_SRS_SKILL = "software-requirements"

_CHAIN_SKILLS = (_BRD_SKILL, _PRD_SKILL, _SRS_SKILL)

MAX_NUDGES_PER_CALL = 1

# User statements that release an ordering gate.
_BRD_WAIVER_PATTERNS = ("skip the brd", "no brd", "without brd", "skip brd", "brd is not needed", "don't need a brd", "no business case")
_PRD_WAIVER_PATTERNS = ("skip the prd", "no prd", "without prd", "skip prd", "prd is not needed", "don't need a prd", "straight to srs", "directly to srs")


class RequirementsPipelineMiddleware(AgentMiddleware[AgentState]):
    """Chain BRD -> PRD -> SRS with ordering and traceability nudges."""

    # ── Activation detection ──

    @classmethod
    def _current_skill(cls, messages: list, state: dict) -> str | None:
        """The chain skill being worked on right now, or None.

        Preference order: the most recent slash activation mentioning one of
        the chain skills, then the most recently loaded skill_context entry.
        Returns None when no chain skill is active.
        """
        # Latest slash activation wins: scan messages backwards for the newest
        # activation reminder referencing a chain skill.
        for msg in reversed(messages):
            if not isinstance(msg, HumanMessage):
                continue
            additional_kwargs = getattr(msg, "additional_kwargs", None) or {}
            if not additional_kwargs.get("slash_skill_activation"):
                continue
            content = str(getattr(msg, "content", "") or "")
            for skill in _CHAIN_SKILLS:
                if f'name="{skill}"' in content or f"`{skill}`" in content:
                    return skill

        # Fallback: most recently loaded skill_context entry among chain skills.
        best_skill: str | None = None
        best_loaded_at = -1
        for entry in (state or {}).get("skill_context") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if name not in _CHAIN_SKILLS:
                continue
            loaded_at = entry.get("loaded_at")
            if isinstance(loaded_at, int) and loaded_at > best_loaded_at:
                best_loaded_at = loaded_at
                best_skill = name
        return best_skill

    # ── Document detection (AI content only - nudges are hidden and ignored) ──

    @staticmethod
    def _ai_contents(messages: list) -> list[str]:
        return [
            str(getattr(msg, "content", "") or "").lower()
            for msg in messages
            if isinstance(msg, AIMessage)
        ]

    @classmethod
    def _has_brd(cls, messages: list) -> bool:
        for content in cls._ai_contents(messages):
            if "brd" in content or "business requirements document" in content:
                return True
            if "business requirement" in content and "objective" in content:
                return True
        return False

    @classmethod
    def _has_prd(cls, messages: list) -> bool:
        for content in cls._ai_contents(messages):
            if "# prd" in content:
                return True
            if "product vision" in content and "persona" in content:
                return True
        return False

    @classmethod
    def _has_srs(cls, messages: list) -> bool:
        for content in cls._ai_contents(messages):
            if "software requirements specification" in content:
                return True
            if "data dictionary" in content or "| requirement id |" in content:
                return True
        return False

    @classmethod
    def _latest_doc_content(cls, messages: list, marker: str) -> str:
        """Content of the latest AI message carrying the document marker."""
        for msg in reversed(messages):
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if marker in content.lower():
                return content.lower()
        return ""

    @staticmethod
    def _waived(messages: list, patterns: tuple[str, ...]) -> bool:
        """True when a recent visible user message explicitly released the gate."""
        for msg in reversed(messages[-12:]):
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if any(p in content for p in patterns):
                return True
        return False

    # ── Nudge builder ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list, state: dict) -> list[HumanMessage]:
        current = self._current_skill(messages, state)
        if current is None or current == _BRD_SKILL:
            # Root of the chain, or no requirements skill active.
            return []

        if current == _PRD_SKILL:
            return self._prd_stage_nudges(messages)

        # current == _SRS_SKILL
        return self._srs_stage_nudges(messages)

    def _prd_stage_nudges(self, messages: list) -> list[HumanMessage]:
        brd_exists = self._has_brd(messages)
        prd_exists = self._has_prd(messages)

        if not brd_exists and not self._waived(messages, _BRD_WAIVER_PATTERNS):
            if prd_exists:
                text = (
                    "[PIPELINE REMINDER] STOP: a PRD has been produced but this thread "
                    "has no BRD. The business case must come first - activate "
                    "/business-requirement and produce the BRD (objectives, stakeholders, "
                    "feasibility), or ask the user to explicitly waive it ('skip the BRD'). "
                    "A product defined without a business case is not acceptable."
                )
            else:
                text = (
                    "[PIPELINE REMINDER] You are about to define a product, but this "
                    "thread has no BRD. Business case first: activate /business-requirement "
                    "and produce the BRD, or ask the user to explicitly waive it "
                    "('skip the BRD'). The PRD features and metrics must then trace to "
                    "the BRD objectives."
                )
            return [self._nudge(text)]

        if brd_exists and prd_exists:
            doc = self._latest_doc_content(messages, "# prd") or self._latest_doc_content(messages, "product vision")
            traceable = "brd" in doc or "business objective" in doc or "br-" in doc
            if not traceable:
                return [
                    self._nudge(
                        "[PIPELINE REMINDER] This thread contains a BRD, but the PRD does "
                        "not reference it. Map each PRD feature and success metric back to "
                        "the BRD's business objectives (include a 'BRD objective -> PRD "
                        "feature / metric' table). A PRD that ignores its business case "
                        "is not acceptable."
                    )
                ]

        return []

    def _srs_stage_nudges(self, messages: list) -> list[HumanMessage]:
        prd_exists = self._has_prd(messages)
        srs_exists = self._has_srs(messages)

        if not prd_exists and not self._waived(messages, _PRD_WAIVER_PATTERNS):
            if srs_exists:
                text = (
                    "[PIPELINE REMINDER] STOP: an SRS has been produced but this thread "
                    "has no PRD. The product definition must come first - activate "
                    "/product-requirements and produce the PRD (personas, vision, metrics, "
                    "prioritized features), or ask the user to explicitly waive it "
                    "('skip the PRD'). Engineering a spec without a product definition is "
                    "not acceptable."
                )
            else:
                text = (
                    "[PIPELINE REMINDER] You are about to write an engineering spec, but "
                    "this thread has no PRD. Product definition first: activate "
                    "/product-requirements and produce the PRD, or ask the user to "
                    "explicitly waive it ('skip the PRD'). The SRS requirements must then "
                    "trace to the PRD stories."
                )
            return [self._nudge(text)]

        if prd_exists and srs_exists:
            doc = self._latest_doc_content(messages, "software requirements specification") or self._latest_doc_content(messages, "| requirement id |")
            traceable = "prd" in doc or "us-" in doc
            if not traceable:
                return [
                    self._nudge(
                        "[PIPELINE REMINDER] This thread contains a PRD, but the SRS does "
                        "not reference it. The traceability matrix must map requirement "
                        "IDs to PRD stories/features (reference the story IDs in the "
                        "Source column). Requirements without a product source are not "
                        "acceptable."
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
            logger.info("RequirementsPipelineMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        state = getattr(request, "state", None) or {}

        nudges = self._build_nudges(messages, state)
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

        nudges = self._build_nudges(messages, state)
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
