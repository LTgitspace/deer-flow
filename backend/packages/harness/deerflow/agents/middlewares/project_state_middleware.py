"""Project-state middleware: persist pipeline artifacts and resume across threads.

Contract documents (BRD/PRD/SRS/SAD) produced in a thread are extracted
deterministically from AI messages (document markers shared with the
requirements pipeline) and versioned on disk under DEER_FLOW_HOME/projects.
A thread binds to a project when the user names it:

    /project <name>          project: <name>
    continue project <name>  open project <name>

On binding — or on an explicit "project state" request — the latest artifact
summaries are injected as hidden context, so a new thread resumes where the
project left off.

Design notes:
  - The store is file-based and content-hash versioned; unchanged documents
    never bump versions.
  - The only state write is the lightweight `project` binding channel.
  - Extraction runs on every model call over current messages; writes are
    tiny and deduplicated by the store.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.projects.store import ProjectStore, detect_artifact_kind

logger = logging.getLogger(__name__)

_BINDING_PATTERNS = (
    re.compile(r"/project\s+([a-zA-Z0-9][\w\-]*)"),
    re.compile(r"project:\s*([a-zA-Z0-9][\w\-]*)"),
    re.compile(r"(?:continue|open|resume)\s+project\s+([a-zA-Z0-9][\w\-]*)"),
)
_RESUME_PHRASES = ("project state", "project status", "project summary", "where is the project")

_RESUME_CHAR_BUDGET = 4000


class ProjectStateMiddleware(AgentMiddleware[AgentState]):
    """Extract contract artifacts to the project store; inject resume context."""

    def __init__(self, store: ProjectStore | None = None) -> None:
        super().__init__()
        self._store = store or ProjectStore()

    # ── History-derived state ──

    @staticmethod
    def _latest_user_message(messages: list) -> HumanMessage | None:
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and not (getattr(msg, "additional_kwargs", None) or {}).get("hide_from_ui"):
                return msg
        return None

    @staticmethod
    def _detect_project_binding(message: HumanMessage) -> str | None:
        content = str(getattr(message, "content", "") or "")
        for pattern in _BINDING_PATTERNS:
            match = pattern.search(content)
            if match:
                return match.group(1)
        return None

    def _extract_artifacts(self, messages: list, project: str) -> int:
        saved = 0
        for msg in messages:
            if not isinstance(msg, AIMessage):
                continue
            content = str(getattr(msg, "content", "") or "")
            kind = detect_artifact_kind(content)
            if kind and self._store.save_artifact(project, kind, content):
                saved += 1
        return saved

    def _build_resume_nudge(self, project: str) -> HumanMessage | None:
        summary = self._store.resume_summary(project, char_budget_per_artifact=_RESUME_CHAR_BUDGET)
        if not summary:
            return None
        return HumanMessage(
            content=summary,
            additional_kwargs={"hide_from_ui": True, "project_context": True},
        )

    def _build_nudges(self, messages: list, state: dict) -> list[HumanMessage]:
        latest = self._latest_user_message(messages)
        if latest is None:
            return []
        binding = self._detect_project_binding(latest)
        state_project = state.get("project")
        project = binding or (state_project if isinstance(state_project, str) else None)
        if not project:
            return []

        nudges: list[HumanMessage] = []
        self._extract_artifacts(messages, project)

        content_lower = str(getattr(latest, "content", "") or "").lower()
        asks_resume = binding is not None or any(phrase in content_lower for phrase in _RESUME_PHRASES)
        if asks_resume:
            nudge = self._build_resume_nudge(project)
            if nudge:
                nudges.append(nudge)
        return nudges

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

    # ── Lifecycle hooks ──

    def _capture(self, state: AgentState) -> dict | None:
        """Persist newly produced artifacts and bind the project channel."""
        messages = list(state.get("messages") or [])
        project = state.get("project")
        if isinstance(project, str):
            saved = self._extract_artifacts(messages, project)
            if saved:
                logger.info("ProjectStateMiddleware saved %d artifact(s) for project %s", saved, project)
        latest = self._latest_user_message(messages)
        if latest is not None:
            binding = self._detect_project_binding(latest)
            if binding and project != binding:
                return {"project": binding}
        return None

    @override
    def before_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._capture(state)

    @override
    async def abefore_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._capture(state)

    @override
    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._capture(state)

    @override
    async def aafter_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        return self._capture(state)

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
            for nudge in nudges:
                logger.info("ProjectStateMiddleware inject: %s", str(nudge.content)[:120].replace("\n", " "))
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
            for nudge in nudges:
                logger.info("ProjectStateMiddleware inject: %s", str(nudge.content)[:120].replace("\n", " "))
            request = request.override(messages=self._patch_messages(messages, nudges))
        return await handler(request)
