"""Tests for PlantingResearchMiddleware's forced skill-context gate."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.planting_research_middleware import (
    _SKILL_NAME,
    PlantingResearchMiddleware,
)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _planting_prompt() -> HumanMessage:
    # Deliberately locale-free: "balcony" would satisfy the locale gate and
    # suppress the Gate 1 nudge this test relies on.
    return HumanMessage(content="Help me plan how to grow tomatoes")


def _slash_reminder(skill_name: str = "planting-research") -> HumanMessage:
    return HumanMessage(
        content=(
            "<slash_skill_activation>\n"
            f"The user explicitly activated the `{skill_name}` skill for this turn.\n"
            f'<skill name="{skill_name}" category="research" path="skills/public/{skill_name}" sha256="abc" editable="false">'
        ),
        additional_kwargs={"hide_from_ui": True, "slash_skill_activation": True},
    )


def _active_skill_state() -> dict:
    return {
        "skill_context": [
            {"name": _SKILL_NAME, "path": f"skills/public/{_SKILL_NAME}/SKILL.md", "description": "", "loaded_at": 0}
        ]
    }


def _run(messages: list, state: dict | None = None) -> ModelRequest:
    middleware = PlantingResearchMiddleware()
    return middleware.wrap_model_call(_request(messages, state), lambda req: req)


def _injected_nudges(result: ModelRequest) -> list[HumanMessage]:
    nudges: list[HumanMessage] = []
    for message in result.messages:
        if not isinstance(message, HumanMessage):
            continue
        additional_kwargs = message.additional_kwargs or {}
        if additional_kwargs.get("hide_from_ui") and not additional_kwargs.get("slash_skill_activation"):
            nudges.append(message)
    return nudges


def test_inactive_skill_passes_through_untouched() -> None:
    messages = [_planting_prompt()]
    result = _run(messages, state={})
    assert list(result.messages) == messages


def test_unrelated_thread_passes_through_untouched() -> None:
    messages = [HumanMessage(content="hello there")]
    result = _run(messages, state={})
    assert list(result.messages) == messages


def test_active_via_skill_context_fires_contract() -> None:
    messages = [_planting_prompt()]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    assert "SYSTEM REMINDER" in str(nudges[0].content)


def test_active_via_slash_reminder_fires_contract() -> None:
    messages = [_slash_reminder(), _planting_prompt()]
    result = _run(messages, state={})
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    assert "SYSTEM REMINDER" in str(nudges[0].content)
