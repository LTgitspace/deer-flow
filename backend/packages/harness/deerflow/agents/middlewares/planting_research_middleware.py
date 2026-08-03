"""Deterministic gate middleware for the planting-research skill.

Enforces the 8-phase research contract from the planting-research SKILL.md
in code. This is NOT a prompt — it blocks, counts, and validates regardless
of what the model decides to do.

Phases enforced:
  Phase 1: Scope must be defined before any tool call
  Phase 2: Locale must be confirmed before biology/chemistry research
  Phase 2.5: Calendar should include 12 months of climate data
  Phase 3: Biology research must have growth cycle, root specs, light needs
  Phase 4: Chemistry must have pH range, NPK per stage, deficiency table
  Phase 5: Process must contain specific local product/store names
  Phase 8: Local details must include water quality, local pests, local stores
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

# ── Phase state tracking keys (stored in ThreadState.custom_data) ──

_PHASE_KEY = "_planting_research_phase"
_SEARCH_COUNT_KEY = "_planting_research_search_count"
_UNIQUE_QUERIES_KEY = "_planting_research_unique_queries"
_LOCALE_CONFIRMED_KEY = "_planting_research_locale_confirmed"

# ── Minimum thresholds ──

MIN_SEARCHES_BEFORE_SYNTHESIS = 3
MIN_UNIQUE_ANGLES = 3
MIN_SOURCES_PER_CLAIM = 2
MIN_MONTHS_IN_CALENDAR = 12

# ── Phase names ──

PHASE_SCOPE = "scope"
PHASE_LOCALE = "locale"
PHASE_CALENDAR = "calendar"
PHASE_BIOLOGY = "biology"
PHASE_CHEMISTRY = "chemistry"
PHASE_PROCESS = "process"
PHASE_TIPS = "tips"
PHASE_TUTORIAL = "tutorial"
PHASE_LOCAL = "local"

PHASE_ORDER = [
    PHASE_SCOPE,
    PHASE_LOCALE,
    PHASE_CALENDAR,
    PHASE_BIOLOGY,
    PHASE_CHEMISTRY,
    PHASE_PROCESS,
    PHASE_TIPS,
    PHASE_TUTORIAL,
    PHASE_LOCAL,
]


class PlantingResearchMiddleware(AgentMiddleware[AgentState]):
    """Enforce planting research phases deterministically.

    Counts web_search calls, tracks locale confirmation, and injects
    structured nudges when phases are skipped. Does not block the model
    completely — nudges are injected as hidden context so the model
    self-corrects without a hard rejection loop.
    """

    @staticmethod
    def _current_phase(state: dict[str, Any]) -> str:
        return (state.get("custom_data") or {}).get(_PHASE_KEY, PHASE_SCOPE)

    @staticmethod
    def _search_count(state: dict[str, Any]) -> int:
        return (state.get("custom_data") or {}).get(_SEARCH_COUNT_KEY, 0)

    @staticmethod
    def _unique_queries(state: dict[str, Any]) -> set[str]:
        raw = (state.get("custom_data") or {}).get(_UNIQUE_QUERIES_KEY) or []
        return set(raw)

    @staticmethod
    def _locale_confirmed(state: dict[str, Any]) -> bool:
        return (state.get("custom_data") or {}).get(_LOCALE_CONFIRMED_KEY, False)

    @staticmethod
    def _has_mermaid(messages: list) -> bool:
        """True if the latest AI content already contains a mermaid diagram."""
        for msg in reversed(messages):
            if not isinstance(msg, AIMessage):
                continue
            if getattr(msg, "tool_calls", None):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            return any(
                marker in content
                for marker in ("mermaid", "graph td", "graph lr", "sequencediagram", "flowchart")
            )
        return False

    # ── Per-step utilities ──

    def _extract_search_queries(self, messages: list) -> tuple[int, set[str]]:
        """Count web_search calls and extract unique query strings."""
        count = 0
        queries: set[str] = set()
        for msg in messages:
            if not isinstance(msg, ToolMessage):
                continue
            content = getattr(msg, "content", "") or ""
            name = getattr(msg, "name", "") or ""
            if name != "web_search":
                continue
            count += 1
            # Try to extract query from structured tool calls in preceding AIMessage
            # Fall back to first 100 chars of content as a fingerprint
            fingerprint = str(content)[:100].strip()
            if fingerprint:
                queries.add(fingerprint)
        return count, queries

    def _detect_locale_confirmation(self, messages: list) -> bool:
        """Check if locale has been provided by the user."""
        # Look for human messages containing location indicators
        locale_hints = [
            "vietnam", "ho chi minh", "hanoi", "da nang",
            "saigon", "singapore", "bangkok", "jakarta", "manila",
            "kuala lumpur", "indo", "malay", "thai",
            "usda zone", "climate zone", "tropical", "temperate",
            "indoor", "outdoor", "balcony", "garden", "greenhouse",
        ]
        recent_human_msgs = [
            msg for msg in messages
            if isinstance(msg, HumanMessage)
            and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui")
        ]
        for msg in recent_human_msgs[-3:]:
            content = str(getattr(msg, "content", "") or "").lower()
            for hint in locale_hints:
                if hint in content:
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

    def _build_nudge(self, phase: str, missing: str, search_count: int = 0) -> HumanMessage:
        """Create a hidden context message that nudges the model."""
        nudges = {
            PHASE_LOCALE: (
                "[SYSTEM REMINDER] You have not confirmed the user's planting locale. "
                "Use ask_clarification to ask: country, indoor/outdoor, climate zone, "
                "current season. Do not proceed to biology or chemistry without this."
            ),
            PHASE_CALENDAR: (
                "[SYSTEM REMINDER] Build the 12-month calendar. Each month must include "
                "temperature range, plant status, watering schedule, and pest watch. "
                "Include a climate summary table with avg temp, rainfall, and daylight hours."
            ),
            PHASE_BIOLOGY: (
                "[SYSTEM REMINDER] Complete the biological profile: growth cycle table "
                "(germination → seedling → vegetative → flowering → fruiting → dormancy), "
                "root depth/spread, light requirements, pollination method, pests/diseases."
            ),
            PHASE_CHEMISTRY: (
                "[SYSTEM REMINDER] Complete the chemical profile: soil pH range, NPK ratios "
                "per growth stage, specific fertilizer products, deficiency symptoms table, "
                "water chemistry tolerance, and toxicity warnings."
            ),
            PHASE_PROCESS: (
                "[SYSTEM REMINDER] The process guide must include local products and store names. "
                "No generalizations. Include: pot selection (with local store), soil mix recipe "
                "(with local sources), seed sourcing (specific stores in locale), "
                "germination schedule, daily/weekly care routine, harvesting guide."
            ),
            PHASE_TIPS: (
                "[SYSTEM REMINDER] Include common beginner mistakes table, yield-boosting hacks "
                "with credibility sources, pest control table with organic vs chemical options, "
                "and community wisdom (Reddit threads, YouTube channels)."
            ),
            PHASE_TUTORIAL: (
                "[SYSTEM REMINDER] The beginner tutorial needs: shopping list with local prices, "
                "Day 1 setup steps, daily care instructions, troubleshooting table "
                "(symptom → what it means → what to do)."
            ),
            PHASE_LOCAL: (
                "[SYSTEM REMINDER] Add local details: tap water quality, climate threats "
                "(typhoon/frost/heat wave with dates), local soil analysis, local fertilizer "
                "brand names, local pest names in user's language, local gardening groups, "
                "and invasive species check."
            ),
            "search_depth": (
                f"[SYSTEM REMINDER] You have done {search_count} searches. "
                f"Minimum required: {MIN_SEARCHES_BEFORE_SYNTHESIS}. "
                "Search from different angles — you need varied perspectives, not variants "
                "of the same query."
            ),
            "wait": (
                "[SYSTEM REMINDER] The user has not answered your last question yet. "
                "Do NOT guess or proceed on assumptions — wait for their answer, "
                "then continue the research."
            ),
            "mermaid": (
                "[SYSTEM REMINDER] Your final answer must include at least one mermaid diagram "
                "(```mermaid ... ``` code block) visualizing the key structure, process, or flow "
                "of your research. If your answer already contains one, ignore this."
            ),
        }
        content = nudges.get(phase, nudges.get(missing, f"[SYSTEM REMINDER] Complete phase: {phase}"))
        return HumanMessage(content=content, additional_kwargs={"hide_from_ui": True})

    @staticmethod
    def _log_nudges(nudges: list[HumanMessage]) -> None:
        """Log every injected nudge for observability."""
        for nudge in nudges:
            logger.info("PlantingResearchMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        state = request.state or {}

        search_count, unique_queries = self._extract_search_queries(messages)
        locale_confirmed = self._detect_locale_confirmation(messages)
        current_phase = self._current_phase(state)

        nudges: list[HumanMessage] = []

        # Gate 1: Locale MUST be confirmed before anything beyond scope
        if current_phase in (PHASE_SCOPE, PHASE_LOCALE) and not locale_confirmed:
            if self._user_replied_after_last_ask(messages):
                nudges.append(self._build_nudge(PHASE_LOCALE, "", search_count))
            else:
                nudges.append(self._build_nudge("", "wait", search_count))

        # Gate 2: Search depth check
        if current_phase in (PHASE_BIOLOGY, PHASE_CHEMISTRY, PHASE_PROCESS, PHASE_TIPS):
            if search_count < MIN_SEARCHES_BEFORE_SYNTHESIS:
                nudges.append(self._build_nudge("", "search_depth", search_count))

        # Gate 3: Calendar completeness
        if current_phase == PHASE_CALENDAR:
            calendar_months_found = 0
            for msg in messages[-5:]:
                content = str(getattr(msg, "content", "") or "")
                calendar_months_found += content.count("| January")
                calendar_months_found += content.count("| February")
                calendar_months_found += content.count("| March")
            if calendar_months_found < MIN_MONTHS_IN_CALENDAR:
                nudges.append(self._build_nudge(PHASE_CALENDAR, "", search_count))

        # Gate 4: Synthesis must include a mermaid diagram
        if search_count >= MIN_SEARCHES_BEFORE_SYNTHESIS and not self._has_mermaid(messages):
            nudges.append(self._build_nudge("", "mermaid", search_count))

        # Inject nudges as hidden messages before the model call
        if nudges:
            # Find insertion point: after the last system message, before user messages
            patched = list(messages)
            insert_at = 0
            for i, msg in enumerate(patched):
                if isinstance(msg, HumanMessage) or isinstance(msg, AIMessage):
                    insert_at = i
                    break
            for nudge in reversed(nudges):
                patched.insert(insert_at, nudge)
            self._log_nudges(nudges)
            request = request.override(messages=patched)

        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        # Same logic as sync version
        messages = list(request.messages)
        state = request.state or {}

        search_count, unique_queries = self._extract_search_queries(messages)
        locale_confirmed = self._detect_locale_confirmation(messages)
        current_phase = self._current_phase(state)

        nudges: list[HumanMessage] = []

        if current_phase in (PHASE_SCOPE, PHASE_LOCALE) and not locale_confirmed:
            if self._user_replied_after_last_ask(messages):
                nudges.append(self._build_nudge(PHASE_LOCALE, "", search_count))
            else:
                nudges.append(self._build_nudge("", "wait", search_count))

        if current_phase in (PHASE_BIOLOGY, PHASE_CHEMISTRY, PHASE_PROCESS, PHASE_TIPS):
            if search_count < MIN_SEARCHES_BEFORE_SYNTHESIS:
                nudges.append(self._build_nudge("", "search_depth", search_count))

        if current_phase == PHASE_CALENDAR:
            calendar_months_found = 0
            for msg in messages[-5:]:
                content = str(getattr(msg, "content", "") or "")
                calendar_months_found += content.count("| January")
                calendar_months_found += content.count("| February")
                calendar_months_found += content.count("| March")
            if calendar_months_found < MIN_MONTHS_IN_CALENDAR:
                nudges.append(self._build_nudge(PHASE_CALENDAR, "", search_count))

        if search_count >= MIN_SEARCHES_BEFORE_SYNTHESIS and not self._has_mermaid(messages):
            nudges.append(self._build_nudge("", "mermaid", search_count))

        if nudges:
            patched = list(messages)
            insert_at = 0
            for i, msg in enumerate(patched):
                if isinstance(msg, HumanMessage) or isinstance(msg, AIMessage):
                    insert_at = i
                    break
            for nudge in reversed(nudges):
                patched.insert(insert_at, nudge)
            self._log_nudges(nudges)
            request = request.override(messages=patched)

        return await handler(request)
