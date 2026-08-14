"""Planner middleware: deterministic plan-first enforcement for multi-step work.

The workflow contract, enforced around the model's own actions:

  1. Plan first — a multi-step request must produce a numbered plan (one
     step per line, one target per step) before any file is touched.
  2. No plan, no edits — file mutations (write_file / str_replace) executed
     before a plan exists get a STOP correction until the plan appears.
  3. Strict execution — an edited file that does not appear in the plan
     gets a deviation correction (update the plan or revert).

Mechanics:
  - Multi-step classification is deterministic: two distinct action verbs,
    a numbered directive, two or more file mentions, or multi-part
    conjunctions — all gated on a minimum message length.
  - Plan evidence is a numbered list in the exchange's AI text, a "## Plan"
    header, or the thread's todo channel (the harness's persistent plan
    store across turns).
  - Gates are scoped to the current exchange (messages after the latest
    visible user message), so a new trivial message re-arms and the
    middleware can never nag across unrelated turns.
  - Hidden HumanMessage nudges, self-correction only: no hard block, no
    state writes beyond reading the todos channel.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.config.planner_config import get_planner_config

logger = logging.getLogger(__name__)

MAX_NUDGES_PER_CALL = 1

_MUTATION_TOOLS = ("write_file", "str_replace")
_NUMBERED_LINE_RE = re.compile(r"^\s*(?:\d+[.)]|[-*])\s+\S", re.MULTILINE)
_PLAN_HEADER_RE = re.compile(r"^#{1,3}\s*plan\b", re.MULTILINE | re.IGNORECASE)
_EXTENSION_RE = re.compile(r"\b[\w\-./]+\.([a-z0-9]{1,5})\b", re.IGNORECASE)
_NUMBERED_DIRECTIVE_RE = re.compile(r"(?m)^\s*\d+[.)]\s")


class PlannerMiddleware(AgentMiddleware[AgentState]):
    """Enforce plan-first execution for multi-step work."""

    def __init__(self, *, app_config=None, planner_config=None) -> None:
        super().__init__()
        self._app_config = app_config
        self._planner_config = planner_config

    def _get_config(self):
        if self._planner_config is not None:
            return self._planner_config
        section = getattr(self._app_config, "planner", None)
        if section is not None:
            return section
        return get_planner_config()

    # ── History-derived state ──

    @staticmethod
    def _latest_user_index(messages: list) -> int | None:
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return i
        return None

    def _classify_multi_step(self, content: str) -> bool:
        config = self._get_config()
        content = content.strip()
        if len(content) < config.min_chars:
            return False
        lowered = content.lower()

        distinct_verbs = {verb for verb in config.action_verbs if re.search(rf"\b{re.escape(verb)}\b", lowered)}
        if len(distinct_verbs) >= 2:
            return True
        if len(_NUMBERED_DIRECTIVE_RE.findall(content)) >= 2:
            return True
        file_mentions = sum(1 for match in _EXTENSION_RE.finditer(content) if match.group(1).lower() in {ext.lower() for ext in config.file_extensions})
        if file_mentions >= 2:
            return True
        if lowered.count(" and ") >= 2:
            return True
        return False

    @staticmethod
    def _has_plan_text(content: str, min_steps: int) -> bool:
        if _PLAN_HEADER_RE.search(content):
            return True
        if len(_NUMBERED_LINE_RE.findall(content)) >= min_steps:
            return True
        if "step 1" in content.lower() and "step 2" in content.lower():
            return True
        return False

    def _exchange_plan_exists(self, exchange: list) -> bool:
        config = self._get_config()
        for msg in exchange:
            if isinstance(msg, AIMessage) and self._has_plan_text(str(getattr(msg, "content", "") or ""), config.min_plan_steps):
                return True
        return False

    def _exchange_plan_text(self, exchange: list) -> str:
        return "\n".join(
            str(getattr(msg, "content", "") or "")
            for msg in exchange
            if isinstance(msg, AIMessage)
        ).lower()

    @staticmethod
    def _thread_todos(state: dict) -> bool:
        todos = state.get("todos")
        return bool(isinstance(todos, list) and todos)

    def _exchange_edits(self, exchange: list) -> list[str]:
        """File paths mutated in this exchange via write_file / str_replace."""
        edits: list[str] = []
        for msg in exchange:
            if not isinstance(msg, AIMessage):
                continue
            for tool_call in getattr(msg, "tool_calls", None) or []:
                if tool_call.get("name") not in _MUTATION_TOOLS:
                    continue
                path = str((tool_call.get("args") or {}).get("path") or "").strip()
                if not path:
                    continue
                completion_ok = any(
                    isinstance(later, ToolMessage)
                    and getattr(later, "tool_call_id", None) == tool_call.get("id")
                    and getattr(later, "status", None) != "error"
                    for later in exchange
                )
                if completion_ok:
                    edits.append(path)
        return edits

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list, state: dict) -> list[HumanMessage]:
        config = self._get_config()
        if not config.enabled:
            return []

        user_idx = self._latest_user_index(messages)
        if user_idx is None:
            return []
        user_content = str(getattr(messages[user_idx], "content", "") or "")
        if not self._classify_multi_step(user_content):
            return []

        exchange = list(messages[user_idx + 1 :])
        edits = self._exchange_edits(exchange)
        plan_exists = self._exchange_plan_exists(exchange) or self._thread_todos(state)

        if edits and not plan_exists:
            return [
                self._nudge(
                    "[PLANNER REMINDER] STOP: files were modified without a plan. Produce the "
                    "numbered plan now — one step per line, one target per step — map what was "
                    "already done onto it, then continue executing strictly in plan order."
                )
            ]

        if not plan_exists:
            return [
                self._nudge(
                    "[PLANNER REMINDER] This is multi-step work. Before touching any files, "
                    "write a numbered plan: one step per line, one target per step. Present the "
                    "plan first, then execute step by step. Do not start editing until the plan "
                    "exists."
                )
            ]

        if edits:
            plan_text = self._exchange_plan_text(exchange)
            for path in edits:
                basename = path.replace("\\", "/").split("/")[-1].lower()
                if basename and basename not in plan_text:
                    return [
                        self._nudge(
                            f"[PLANNER REMINDER] Deviation: '{path}' was modified but does not "
                            "appear in the plan. Either update the plan to include it or revert "
                            "the change. Execute strictly within the planned steps."
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
            logger.info("PlannerMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

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
