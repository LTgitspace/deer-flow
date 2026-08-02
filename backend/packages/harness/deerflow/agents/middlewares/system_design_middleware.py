"""Deterministic gate middleware for the system-design skill.

Enforces the lane-based system design contract from the system-design
SKILL.md in code. This is NOT a prompt — it nudges, counts, and validates
regardless of what the model decides to do.

Contract enforced (per user requirements):
  Phase 0: Sizing checkpoint first — BRD-style context discovery: ask ONE
    question at a time via ask_clarification (no batching) until the user's
    answers contain >= 3 context signals (scale, deployment target, budget,
    stack). Then classify Lane A/B/C.
  Phase 1: Requirements (goal, FR, NFR, constraints) before architecture.
  Phase 2: Architecture must be a mermaid diagram, not ASCII art, and must
    include a component decomposition table + communication patterns.
    Present it and get user approval before continuing.
  Phase 3-4: Storage choices, component interactions, and system-level data
    flow. Implementation details (entity schemas, endpoint signatures,
    concurrency internals) trigger a scope-correction nudge.
  Phase 5: Deployment topology per lane; tradeoffs, risks, and a numbered
    Build Order are mandatory.
  Lane consistency: a personal/local design must not reference
    Kubernetes/microservices/sharding.

Design notes:
  - Nudges are hidden HumanMessages (hide_from_ui) injected before the
    model call — the model self-corrects without a hard rejection loop.
  - All state is derived from message history; no custom_data writes.
  - Enforcement is scoped: it only activates when the conversation is
    design-shaped (trigger words in the latest user message).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

MAX_NUDGES_PER_CALL = 2

# ── Evidence thresholds (Phase 1.5) ──

MIN_DESIGN_SEARCHES = 4
MIN_DESIGN_FETCHES = 2

_DESIGN_TRIGGERS = (
    "design",
    "architecture",
    "technical design",
    "architecture review",
    "how to build",
    "build a",
    "blueprint",
    "design doc",
)

# Lane A signals from the user (personal/local).
_LANE_A_SIGNALS = (
    "just me",
    "only me",
    "myself",
    "personal",
    "local",
    "single machine",
    "my machine",
    "one machine",
    "side project",
    "home",
)

# Lane B/C signals that move the design up a lane.
_LANE_BC_SIGNALS = (
    "team",
    "self-host",
    "vps",
    "server",
    "docker",
    "internal",
    "company",
    "colleagues",
    "few users",
    "million",
    "scale",
    "public",
    "global",
    "high traffic",
    "production",
)

# Generic lane signals and the one-question-at-a-time sequence (BRD-style
# context discovery: keep asking until a user message matches >= 3 signals).
_DESIGN_CONTEXT_SIGNALS = (
    "user", "users", "personal", "local", "team", "self-host", "vps",
    "server", "machine", "scale", "deploy", "budget", "timeline",
    "month", "stack", "framework", "existing", "constraint", "api",
    "database", "web", "mobile", "desktop",
)

_QUESTION_SEQUENCE = (
    "What is the core problem this system solves, and who uses it?",
    "How many users, and where does it run (personal machine / VPS / cluster)?",
    "What is the budget and timeline?",
    "Are there stack constraints or existing systems to integrate with?",
    "What are the must-have capabilities (top 3)?",
)

# Scale-out vocabulary that must never appear in a Lane A design.
_LANE_A_FORBIDDEN = ("kubernetes", "k8s", "microservice", "sharding", "helm", "autoscaling")

# Implementation-level markers that do not belong in a high-level architecture
# document (the scope-correction guard).
_IMPLEMENTATION_MARKERS = (
    "create table",
    "password_hash",
    "next_cursor",
    "cursor-based",
    "thread pool",
    "worker pool",
    "backpressure",
    "uuid (pk)",
)


class SystemDesignMiddleware(AgentMiddleware[AgentState]):
    """Enforce the lane-based system design contract deterministically."""

    # ── History-derived state ──

    def _latest_user_message(self, messages: list) -> HumanMessage | None:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return msg
        return None

    def _is_design_shaped(self, messages: list) -> bool:
        latest = self._latest_user_message(messages)
        if latest is None:
            return False
        content = str(getattr(latest, "content", "") or "").lower()
        return any(t in content for t in _DESIGN_TRIGGERS)

    @staticmethod
    def _count_clarification_asks(messages: list) -> int:
        """Count ask_clarification tool calls made by the model."""
        count = 0
        for msg in messages:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                if any("clarif" in (tc.get("name", "") or "") for tc in msg.tool_calls):
                    count += 1
        return count

    def _context_answered(self, messages: list) -> bool:
        """True when a user message contains >= 3 design-context signals."""
        for msg in reversed(messages):
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if sum(1 for s in _DESIGN_CONTEXT_SIGNALS if s in content) >= 3:
                return True
        return False

    def _lane_a_confirmed(self, messages: list) -> bool:
        """True when the user clearly described a personal/local system."""
        for msg in reversed(messages):
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if any(s in content for s in _LANE_A_SIGNALS):
                return True
        return False

    def _tool_counts(self, messages: list) -> tuple[int, int, set[str]]:
        """Return (search_count, fetch_count, unique_query_fingerprints)."""
        search_count = 0
        fetch_count = 0
        queries: set[str] = set()

        tool_calls_by_id: dict[str, tuple[str, dict]] = {}
        for msg in messages:
            if isinstance(msg, AIMessage):
                for tc in getattr(msg, "tool_calls", None) or []:
                    tool_calls_by_id[tc.get("id")] = (tc.get("name", ""), tc.get("args", {}) or {})

        for msg in messages:
            if not isinstance(msg, ToolMessage):
                continue
            name = getattr(msg, "name", "") or ""
            if "search" in name:
                search_count += 1
            elif "fetch" in name:
                fetch_count += 1
            else:
                continue
            query = ""
            tc = tool_calls_by_id.get(getattr(msg, "tool_call_id", None))
            if tc:
                for key in ("query", "input", "q", "url"):
                    val = tc[1].get(key)
                    if isinstance(val, str) and val.strip():
                        query = val
                        break
            if not query:
                query = str(getattr(msg, "content", "") or "")[:100]
            query = " ".join(query.split()).strip().lower()
            if query:
                queries.add(query)
        return search_count, fetch_count, queries

    def _has_citations(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "http://" in c or "https://" in c or "](" in c and "http" in c

    @staticmethod
    def _ai_content(messages: list, lookback: int = 8) -> str:
        chunks: list[str] = []
        for msg in reversed(messages[-lookback:]):
            if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                chunks.append(str(getattr(msg, "content", "") or "").lower())
        return "\n".join(chunks)

    def _has_requirements(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(m in c for m in ("## functional requirements", "## non-functional requirements", "## scope"))

    def _has_mermaid(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(m in c for m in ("```mermaid", "graph td", "graph lr", "flowchart", "sequencediagram"))

    def _has_components(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "component responsibilities" in c or "| component |" in c

    def _has_storage(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(m in c for m in ("storage", "data store", "database"))

    def _has_interactions(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(m in c for m in ("communication", "interaction", "protocol", "sync", "async"))

    def _has_implementation_leak(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(m in c for m in _IMPLEMENTATION_MARKERS)

    def _has_dataflow(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "write path" in c or "read path" in c or "data flow" in c

    def _has_deployment(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return any(m in c for m in ("deployment", "topology", "start.bat", "docker", "systemd", "kubernetes", "nginx", "vps", "cluster"))

    def _has_tradeoffs(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "tradeoff" in c or "build order" in c or ("| risk |" in c)

    def _ai_question_recent(self, messages: list, lookback: int = 4) -> bool:
        """True if the model recently asked the user a question."""
        for msg in reversed(messages[-lookback:]):
            if not isinstance(msg, AIMessage):
                continue
            if getattr(msg, "tool_calls", None):
                if any("clarif" in (tc.get("name", "") or "") for tc in msg.tool_calls):
                    return True
                continue
            content = str(getattr(msg, "content", "") or "").strip()
            if content and content.endswith("?") and len(content) < 600:
                return True
        return False

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list) -> list[HumanMessage]:
        nudges: list[HumanMessage] = []

        # Phase 0 — sizing checkpoint, BRD-style: one question at a time.
        if not self._context_answered(messages):
            asks = self._count_clarification_asks(messages)
            question = _QUESTION_SEQUENCE[min(asks, len(_QUESTION_SEQUENCE) - 1)]
            return [
                self._nudge(
                    "[SYSTEM REMINDER] Gather full design context. No guessing. Ask ONE question at "
                    "a time via ask_clarification — do not batch questions. "
                    f"Next question: {question} Keep asking until you have: scale, deployment "
                    "target, budget/timeline, and stack constraints. If the user cannot answer, "
                    "default to Lane A (local/personal) and state the assumption explicitly."
                )
            ]

        # Phase 1 — requirements before architecture.
        if not self._has_requirements(messages):
            return [
                self._nudge(
                    "[SYSTEM REMINDER] Requirements are not established yet. Produce: Goal, Lane, "
                    "Functional Requirements, Non-Functional Requirements (lane-appropriate), and Constraints. "
                    "Do NOT draw architecture before requirements exist."
                )
            ]

        # Phase 1.5 — evidence gathering before architecture.
        search_count, fetch_count, unique_queries = self._tool_counts(messages)
        if search_count < MIN_DESIGN_SEARCHES or fetch_count < MIN_DESIGN_FETCHES:
            return [
                self._nudge(
                    "[SYSTEM REMINDER] Before designing the architecture, gather validated evidence: "
                    f"search for best practices / official guidelines for the chosen stack, reference "
                    f"architectures and case studies of similar systems, and benchmarks for key decisions "
                    f"(so far: {search_count}/{MIN_DESIGN_SEARCHES} searches, {fetch_count}/"
                    f"{MIN_DESIGN_FETCHES} full-source fetches, {len(unique_queries)} unique angles). "
                    "Never invent a practice nobody has confirmed — every non-obvious decision must "
                    "cite a source."
                )
            ]

        # Phase 2 — mermaid-first architecture.
        if not self._has_mermaid(messages):
            return [
                self._nudge(
                    "[SYSTEM REMINDER] The architecture must be a mermaid diagram (```mermaid ... ``` code "
                    "block), not ASCII art. Show components, data stores, and communication arrows."
                )
            ]
        if not self._has_components(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Add the Component Decomposition table: component, responsibility, "
                    "communicates via (protocol, sync/async), and scaling strategy."
                )
            )

        # Scope guard — implementation details do not belong here. Takes
        # priority: a document drifting to implementation level must be
        # corrected before missing-section nudges accumulate.
        if self._has_components(messages) and self._has_implementation_leak(messages):
            nudges.insert(
                0,
                self._nudge(
                    "[SYSTEM REMINDER] The document is drifting into implementation details (entity "
                    "schemas, endpoint signatures, concurrency internals). Keep it high-level: components, "
                    "responsibilities, interactions, data flow. Defer implementation specifics to a "
                    "follow-up technical spec."
                ),
            )

        # Phase 2 gate — get user approval before detailing components.
        if not self._ai_question_recent(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Present the high-level architecture to the user and ask for approval "
                    "before detailing components (skill gate: high-level architecture approved)."
                )
            )

        # Phase 3 — storage choices at the system level.
        if not self._has_storage(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Define storage at the system level: what each data store holds and "
                    "the technology choice per lane (SQLite / PostgreSQL / object storage) with rationale. "
                    "Do NOT write entity field schemas — that is implementation detail."
                )
            )

        # Phase 3 — component interactions (high level).
        if not self._has_interactions(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Describe how components interact: for each link, the mechanism "
                    "(sync HTTP/gRPC vs async queue/events). Stay at the architecture level — no "
                    "endpoint-level definitions."
                )
            )

        # Phase 3 — system-level data flow.
        if not self._has_dataflow(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Trace the system-level flows: write path, read path, and async path "
                    "through the components, and where consistency matters between them."
                )
            )

        # Phase 4 — deployment topology per lane.
        if not self._has_deployment(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Document the deployment topology per lane: where each component "
                    "runs (single machine / VPS / cluster), startup, backup, and monitoring at the "
                    "architecture level."
                )
            )

        # Scope guard — implementation details do not belong here.
        if self._has_components(messages) and self._has_implementation_leak(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] The document is drifting into implementation details (entity "
                    "schemas, endpoint signatures, concurrency internals). Keep it high-level: components, "
                    "responsibilities, interactions, data flow. Defer implementation specifics to a "
                    "follow-up technical spec."
                )
            )


        # Phase 5 — tradeoffs, risks, build order (architecture level).
        if not self._has_tradeoffs(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Finish with architecture-level Tradeoff and Risk tables "
                    "(decision / rationale / alternative / why not) and a numbered Build Order. "
                    "A design without a build order is not complete."
                )
            )

        # Citations — key decisions must reference validated sources.
        if self._has_tradeoffs(messages) and not self._has_citations(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] The design document must cite sources for its key decisions "
                    "(links or [n](url) references): architecture style, storage choices, and API "
                    "decisions need validated references from the evidence phase."
                )
            )

        # Lane consistency — Lane A must not reference scale-out vocabulary.
        if self._lane_a_confirmed(messages):
            c = self._ai_content(messages)
            if any(w in c for w in _LANE_A_FORBIDDEN):
                nudges.append(
                    self._nudge(
                        "[SYSTEM REMINDER] Lane mismatch: the user described a personal/local system "
                        "(Lane A), but the design references Kubernetes/microservices/sharding. "
                        "Re-scope to Lane A depth: single machine, processes, no cluster."
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
            logger.info("SystemDesignMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        if not self._is_design_shaped(messages):
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
        if not self._is_design_shaped(messages):
            return await handler(request)

        nudges = self._build_nudges(messages)
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
