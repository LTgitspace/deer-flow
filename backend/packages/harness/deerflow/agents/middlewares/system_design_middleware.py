"""Deterministic gate middleware for the system-design skill.

Enforces the lane-based system design contract from the system-design
SKILL.md in code. This is NOT a prompt — it nudges, counts, and validates
regardless of what the model decides to do.

Contract enforced (per user requirements):
  Phase 0: Grounded intake first — interview the user ONE question at a time
    via ask_clarification (no batching) until three pillars are recorded:
    user wanting (goal, must-haves, priorities), constraints (budget,
    timeline, platform, stack, team), and sizing (scale, deployment
    target). Then classify Lane A/B/C.
  Phase 0.5: System reality — inspect the existing system (files, code,
    config) before designing, unless the user states the project is
    greenfield. Unanswered intake items must be recorded as UNKNOWN.
  Phase 1: Requirements (goal, FR, NFR, constraints) before architecture.
  Phase 2: Architecture must be a mermaid diagram, not ASCII art, and must
    include a component decomposition table + communication patterns.
    Present it and get user approval before continuing.
  Phase 3-4: Storage choices, component interactions, and system-level data
    flow. Implementation details (entity schemas, endpoint signatures,
    concurrency internals) trigger a scope-correction nudge.
  Phase 5: Deployment topology per lane; tradeoffs, risks, and a numbered
    Build Order are mandatory.
  Grounding: later phases require explicit UNKNOWN/assumption marking and a
    requirement-to-decision Traceability table.
  Chaining: when upstream pipeline documents (BRD/PRD/SRS) exist in the
    thread, their documented facts satisfy the intake pillars and greenfield
    statements — the interview only asks for what the chain has not recorded.
  Lane consistency: a personal/local design must not reference
    Kubernetes/microservices/sharding.

Design notes:
  - Nudges are hidden HumanMessages (hide_from_ui) injected before the
    model call — the model self-corrects without a hard rejection loop.
  - All state is derived from message history; no custom_data writes.
  - Enforcement is scoped: it only activates when the conversation is
    design-shaped (trigger words in the latest user message).
  - Forced context gate: even when design-shaped, the contract only fires
    once the system-design skill is active in the thread (slash-activated or
    loaded into skill_context). Shaped-but-inactive conversations get a
    single activation nudge instead.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.agents.middlewares.skill_context import skill_is_active

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

# Skill directory name this middleware enforces. The gate only fires when this
# skill is active in the thread (slash-activated or loaded into skill_context).
_SKILL_NAME = "system-design"

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
    "What are the top 3 must-have capabilities, in priority order?",
    "How many users, and where does it run (personal machine / VPS / cluster)?",
    "What is the budget and timeline?",
    "What platform and stack constraints exist (OS, frameworks, existing systems)?",
    "Are there team or compliance constraints (solo / team, legal, security)?",
)

# Pillar 1 — user wanting: goals, must-haves, priorities (interview intake).
_WANTING_SIGNALS = (
    "goal", "problem", "must-have", "must have", "priority", "want", "need it",
    "success", "purpose",
)

# Pillar 2 — constraints: budget, timeline, platform, stack, team (interview intake).
_CONSTRAINT_SIGNALS = (
    "budget", "timeline", "deadline", "month", "week", "cost", "platform",
    "windows", "linux", "macos", "stack", "framework", "team", "solo",
    "constraint", "compliance", "existing",
)

# Greenfield statements that waive the system-reality inspection gate.
_GREENFIELD_SIGNALS = (
    "from scratch", "greenfield", "brand new", "new system", "nothing exists",
    "no existing", "empty repo",
)

# Upstream pipeline documents (BRD/PRD/SRS) that count as grounded intake
# evidence when chaining BRD -> PRD -> SRS -> system-design.
_CHAIN_DOC_MARKERS = (
    "business requirement", "# brd", "business objectives", "# prd", "product vision",
    "software requirements specification", "| requirement id |", "data dictionary",
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

    def _count_clarification_asks(self, messages: list) -> int:
        """Count ask_clarification tool calls in the recent exchange (drives the
        one-question-at-a-time sequence)."""
        count = 0
        for msg in messages[-12:]:
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                if any("clarif" in (tc.get("name", "") or "") for tc in msg.tool_calls):
                    count += 1
        return count

    @staticmethod
    def _signals_answered(messages: list, signals: tuple, threshold: int, lookback: int = 12) -> bool:
        """True when a recent visible user message contains >= threshold pillar signals.

        Scoped to the last `lookback` messages so context from a previous topic
        does not permanently satisfy the gate (re-arming behavior).
        """
        for msg in reversed(messages[-lookback:]):
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if sum(1 for s in signals if s in content) >= threshold:
                return True
        return False

    def _context_answered(self, messages: list) -> bool:
        """Sizing pillar: scale and deployment target recorded."""
        return self._signals_answered(messages, _DESIGN_CONTEXT_SIGNALS, 3)

    def _wanting_answered(self, messages: list) -> bool:
        """User-wanting pillar: goal, must-haves, priorities recorded."""
        return self._signals_answered(messages, _WANTING_SIGNALS, 2)

    def _constraints_answered(self, messages: list) -> bool:
        """Constraints pillar: budget, timeline, platform, stack, team recorded."""
        return self._signals_answered(messages, _CONSTRAINT_SIGNALS, 2)

    def _chain_doc_content(self, messages: list, lookback: int = 16) -> str:
        """AI text from upstream pipeline documents (BRD/PRD/SRS) in the thread.

        When chaining, documented facts satisfy the intake pillars instead of
        re-interviewing the user for what the chain already recorded.
        """
        chunks: list[str] = []
        for msg in reversed(messages[-lookback:]):
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if any(m in content for m in _CHAIN_DOC_MARKERS):
                chunks.append(content)
        return "\n".join(chunks)

    def _pillar_from_chain_docs(self, messages: list, signals: tuple, threshold: int) -> bool:
        content = self._chain_doc_content(messages)
        return sum(1 for s in signals if s in content) >= threshold

    def _intake_answered(self, messages: list) -> bool:
        """All three intake pillars recorded, via the interview or upstream chain docs."""
        if (
            self._context_answered(messages)
            and self._wanting_answered(messages)
            and self._constraints_answered(messages)
        ):
            return True
        return (
            self._pillar_from_chain_docs(messages, _WANTING_SIGNALS, 2)
            and self._pillar_from_chain_docs(messages, _CONSTRAINT_SIGNALS, 2)
            and self._pillar_from_chain_docs(messages, _DESIGN_CONTEXT_SIGNALS, 3)
        )

    def _reality_inspected(self, messages: list) -> bool:
        """True when the model has inspected the actual system (files, dirs, code)."""
        for msg in messages:
            if not isinstance(msg, ToolMessage):
                continue
            name = str(getattr(msg, "name", "") or "").lower()
            if any(t in name for t in ("read_file", "list", "search_code", "code_search", "grep", "find")):
                return True
        return False

    def _greenfield_stated(self, messages: list) -> bool:
        """True when the user or an upstream chain document stated greenfield."""
        for msg in reversed(messages[-12:]):
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                content = str(getattr(msg, "content", "") or "").lower()
                if any(s in content for s in _GREENFIELD_SIGNALS):
                    return True
        return any(s in self._chain_doc_content(messages) for s in _GREENFIELD_SIGNALS)

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

    def _has_unknowns_marked(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "unknown" in c or "assumption" in c

    def _has_traceability(self, messages: list) -> bool:
        c = self._ai_content(messages)
        return "traceability" in c or "| requirement" in c or "requirement id" in c

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

        # Phase 0 — grounded intake (wanting + constraints + sizing): one question at a time.
        if not self._intake_answered(messages):
            # Wait-gate: do not advance the question sequence while the user
            # has not answered the current question.
            if not self._user_replied_after_last_ask(messages):
                return [
                    self._nudge(
                        "[SYSTEM REMINDER] The user has not answered your last sizing question yet. "
                        "Do NOT guess their answers or proceed with the design — wait for their "
                        "reply, then ask the next question."
                    )
                ]
            asks = self._count_clarification_asks(messages)
            question = _QUESTION_SEQUENCE[min(asks, len(_QUESTION_SEQUENCE) - 1)]
            return [
                self._nudge(
                    "[SYSTEM REMINDER] Grounded intake is incomplete. No guessing. Ask ONE question at "
                    "a time via ask_clarification — do not batch questions. "
                    f"Next question: {question} Keep asking until all three pillars are recorded: "
                    "user wanting (goal, must-haves, priorities), constraints (budget, timeline, "
                    "platform, stack, team), and sizing (scale, deployment target). If the user "
                    "cannot answer a pillar, record it as UNKNOWN — never invent it."
                )
            ]

        # Phase 0.5 — system reality: inspect the existing system before designing.
        if not self._reality_inspected(messages) and not self._greenfield_stated(messages):
            return [
                self._nudge(
                    "[SYSTEM REMINDER] The system's reality has not been inspected. If an existing "
                    "codebase, environment, or prior design exists, examine it first (read_file, "
                    "list directories, search code) so the architecture reflects what is real. If "
                    "this is greenfield, the user must state it explicitly — never assume."
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

        # Grounding — unanswered intake items must be marked, not invented.
        if self._has_tradeoffs(messages) and not self._has_unknowns_marked(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Mark every unanswered intake item explicitly as UNKNOWN or as a "
                    "stated assumption. Silent invention of scale, budget, or stack facts is not allowed."
                )
            )

        # Traceability — every decision must cite the requirement and constraint it serves.
        if self._has_tradeoffs(messages) and not self._has_traceability(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Add a Traceability section mapping each architecture decision to "
                    "the requirement and constraint it serves "
                    "(| decision | requirement | constraint | component |)."
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

        state = getattr(request, "state", None) or {}
        if not skill_is_active(messages, state, _SKILL_NAME):
            # Inactive-skill fast exit: do NOT inject an activation nudge on
            # casual queries that merely contain design-shaped words. The
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
        if not self._is_design_shaped(messages):
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
