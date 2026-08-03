"""Deterministic gate middleware for the deep-research skill.

Enforces the research contract from the deep-research SKILL.md in code.
This is NOT a prompt — it nudges, counts, and validates regardless of
what the model decides to do.

Contract enforced (per user requirements):
  1. Before any research, the model must ask the user at least 3
     clarification questions (goal/scope, constraints, depth/format).
  2. If the user's answers are thin, ask 1-2 follow-ups. Keep asking
     while context is genuinely insufficient.
  3. No guessing: the model must search before answering; never
     synthesize from general knowledge alone.
  4. Research must use search tools (web_search / search) and full-read
     tools (web_fetch / fetch), not single superficial queries.
  5. Citations are mandatory: final answers must cite numbered source
     links for claims.
  6. Mid-process direction checks: after the first research batch the
     model must pause and ask the user whether the direction is right.

Design notes:
  - Nudges are hidden HumanMessages (hide_from_ui) injected before the
    model call — the model self-corrects without a hard rejection loop.
  - All state is derived from message history; no custom_data writes,
    so the middleware is deterministic across runs and restarts.
  - Enforcement is scoped: it only activates when the conversation is
    research-shaped (research trigger in the latest user message, or
    search/fetch tools already used). Non-research threads are untouched.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)

# ── Minimum thresholds ──

MIN_CLARIFY_QUESTIONS = 3
MIN_SEARCHES = 4
MIN_UNIQUE_ANGLES = 3
MIN_FETCHES = 2
MIDCHECK_AT_SEARCHES = 3
MIDCHECK_2_AT_SEARCHES = 8
FOLLOWUP_IF_ANSWER_SHORTER_THAN = 20  # words
MAX_NUDGES_PER_CALL = 2

# ── Heuristic markers ──

_CITATION_URL_RE = re.compile(r"https?://|\[\d+\]|\[source", re.IGNORECASE)
_RECENCY_INTENT = ("today", "latest", "recent", "this week", "this month", "this year", "breaking", "just released")

_RESEARCH_TRIGGERS = (
    "research",
    "investigate",
    "compare",
    "explain",
    "what is",
    "what are",
    "how does",
    "how do",
    "why",
    "analyze",
    "analysis",
    "deep dive",
    "look up",
    "find out",
    "search",
    "latest",
    "trends",
    "report",
    "article",
    "write about",
    "summary of",
    "study",
    "data on",
)


class DeepResearchMiddleware(AgentMiddleware[AgentState]):
    """Enforce the deep-research contract deterministically."""

    # ── History-derived state ──

    def _latest_user_message(self, messages: list) -> HumanMessage | None:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return msg
        return None

    def _is_research_shaped(self, messages: list) -> bool:
        """True when this conversation is research-shaped.

        Either research tools were already used, or the latest visible
        user message contains a research trigger.
        """
        for msg in messages:
            if isinstance(msg, ToolMessage):
                name = getattr(msg, "name", "") or ""
                if "search" in name or "fetch" in name:
                    return True
        latest = self._latest_user_message(messages)
        if latest is None:
            return False
        content = str(getattr(latest, "content", "") or "").lower()
        return any(t in content for t in _RESEARCH_TRIGGERS)

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
            # Extract the query from the originating tool call when possible.
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
            query = re.sub(r"\s+", " ", query).strip().lower()
            if query:
                queries.add(query)
        return search_count, fetch_count, queries

    def _ai_asked_clarification(self, messages: list, lookback: int = 12) -> bool:
        """True if the model asked a clarification question set in the recent exchange.

        Scoped to the last ``lookback`` messages so old questions from a previous
        topic in a long thread do not permanently satisfy the gate — a new
        research question must get fresh clarification.
        """
        for msg in reversed(messages[-lookback:]):
            if not isinstance(msg, AIMessage):
                continue
            if getattr(msg, "tool_calls", None):
                if any("clarif" in (tc.get("name", "") or "") for tc in msg.tool_calls):
                    return True
            content = str(getattr(msg, "content", "") or "")
            if content.count("?") >= MIN_CLARIFY_QUESTIONS:
                return True
        return False

    def _clarification_answered(self, messages: list) -> bool:
        """True if a visible user message arrived after the clarification ask."""
        ask_index = None
        for i, msg in enumerate(messages):
            if not isinstance(msg, AIMessage):
                continue
            if getattr(msg, "tool_calls", None) and any(
                "clarif" in (tc.get("name", "") or "") for tc in msg.tool_calls
            ):
                ask_index = i
                continue
            content = str(getattr(msg, "content", "") or "")
            if content.count("?") >= MIN_CLARIFY_QUESTIONS:
                ask_index = i
        if ask_index is None:
            return False
        for msg in messages[ask_index + 1 :]:
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return True
        return False

    def _latest_answer_word_count(self, messages: list) -> int:
        latest = self._latest_user_message(messages)
        if latest is None:
            return 0
        return len(str(getattr(latest, "content", "") or "").split())

    def _ai_question_recent(self, messages: list, lookback: int = 4) -> bool:
        """True if the model recently asked the user a direction question.

        Detects either an ask_clarification tool call or a short AI
        message ending with '?' (a question, not an answer).
        """
        for msg in reversed(messages[-lookback:]):
            if not isinstance(msg, AIMessage):
                continue
            if getattr(msg, "tool_calls", None):
                if any("clarif" in (tc.get("name", "") or "") for tc in msg.tool_calls):
                    return True
                continue  # tool calls without clarification are not questions
            content = str(getattr(msg, "content", "") or "").strip()
            if content and content.endswith("?") and len(content) < 600:
                return True
        return False

    def _last_ai_content(self, messages: list) -> str:
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                return str(getattr(msg, "content", "") or "")
        return ""

    def _has_citations(self, messages: list) -> bool:
        return bool(_CITATION_URL_RE.search(self._last_ai_content(messages)))

    def _has_mermaid(self, messages: list) -> bool:
        content = self._last_ai_content(messages).lower()
        return any(
            marker in content
            for marker in ("mermaid", "graph td", "graph lr", "sequencediagram", "flowchart")
        )

    def _uses_current_year(self, queries: set[str]) -> bool:
        year = str(datetime.now(UTC).year)
        return any(year in q for q in queries)

    def _wants_recency(self, messages: list) -> bool:
        latest = self._latest_user_message(messages)
        if latest is None:
            return False
        content = str(getattr(latest, "content", "") or "").lower()
        return any(token in content for token in _RECENCY_INTENT)

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(
        self,
        *,
        search_count: int,
        fetch_count: int,
        unique_queries: set[str],
        messages: list,
    ) -> list[HumanMessage]:
        nudges: list[HumanMessage] = []

        # Rule 1: clarification first — RE-ARMING gate. Fires until the user has
        # actually answered, even if the model already started searching. One
        # defiant search no longer disarms it.
        if not self._ai_asked_clarification(messages):
            if search_count > 0:
                text = (
                    "[SYSTEM REMINDER] You started searching before clarifying the user's needs. "
                    f"STOP researching and ask the user {MIN_CLARIFY_QUESTIONS} clarification questions via "
                    "ask_clarification: (1) exact goal and scope, (2) key constraints or preferences, "
                    "(3) desired depth and output format. Do not continue until they respond."
                )
            else:
                text = (
                    "[SYSTEM REMINDER] You are about to conduct deep research. "
                    f"Before ANY research, ask the user {MIN_CLARIFY_QUESTIONS} clarification questions via "
                    "ask_clarification: (1) exact goal and scope, (2) key constraints or preferences, "
                    "(3) desired depth and output format. Do not search or answer until they respond."
                )
            nudges.append(self._nudge(text))
            return nudges

        # Wait-gate: the model asked, but the user has not answered yet.
        if not self._clarification_answered(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] You asked clarification questions but the user has not answered "
                    "yet. Do NOT guess their answers or continue researching on assumptions — wait "
                    "for their reply."
                )
            )
            return nudges

        # Rule 2: thin answers → keep asking targeted follow-ups, never guess.
        if (
            search_count == 0
            and self._ai_asked_clarification(messages)
            and self._clarification_answered(messages)
            and self._latest_answer_word_count(messages) < FOLLOWUP_IF_ANSWER_SHORTER_THAN
            and not self._ai_question_recent(messages)
        ):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] The user's clarification answer is brief. "
                    "Ask 1-2 targeted follow-up questions to pin down scope, constraints, "
                    "and output format. Do NOT guess or start researching on assumptions."
                )
            )
            return nudges

        # Rule 4+3: search depth + no guessing.
        if search_count < MIN_SEARCHES:
            if search_count == 0:
                text = (
                    "[SYSTEM REMINDER] Do NOT answer from general knowledge and do NOT guess. "
                    "Use a search tool first (web_search / search). One query is never enough."
                )
            else:
                text = (
                    f"[SYSTEM REMINDER] You have done {search_count} searches. "
                    f"Minimum required before synthesis: {MIN_SEARCHES}. Search from different angles; "
                    "use the ACTUAL current year from <current_date> in time-sensitive queries."
                )
            nudges.append(self._nudge(text))
            return nudges

        # Temporal precision: recency intent must use the current year.
        if self._wants_recency(messages) and not self._uses_current_year(unique_queries):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] The user wants current information, but none of your queries "
                    f"contains the current year ({datetime.now(UTC).year}). Add year (and month/day for "
                    "'today'/'this week' intents) to the next searches."
                )
            )

        # Rule 4: diversity of angles (facts, examples, opinions, trends, comparisons, challenges).
        if len(unique_queries) < MIN_UNIQUE_ANGLES:
            nudges.append(
                self._nudge(
                    f"[SYSTEM REMINDER] Only {len(unique_queries)} distinct query angles so far; "
                    f"minimum is {MIN_UNIQUE_ANGLES}. Cover diverse information types: facts/data, "
                    "real-world examples/case studies, expert opinions, trends, comparisons, and challenges."
                )
            )

        # Rule 4: full reads, not just snippets.
        if fetch_count < MIN_FETCHES:
            nudges.append(
                self._nudge(
                    f"[SYSTEM REMINDER] You have only {fetch_count} full-page fetch(es); "
                    f"minimum is {MIN_FETCHES}. Use a fetch tool (web_fetch / fetch) on the most "
                    "relevant sources to read them in full, not just search snippets."
                )
            )

        # Rule 6: mid-process direction check after the first research batch.
        if search_count >= MIDCHECK_AT_SEARCHES and not self._ai_question_recent(messages):
            if search_count < MIDCHECK_2_AT_SEARCHES:
                nudges.append(
                    self._nudge(
                        "[SYSTEM REMINDER] Research checkpoint: pause and summarize what you found so far, "
                        "then ask the user for direction — is the scope right, and should you go deeper on "
                        "any angle? Wait for their answer before continuing."
                    )
                )
            elif not self._ai_question_recent(messages, lookback=6):
                nudges.append(
                    self._nudge(
                        "[SYSTEM REMINDER] Second research checkpoint: you have covered a lot of ground. "
                        "Brief the user on findings and ask whether to continue, narrow, or wrap up."
                    )
                )

        # Rule 5: citations on synthesis.
        if search_count >= MIN_SEARCHES and fetch_count >= MIN_FETCHES and not self._has_citations(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Synthesis requirements: cite every claim with numbered source links "
                    "from your search results (e.g. [1](url)); include 2-3 concrete examples, mention "
                    "challenges/limitations, and note the current year for time-sensitive claims. "
                    "An answer without citations is not acceptable."
                )
            )

        # Mermaid: synthesis must include a visual diagram.
        if search_count >= MIN_SEARCHES and not self._has_mermaid(messages):
            nudges.append(
                self._nudge(
                    "[SYSTEM REMINDER] Your final answer must include at least one mermaid diagram "
                    "(```mermaid ... ``` code block) visualizing the key structure, process, or flow of "
                    "your research findings. If your answer already contains one, ignore this."
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
            logger.info("DeepResearchMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
        if not self._is_research_shaped(messages):
            return handler(request)

        search_count, fetch_count, unique_queries = self._tool_counts(messages)
        nudges = self._build_nudges(
            search_count=search_count,
            fetch_count=fetch_count,
            unique_queries=unique_queries,
            messages=messages,
        )
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
        if not self._is_research_shaped(messages):
            return await handler(request)

        search_count, fetch_count, unique_queries = self._tool_counts(messages)
        nudges = self._build_nudges(
            search_count=search_count,
            fetch_count=fetch_count,
            unique_queries=unique_queries,
            messages=messages,
        )
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
