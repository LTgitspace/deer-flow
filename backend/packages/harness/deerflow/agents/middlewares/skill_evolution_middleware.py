"""Skill-evolution middleware: reviewer-first writes and user-ratified drafts.

The deterministic workflow enforced around the skill_manage tool:

  1. Reviewer first — a skill write (create/edit/patch/write_file) must be
     preceded in the thread by a ``review_skill_package`` run. The reviewer
     report is evidence the proposed content was inspected before writing,
     not just written blind.
  2. Draft until ratified — after a successful write the skill is a DRAFT.
     The model must present the reviewer findings and ask the user for
     explicit approval. Until the user approves, the skill must not be
     loaded or used.
  3. Ratification — a visible user message with approval language after the
     write ends the obligation.

Enforcement is via hidden nudges (self-correction), consistent with every
other gate: no hard block, no state writes, everything derived from message
history. The middleware is silent unless skill evolution is enabled in
config.

Heuristic notes (documented, deterministic):
  - "Reviewed before" is presence-based: any review_skill_package tool
    result earlier in the thread counts as evidence for the write.
  - Blocked writes (tool errors) end the obligation — the tool already
    surfaced the failure to the model.
  - Delete / remove_file actions are not content writes and are ignored.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from deerflow.config.skill_evolution_config import SkillEvolutionConfig

logger = logging.getLogger(__name__)

MAX_NUDGES_PER_CALL = 1

_WRITE_ACTIONS = ("create", "edit", "patch", "write_file")
_SUCCESS_PREFIXES = ("Created custom skill", "Updated custom skill", "Patched custom skill", "Wrote '")
_APPROVAL_PHRASES = (
    "approve", "approved", "looks good", "sounds good", "activate",
    "go ahead", "go for it", "ship it",
)


class SkillEvolutionMiddleware(AgentMiddleware[AgentState]):
    """Enforce reviewer-first skill writes and user-ratified drafts."""

    def __init__(self, *, app_config=None) -> None:
        super().__init__()
        self._app_config = app_config

    def _get_config(self) -> SkillEvolutionConfig:
        section = getattr(self._app_config, "skill_evolution", None)
        return section if section is not None else SkillEvolutionConfig()

    # ── History-derived state ──

    @staticmethod
    def _write_call(messages: list) -> tuple[int, dict] | None:
        """The latest skill_manage content-write call, as (index, tool_call)."""
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if not isinstance(msg, AIMessage):
                continue
            for tool_call in getattr(msg, "tool_calls", None) or []:
                if tool_call.get("name") != "skill_manage":
                    continue
                args = tool_call.get("args") or {}
                if args.get("action") in _WRITE_ACTIONS:
                    return i, tool_call
        return None

    @staticmethod
    def _reviewed_before(messages: list, call_index: int) -> bool:
        for msg in messages[:call_index]:
            if isinstance(msg, ToolMessage) and getattr(msg, "name", "") == "review_skill_package":
                return True
        return False

    @staticmethod
    def _completion(messages: list, tool_call: dict) -> tuple[int, ToolMessage] | None:
        """The ToolMessage completing the write call, as (index, message)."""
        call_id = tool_call.get("id")
        if not call_id:
            return None
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, ToolMessage) and getattr(msg, "tool_call_id", None) == call_id:
                return i, msg
        return None

    @staticmethod
    def _is_success(completion: ToolMessage) -> bool:
        if getattr(completion, "status", None) == "error":
            return False
        content = str(getattr(completion, "content", "") or "")
        return content.startswith(_SUCCESS_PREFIXES)

    @staticmethod
    def _approved_after(messages: list, completion_index: int) -> bool:
        for msg in messages[completion_index + 1 :]:
            if not isinstance(msg, HumanMessage):
                continue
            if (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                continue
            content = str(getattr(msg, "content", "") or "").lower()
            if any(phrase in content for phrase in _APPROVAL_PHRASES):
                return True
        return False

    # ── Nudge builders ──

    def _nudge(self, text: str) -> HumanMessage:
        return HumanMessage(content=text, additional_kwargs={"hide_from_ui": True})

    def _build_nudges(self, messages: list) -> list[HumanMessage]:
        if not self._get_config().enabled:
            return []

        write = self._write_call(messages)
        if write is None:
            return []

        call_index, tool_call = write
        completion = self._completion(messages, tool_call)

        if completion is None:
            if not self._reviewed_before(messages, call_index):
                return [
                    self._nudge(
                        "[SKILL EVOLUTION REMINDER] You are about to write a skill, but no "
                        "review_skill_package run exists in this thread for the proposed content. "
                        "Run review_skill_package first (inline the proposed SKILL.md), confirm the "
                        "report shows valid frontmatter and content, and only then write."
                    )
                ]
            return []

        completion_index, completion_msg = completion
        if self._is_success(completion_msg) and not self._approved_after(messages, completion_index):
            return [
                self._nudge(
                    "[SKILL EVOLUTION REMINDER] The skill was written successfully, but it is still "
                    "a DRAFT. Present the reviewer findings to the user and ask for explicit "
                    "approval to activate it. Do not load or use the new skill until the user "
                    "approves."
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
            logger.info("SkillEvolutionMiddleware trigger: %s", str(nudge.content)[:120].replace("\n", " "))

    # ── Lifecycle hooks ──

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        messages = list(request.messages)
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
        nudges = self._build_nudges(messages)
        if nudges:
            self._log_nudges(nudges)
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
