"""Deterministic gate middleware for the business-requirement skill.

Enforces the 7-phase BRD contract from the business-requirement SKILL.md
in code. Tracks continuous context discovery, end-to-end process mapping with
Mermaid diagrams, scope management, intention anchoring, feasibility assessment,
glossary maintenance, consistency checks, and polished output.

Phases enforced:
  Phase 0: Continuous context discovery — ask, don't guess
  Phase 1: End-to-end process mapping with Mermaid diagrams
  Phase 2: Scope management (in-scope / out-of-scope)
  Phase 3: Intention anchoring (trace back to original objective)
  Phase 4: Feature feasibility assessment
  Phase 5: Glossary maintenance
  Phase 6: Consistency review (cross-reference checks)
  Phase 7: Polish & format (professional output)
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage

logger = logging.getLogger(__name__)

# ── Minimum thresholds ──

MIN_STAKEHOLDER_COUNT = 2
MIN_OBJECTIVE_COUNT = 2
MIN_PAIN_POINTS = 2
MIN_REQUIREMENTS = 5
MIN_RISKS = 3
MIN_GLOSSARY_TERMS = 3
MIN_COST_ITEMS = 2
MIN_BENEFIT_ITEMS = 2


class BusinessRequirementMiddleware(AgentMiddleware[AgentState]):
    """Enforce business requirement phases deterministically."""

    # ── Detection helpers ──

    @staticmethod
    def _context_answered(messages: list) -> bool:
        signals = [
            "problem", "opportunity", "stakeholder", "sponsor",
            "objective", "kpi", "budget", "timeline", "constraint",
            "approval", "integration", "existing system",
        ]
        for msg in reversed(messages):
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            matched = sum(1 for s in signals if s in content)
            if matched >= 3:
                return True
        return False

    @staticmethod
    def _has_objectives(messages: list) -> bool:
        for msg in messages[-8:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if "objective" in content and ("kpi" in content or "target" in content):
                return True
        return False

    @staticmethod
    def _has_mermaid(messages: list) -> bool:
        """Check if Mermaid diagrams exist in the output."""
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if "```mermaid" in content or "flowchart" in content:
                return True
        return False

    @staticmethod
    def _has_scope(messages: list) -> bool:
        """Check if scope section exists with in/out-of-scope."""
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            has_in = "In Scope" in content
            has_out = "Out of Scope" in content
            if has_in or has_out:
                return True
        return False

    @staticmethod
    def _has_stakeholders(messages: list) -> bool:
        for msg in messages[-8:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if "Stakeholder" in content and ("Influence" in content or "interest" in content.lower()):
                return True
        return False

    @staticmethod
    def _has_current_state(messages: list) -> bool:
        signals = ["pain point", "as-is", "current state", "current cost", "current process"]
        for msg in messages[-8:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if sum(1 for s in signals if s in content) >= 2:
                return True
        return False

    @staticmethod
    def _has_requirements(messages: list) -> bool:
        for msg in messages[-8:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            has_br = "BR-" in content or "Business Requirement" in content
            has_fr = "FR-" in content or "Functional Requirement" in content
            if has_br or has_fr:
                return True
        return False

    @staticmethod
    def _has_feasibility(messages: list) -> bool:
        """Check if feasibility assessment exists."""
        signals = ["feasibility", "Feasibility"]
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if any(s in content for s in signals):
                return True
        return False

    @staticmethod
    def _has_glossary(messages: list) -> bool:
        """Check if glossary exists with defined terms."""
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if "Glossary" in content and "Term" in content and "Definition" in content:
                return True
        return False

    @staticmethod
    def _has_risks(messages: list) -> bool:
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if "Risk" in content and "Mitigation" in content:
                return True
        return False

    @staticmethod
    def _has_cost_benefit(messages: list) -> bool:
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            has_monetary = "$" in content
            has_roi = "ROI" in content.lower() or "payback" in content.lower()
            has_cost_table = "Cost" in content and "Benefit" in content
            if has_monetary and (has_roi or has_cost_table):
                return True
        return False

    @staticmethod
    def _has_recommendation(messages: list) -> bool:
        signals = ["recommendation", "should proceed", "should not proceed", "go forward", "next step"]
        for msg in messages[-4:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if any(s in content for s in signals):
                return True
        return False

    @staticmethod
    def _has_numbers(messages: list) -> bool:
        import re
        for msg in messages[-8:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            if re.search(r'\$\s*\d[\d,]*', content):
                return True
            if re.search(r'\d+\s*%', content):
                return True
        return False

    @staticmethod
    def _has_intention_check(messages: list) -> bool:
        """Check if intention anchoring / scope creep check has occurred."""
        signals = ["original intention", "still on track", "scope creep", "intention change"]
        for msg in messages[-6:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if any(s in content for s in signals):
                return True
        return False

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

    # ── Nudge builder ──

    def _build_nudge(self, reason: str) -> HumanMessage:
        nudges = {
            "context": (
                "[BRD REMINDER] Gather full business context. No guessing. Ask one question at a time. "
                "Start with: what is the core problem, who is the sponsor, what happens if nothing changes. "
                "Then: stakeholders, budget, timeline, existing systems, approval authority. "
                "Use ask_clarification for each question. Do not batch."
            ),
            "objectives": (
                "[BRD REMINDER] Define business objectives with measurable KPIs. "
                "Not 'increase revenue' but 'increase MRR from $50K to $75K in 6 months'. "
                "Every objective needs: current value, target value, timeline, measurement method."
            ),
            "stakeholders": (
                "[BRD REMINDER] Map stakeholders: who cares, who approves, who pays. "
                "For each: role, interest, influence level (H/M/L), concerns, approval needed."
            ),
            "process": (
                "[BRD REMINDER] Map the end-to-end process. Walk through every step. "
                "Who does it, what tool, how long, what information is passed, what breaks. "
                "Create a Mermaid flowchart diagram for the current state (as-is). "
                "Mark pain points. Mark manual steps. Then create the future state (to-be)."
            ),
            "mermaid": (
                "[BRD REMINDER] You must include Mermaid diagrams. Current state AND future state. "
                "Use `mermaid flowchart TD` syntax. Mark pain points and manual steps visually. "
                "Every process flow needs a diagram."
            ),
            "alternatives": (
                "[BRD REMINDER] For each key decision, present real-world alternatives. "
                "At least 2 options plus the 'do nothing' option. Tradeoffs: cost, timeline, risk. "
                "Recommend one and confirm with the user."
            ),
            "scope": (
                "[BRD REMINDER] Define scope boundaries explicitly. What is IN scope? What is OUT? "
                "What is in the gray area (needs a decision)? For each item, state WHY. "
                "Without this, the project will drift."
            ),
            "intention": (
                "[BRD REMINDER] Pause and check alignment. Restate the original intention from Phase 0. "
                "Compare with what you are discussing right now. Are we still on track? "
                "If the user added new requirements, flag them: 'This is new and was not in scope.' "
                "Log all intention changes."
            ),
            "feasibility": (
                "[BRD REMINDER] Assess each feature on 4 dimensions: "
                "Technical (does the tech exist? team skills?), "
                "Operational (can the org absorb change? training needed?), "
                "Financial (within budget? ongoing cost?), "
                "Timeline (can it be delivered by the deadline?). "
                "Rate each: Feasible / Risky / Blocked. State confidence level."
            ),
            "glossary": (
                "[BRD REMINDER] Maintain a glossary of all domain terms and acronyms. "
                "Define every term the first time it appears. Spell out every acronym. "
                "If the user uses a term ambiguously, ask for clarification. "
                "Add terms proactively when you detect potential confusion."
            ),
            "consistency": (
                "[BRD REMINDER] Cross-reference for consistency. Scan all phases: "
                "do any requirements contradict each other? Does the glossary match "
                "all sections? Every requirement must trace back to a business objective. "
                "Nothing should reference a section that does not exist."
            ),
            "requirements": (
                "[BRD REMINDER] Define requirements with traceability. "
                "Business Requirements (BR-xx) describe WHAT the business needs. "
                "Functional Requirements (FR-xx) describe WHAT the system must do. "
                "Non-Functional Requirements (NFR-xx) describe quality targets. "
                "Every requirement must map to a business objective from Phase 0."
            ),
            "quantify": (
                "[BRD REMINDER] Put numbers on it. Costs, benefits, timelines. "
                "Not 'saves time' but 'saves 10 hours/week × $50/hour = $500/week'. "
                "If there is no data, state the assumption and flag uncertainty."
            ),
            "risks": (
                "[BRD REMINDER] Document risks: likelihood (H/M/L), impact, "
                "concrete mitigation action, named owner. Minimum 3 risks. "
                "'Monitor' is not a mitigation."
            ),
            "cost_benefit": (
                "[BRD REMINDER] Quantify costs and benefits. Development, licensing, "
                "operations, training costs. Labor savings, revenue, error reduction. "
                "Calculate ROI, net benefit, payback period."
            ),
            "polish": (
                "[BRD REMINDER] Polish the final output. Executive summary must be 1 page. "
                "All tables consistently formatted. All processes have Mermaid diagrams "
                "(both as-is and to-be). Consistent headings, professional tone, "
                "no contradictions. Ensure the Glossary is complete and the Intention "
                "Changes Log is included if any changes occurred."
            ),
            "recommendation": (
                "[BRD REMINDER] End with a clear specific recommendation. "
                "An executive must be able to say yes or no based on this section alone. "
                "Include: what to do, why, when, how much, and expected return."
            ),
        }
        return HumanMessage(content=nudges.get(reason, ""), additional_kwargs={"hide_from_ui": True})

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        nudges: list[HumanMessage] = []

        clarifications = self._count_clarification_asks(messages)
        context_ok = self._context_answered(messages)
        has_obj = self._has_objectives(messages)
        has_stake = self._has_stakeholders(messages)
        has_mermaid = self._has_mermaid(messages)
        has_scope = self._has_scope(messages)
        has_current = self._has_current_state(messages)
        has_reqs = self._has_requirements(messages)
        has_feas = self._has_feasibility(messages)
        has_glossary = self._has_glossary(messages)
        has_intent = self._has_intention_check(messages)
        has_risks = self._has_risks(messages)
        has_cba = self._has_cost_benefit(messages)
        has_reco = self._has_recommendation(messages)
        has_nums = self._has_numbers(messages)

        # Phase 0 — Continuous context
        if not context_ok:
            nudges.append(self._build_nudge("context"))
            nudges.append(self._build_nudge("stakeholders"))
        else:
            if not has_obj:
                nudges.append(self._build_nudge("objectives"))

        # Phase 1 — Process mapping with Mermaid
        if has_obj and not has_current:
            nudges.append(self._build_nudge("process"))
        if has_current and not has_mermaid:
            nudges.append(self._build_nudge("mermaid"))

        # Phase 2 — Scope
        if has_mermaid and not has_scope:
            nudges.append(self._build_nudge("scope"))

        # Phase 3 — Intention anchoring
        if has_reqs and clarifications > 3 and not has_intent:
            nudges.append(self._build_nudge("intention"))

        # Phase 4 — Feasibility
        if has_reqs and not has_feas:
            nudges.append(self._build_nudge("feasibility"))

        # Phase 5 — Glossary
        if has_current and not has_glossary:
            nudges.append(self._build_nudge("glossary"))

        # Phase 6 — Consistency
        if has_reqs and has_glossary and not has_cba:
            nudges.append(self._build_nudge("consistency"))

        # Quantification
        if has_reqs and not has_nums:
            nudges.append(self._build_nudge("quantify"))

        # Requirements
        if has_current and not has_reqs:
            nudges.append(self._build_nudge("requirements"))

        # Risks
        if has_reqs and not has_risks:
            nudges.append(self._build_nudge("risks"))

        # Cost-benefit
        if has_risks and not has_cba:
            nudges.append(self._build_nudge("cost_benefit"))

        # Polish
        if has_cba and not has_reco:
            nudges.append(self._build_nudge("polish"))

        # Recommendation
        if has_cba and not has_reco:
            nudges.append(self._build_nudge("recommendation"))

        if nudges:
            patched = list(messages)
            insert_at = len(patched)
            for i, msg in enumerate(patched):
                if isinstance(msg, (HumanMessage, AIMessage)):
                    insert_at = i
                    break
            for nudge in reversed(nudges):
                patched.insert(insert_at, nudge)
            request = request.override(messages=patched)

        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        messages = list(request.messages)
        nudges: list[HumanMessage] = []

        clarifications = self._count_clarification_asks(messages)
        context_ok = self._context_answered(messages)
        has_obj = self._has_objectives(messages)
        has_stake = self._has_stakeholders(messages)
        has_mermaid = self._has_mermaid(messages)
        has_scope = self._has_scope(messages)
        has_current = self._has_current_state(messages)
        has_reqs = self._has_requirements(messages)
        has_feas = self._has_feasibility(messages)
        has_glossary = self._has_glossary(messages)
        has_intent = self._has_intention_check(messages)
        has_risks = self._has_risks(messages)
        has_cba = self._has_cost_benefit(messages)
        has_reco = self._has_recommendation(messages)
        has_nums = self._has_numbers(messages)

        if not context_ok:
            nudges.append(self._build_nudge("context"))
            nudges.append(self._build_nudge("stakeholders"))
        else:
            if not has_obj:
                nudges.append(self._build_nudge("objectives"))

        if has_obj and not has_current:
            nudges.append(self._build_nudge("process"))
        if has_current and not has_mermaid:
            nudges.append(self._build_nudge("mermaid"))
        if has_mermaid and not has_scope:
            nudges.append(self._build_nudge("scope"))
        if has_reqs and clarifications > 3 and not has_intent:
            nudges.append(self._build_nudge("intention"))
        if has_reqs and not has_feas:
            nudges.append(self._build_nudge("feasibility"))
        if has_current and not has_glossary:
            nudges.append(self._build_nudge("glossary"))
        if has_reqs and has_glossary and not has_cba:
            nudges.append(self._build_nudge("consistency"))
        if has_reqs and not has_nums:
            nudges.append(self._build_nudge("quantify"))
        if has_current and not has_reqs:
            nudges.append(self._build_nudge("requirements"))
        if has_reqs and not has_risks:
            nudges.append(self._build_nudge("risks"))
        if has_risks and not has_cba:
            nudges.append(self._build_nudge("cost_benefit"))
        if has_cba and not has_reco:
            nudges.append(self._build_nudge("polish"))
        if has_cba and not has_reco:
            nudges.append(self._build_nudge("recommendation"))

        if nudges:
            patched = list(messages)
            insert_at = len(patched)
            for i, msg in enumerate(patched):
                if isinstance(msg, (HumanMessage, AIMessage)):
                    insert_at = i
                    break
            for nudge in reversed(nudges):
                patched.insert(insert_at, nudge)
            request = request.override(messages=patched)

        return await handler(request)
