"""Tests for SkillEvolutionMiddleware's reviewer-first, user-ratified workflow."""

import asyncio
from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.skill_evolution_middleware import SkillEvolutionMiddleware
from deerflow.config.skill_evolution_config import SkillEvolutionConfig


class _EnabledConfig:
    """Minimal stand-in for AppConfig exposing an enabled skill_evolution section."""

    def __init__(self, enabled: bool = True) -> None:
        self.skill_evolution = SkillEvolutionConfig(enabled=enabled)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _run(messages: list, enabled: bool = True) -> ModelRequest:
    middleware = SkillEvolutionMiddleware(app_config=_EnabledConfig(enabled=enabled))
    return middleware.wrap_model_call(_request(messages), lambda req: req)


def _injected(result: ModelRequest) -> list[HumanMessage]:
    return [
        msg
        for msg in result.messages
        if isinstance(msg, HumanMessage) and "SKILL EVOLUTION REMINDER" in str(msg.content)
    ]


def _write_call(action: str = "create", call_id: str = "call-write-1") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "skill_manage", "args": {"action": action, "name": "demo-skill"}, "id": call_id}],
    )


def _review_result() -> ToolMessage:
    return ToolMessage(content="static_report: ok", name="review_skill_package", tool_call_id="call-review-1")


def _write_success(call_id: str = "call-write-1") -> ToolMessage:
    return ToolMessage(content="Created custom skill 'demo-skill'.", name="skill_manage", tool_call_id=call_id)


def _write_error(call_id: str = "call-write-1") -> ToolMessage:
    return ToolMessage(content="Error: security scan blocked the write.", name="skill_manage", tool_call_id=call_id, status="error")


# ── Silence ──


def test_no_skill_calls_passes_through() -> None:
    result = _run([HumanMessage(content="hello there")])
    assert _injected(result) == []


def test_disabled_config_stays_silent() -> None:
    result = _run([_write_call()], enabled=False)
    assert _injected(result) == []


# ── Gate 1: reviewer first ──


def test_pending_write_without_review_gets_reviewer_nudge() -> None:
    result = _run([_write_call()])
    nudges = _injected(result)
    assert len(nudges) == 1
    assert "review_skill_package" in str(nudges[0].content)


def test_pending_write_with_prior_review_is_quiet() -> None:
    result = _run([_review_result(), _write_call()])
    assert _injected(result) == []


# ── Gate 2: draft until ratified ──


def test_successful_write_without_approval_gets_draft_nudge() -> None:
    result = _run([_review_result(), _write_call(), _write_success()])
    nudges = _injected(result)
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "DRAFT" in content
    assert "approval" in content


def test_successful_write_then_user_approval_is_quiet() -> None:
    result = _run([_review_result(), _write_call(), _write_success(), HumanMessage(content="approved, activate it")])
    assert _injected(result) == []


def test_approval_phrase_variants() -> None:
    for phrase in ("looks good", "go ahead", "ship it", "go for it"):
        result = _run([_review_result(), _write_call(), _write_success(), HumanMessage(content=phrase)])
        assert _injected(result) == []


def test_blocked_write_ends_obligation() -> None:
    result = _run([_review_result(), _write_call(), _write_error()])
    assert _injected(result) == []


# ── Action and message filtering ──


def test_delete_action_is_ignored() -> None:
    result = _run([_write_call(action="delete")])
    assert _injected(result) == []


def test_hidden_messages_do_not_count_as_approval() -> None:
    hidden = HumanMessage(content="approved", additional_kwargs={"hide_from_ui": True})
    result = _run([_review_result(), _write_call(), _write_success(), hidden])
    nudges = _injected(result)
    assert len(nudges) == 1
    assert "DRAFT" in str(nudges[0].content)


def test_prior_review_satisfies_gate_for_later_write() -> None:
    # Presence-based heuristic: any earlier review_skill_package result in the
    # thread counts as evidence for a subsequent write.
    messages = [
        _write_call(action="create", call_id="call-1"),
        _write_success(call_id="call-1"),
        _review_result(),
        _write_call(action="edit", call_id="call-2"),
    ]
    assert _injected(_run(messages)) == []


def test_full_flow_review_write_approve_is_quiet() -> None:
    messages = [
        _review_result(),
        _write_call(),
        _write_success(),
        HumanMessage(content="approved"),
        AIMessage(content="The skill demo-skill is now active."),
    ]
    assert _injected(_run(messages)) == []


def test_awrap_model_call_injects_draft_nudge() -> None:
    middleware = SkillEvolutionMiddleware(app_config=_EnabledConfig())

    async def handler(req: ModelRequest) -> ModelRequest:
        return req

    result = asyncio.run(
        middleware.awrap_model_call(
            _request([_review_result(), _write_call(), _write_success()]),
            handler,
        )
    )
    assert len(_injected(result)) == 1


def test_config_defaults() -> None:
    config = SkillEvolutionConfig()
    assert config.enabled is False
    assert config.security_fail_closed is True
    assert config.moderation_model_name is None
