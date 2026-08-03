"""Deterministic gate middleware for the code-review skill.

Enforces the 5-phase code review contract from the code-review SKILL.md
in code. Tracks continuous context discovery, codebase indexing, SonarQube
separation, iterative logic review with confirmation, and report compilation.

Phases enforced:
  Phase 0: Continuous context discovery — keep asking, never stop
  Phase 1: Codebase indexed (dir tree + functions/classes)
  Phase 2: SonarQube separated from logic (syntax ≠ correctness)
  Phase 3: Every logic finding confirmed with user before proceeding
  Phase 4: Report compiled with clear separation + verdict
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

# ── Phase names ──

PHASE_CONTEXT = "context"
PHASE_INDEX = "index"
PHASE_SONAR = "sonarqube"
PHASE_LOGIC = "logic"
PHASE_REPORT = "report"

# ── Minimum thresholds ──

MIN_CLARIFICATION_ASKS = 2
MIN_CONTEXT_SIGNALS = 2
MIN_INDEX_SIGNALS = 1
MIN_FINDING_SIGNALS = 1
MIN_REPORT_SIGNALS = 2


class CodeReviewMiddleware(AgentMiddleware[AgentState]):
    """Enforce code review phases deterministically.

    Continuously nudges the model to ask questions, confirm findings,
    separate SonarQube syntax from AI logic, and compile a structured report.
    """

    # ── Detection helpers ──

    @staticmethod
    def _context_answered(messages: list) -> bool:
        """Detect if user has answered context questions (Phase 0)."""
        signals = [
            "language", "framework", "library", "proprietary",
            "new code", "bug fix", "refactor",
            "hobby", "production", "enterprise", "critical",
            "team", "maintain", "scale",
            "script", "service", "mission",
        ]
        # Scoped to the recent exchange: old context from a previous topic must
        # not permanently satisfy the gate (re-arming behavior).
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
    def _has_codebase_index(messages: list) -> bool:
        """Check if codebase has been indexed (dir tree + functions)."""
        indicators = [
            "Codebase Map", "Project Structure", "Directory Structure",
            "├── ", "└── ",
            "Key Functions", "Function/Class Index",
            "Dependency Graph", "External Dependencies",
        ]
        for msg in messages[-10:]:
            content = str(getattr(msg, "content", "") or "")
            score = sum(1 for i in indicators if i.lower() in content.lower())
            if score >= MIN_INDEX_SIGNALS:
                return True
        return False

    @staticmethod
    def _has_sonarqube_section(messages: list) -> bool:
        """Check if SonarQube findings are separated from logic findings."""
        sonar_signals = [
            "sonarqube", "static analysis", "code smells",
            "syntax only", "code conventions",
        ]
        separation_signals = [
            "logic review", "correctness", "architecture",
        ]
        for msg in messages[-6:]:
            content = str(getattr(msg, "content", "") or "").lower()
            sonar_score = sum(1 for s in sonar_signals if s in content)
            logic_score = sum(1 for s in separation_signals if s in content)
            if sonar_score >= 1 and logic_score >= 1:
                return True
        return False

    @staticmethod
    def _has_findings(messages: list) -> bool:
        """Check if structured findings exist."""
        for msg in messages[-6:]:
            content = str(getattr(msg, "content", "") or "")
            if "Severity" in content and ("critical" in content.lower() or "major" in content.lower()):
                return True
        return False

    @staticmethod
    def _has_verdict(messages: list) -> bool:
        """Check if report ends with verdict."""
        indicators = [
            "Overall Assessment", "verdict",
            "merge as-is", "minor changes", "blocked",
            "What Went Well",
        ]
        for msg in messages[-4:]:
            content = str(getattr(msg, "content", "") or "")
            score = sum(1 for i in indicators if i.lower() in content.lower())
            if score >= MIN_REPORT_SIGNALS:
                return True
        return False

    @staticmethod
    def _count_clarification_asks(messages: list) -> int:
        """Count ask_clarification tool calls."""
        count = 0
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            for tc in getattr(msg, "tool_calls", None) or []:
                if isinstance(tc, dict) and tc.get("name") == "ask_clarification":
                    count += 1
        return count

    @staticmethod
    def _recent_ai_text(messages: list, lookback: int = 4) -> str:
        """Get concatenated recent AI response text for signal scanning."""
        recent = ""
        for msg in messages[-lookback:]:
            if not isinstance(msg, AIMessage):
                continue
            recent += str(getattr(msg, "content", "") or "") + " "
        return recent

    @staticmethod
    def _user_answered_recently(messages: list, lookback: int = 3) -> bool:
        """Check if user responded to a recent question."""
        for msg in messages[-lookback:]:
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").strip()
            if len(content) > 5:
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
    def _uses_sonarqube_tool(messages: list) -> bool:
        """Check if SonarQube is being used."""
        for msg in messages[-8:]:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if "sonarqube" in content:
                return True
            for tc in getattr(msg, "tool_calls", None) or []:
                if isinstance(tc, dict) and "sonar" in str(tc.get("name", "")).lower():
                    return True
        return False

    # ── Nudge builder ──

    def _build_nudge(self, reason: str, extra: str = "") -> HumanMessage:
        nudges = {
            "context": (
                "[CODE REVIEW] Ask the user about this code. What language? What framework? "
                "What libs? Is this new code or a fix? Who maintains it? How strict should "
                "I be? Start with 1-2 questions. If the user cannot answer, inspect the code "
                "directly: check file extensions, read package.json/requirements.txt/go.mod, "
                "grep for imports. Use ask_clarification to confirm."
            ),
            "context_continue": (
                "[CODE REVIEW] Keep asking. What proprietary libs or internal dependencies "
                "does this code use? Are there tests? Is there a CI/CD pipeline? Is there "
                "anything you are unsure about that the user can clarify? Use ask_clarification."
            ),
            "index": (
                "[CODE REVIEW] Index the codebase. Walk the directory tree with ls -R or "
                "individual ls calls. Read the key files. Map out the project structure, "
                "key functions and classes, and their purposes. Build a dependency graph. "
                "Note any proprietary or internal dependencies you cannot verify. "
                "Output a structured codebase map."
            ),
            "inspect": (
                "[CODE REVIEW] The user may not know the tech details. Figure them out "
                "yourself. Read the project's package manager file. Check file extensions. "
                "Search for imports. Look for test files. Look for CI/CD configs. "
                "Use bash ls, read_file, and grep to discover what you need."
            ),
            "wait": (
                "[CODE REVIEW] The user has not answered your last question yet. "
                "Do NOT guess the code context or continue on assumptions — wait "
                "for their answer, then ask the next question."
            ),
            "sonarqube": (
                "[CODE REVIEW] SonarQube findings are syntax/style ONLY — not logic bugs. "
                "Keep them in a separate section labeled 'Static Analysis (SonarQube)'. "
                "For each SonarQube finding, ask the user: 'Report this or skip it?' "
                "AI logic findings (correctness, architecture, security, edge cases) go in "
                "a separate 'Logic Review' section."
            ),
            "confirm": (
                "[CODE REVIEW] Before writing this finding into the report, confirm with "
                "the user. Use ask_clarification: show the code snippet, explain why you "
                "think it is wrong, and ask 'Is this intentional?' Do not batch questions. "
                "One finding → one confirmation → move to next."
            ),
            "severity": (
                "[CODE REVIEW] Every finding needs a severity. Critical = production outage "
                "or security breach. Major = bugs under specific conditions. Minor = readability "
                "or maintainability. Suggestion = optional improvement. Scale strictness based "
                "on what you learned: hobby → skip minor+suggestion, enterprise → report all."
            ),
            "report": (
                "[CODE REVIEW] Compile the final report. Include: scope, static analysis "
                "section (SonarQube), logic review section (AI findings by severity), "
                "what went well, and a clear verdict: merge as-is / minor changes / blocked. "
                "Present the report to the user for final review."
            ),
            "proprietary": (
                "[CODE REVIEW] You found imports or dependencies you cannot verify. "
                "Flag them: 'I found {module}. Is this a proprietary/internal library? "
                "If yes, I cannot review its behavior. If no, what is it?' "
                "Use ask_clarification to confirm."
            ),
        }
        content = nudges.get(reason, "")
        if extra and reason == "proprietary":
            content = content.format(module=extra)
        return HumanMessage(content=content, additional_kwargs={"hide_from_ui": True})

    # ── Lifecycle hooks ──

    @staticmethod
    def _log_nudges(nudges: list[HumanMessage]) -> None:
        """Log every injected nudge for observability."""
        for nudge in nudges:
            logger.info("CodeReviewMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        nudges: list[HumanMessage] = []

        context_ok = self._context_answered(messages)
        has_index = self._has_codebase_index(messages)
        has_sonarqube = self._has_sonarqube_section(messages)
        has_findings = self._has_findings(messages)
        has_verdict = self._has_verdict(messages)
        clarifications = self._count_clarification_asks(messages)
        user_replied = self._user_answered_recently(messages)
        uses_sonar = self._uses_sonarqube_tool(messages)

        # Phase 0 — Continuous context: keep asking until we have enough signals
        # Continuous context
        if not context_ok:
            if self._user_replied_after_last_ask(messages):
                await_nudge = "[CODE REVIEW] Build context first. Inspect the codebase structure, "
                "file types, and package manager to determine language, framework, and dependencies. "
                "Then use ask_clarification to confirm with user."

                nudges.append(HumanMessage(content=await_nudge, additional_kwargs={"hide_from_ui": True}))

                # Context incomplete
                nudges.append(self._build_nudge("context"))
                nudges.append(self._build_nudge("inspect"))
            else:
                nudges.append(self._build_nudge("wait"))
        else:
            if user_replied and clarifications < 5:
                nudges.append(self._build_nudge("context_continue"))

        if context_ok and not has_index:
            nudges.append(self._build_nudge("index"))

        if has_index and uses_sonar and not has_sonarqube:
            nudges.append(self._build_nudge("sonarqube"))

        if has_index and not has_findings:
            nudges.append(self._build_nudge("confirm"))

        if has_findings and not has_verdict:
            nudges.append(self._build_nudge("severity"))

        # Phase 4 — Report completeness
        if has_findings and clarifications >= MIN_CLARIFICATION_ASKS and not has_verdict:
            nudges.append(self._build_nudge("report"))

        # Inject nudges
        if nudges:
            patched = list(messages)
            insert_at = len(patched)
            for i, msg in enumerate(patched):
                if isinstance(msg, (HumanMessage, AIMessage)):
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
        messages = list(request.messages)
        nudges: list[HumanMessage] = []

        context_ok = self._context_answered(messages)
        has_index = self._has_codebase_index(messages)
        has_sonarqube = self._has_sonarqube_section(messages)
        has_findings = self._has_findings(messages)
        has_verdict = self._has_verdict(messages)
        clarifications = self._count_clarification_asks(messages)
        user_replied = self._user_answered_recently(messages)
        uses_sonar = self._uses_sonarqube_tool(messages)

        # Continuous context
        if not context_ok:
            if self._user_replied_after_last_ask(messages):
                await_nudge = "[CODE REVIEW] Build context first. Inspect the codebase structure, "
                "file types, and package manager to determine language, framework, and dependencies. "
                "Then use ask_clarification to confirm with user."

                nudges.append(HumanMessage(content=await_nudge, additional_kwargs={"hide_from_ui": True}))

                # Context incomplete
                nudges.append(self._build_nudge("context"))
                nudges.append(self._build_nudge("inspect"))
            else:
                nudges.append(self._build_nudge("wait"))
        else:
            if user_replied and clarifications < 5:
                nudges.append(self._build_nudge("context_continue"))

        if context_ok and not has_index:
            nudges.append(self._build_nudge("index"))

        if has_index and uses_sonar and not has_sonarqube:
            nudges.append(self._build_nudge("sonarqube"))

        if has_index and not has_findings:
            nudges.append(self._build_nudge("confirm"))

        if has_findings and not has_verdict:
            nudges.append(self._build_nudge("severity"))

        if has_findings and clarifications >= MIN_CLARIFICATION_ASKS and not has_verdict:
            nudges.append(self._build_nudge("report"))

        if nudges:
            patched = list(messages)
            insert_at = len(patched)
            for i, msg in enumerate(patched):
                if isinstance(msg, (HumanMessage, AIMessage)):
                    insert_at = i
                    break
            for nudge in reversed(nudges):
                patched.insert(insert_at, nudge)
            self._log_nudges(nudges)
            request = request.override(messages=patched)

        return await handler(request)
