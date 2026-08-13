"""Tests for SystemDesignMiddleware's forced skill-context gate."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.system_design_middleware import (
    _SKILL_NAME,
    SystemDesignMiddleware,
)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _design_prompt() -> HumanMessage:
    return HumanMessage(content="Can you design the architecture for my personal note-taking app?")


def _slash_reminder(skill_name: str = "system-design") -> HumanMessage:
    return HumanMessage(
        content=(
            "<slash_skill_activation>\n"
            f"The user explicitly activated the `{skill_name}` skill for this turn.\n"
            f'<skill name="{skill_name}" category="design" path="skills/public/{skill_name}" sha256="abc" editable="false">'
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
    middleware = SystemDesignMiddleware()
    return middleware.wrap_model_call(_request(messages, state), lambda req: req)


def _injected_nudges(result: ModelRequest) -> list[HumanMessage]:
    """Extract hidden nudge messages injected by the middleware."""
    nudges: list[HumanMessage] = []
    for message in result.messages:
        if not isinstance(message, HumanMessage):
            continue
        additional_kwargs = message.additional_kwargs or {}
        if additional_kwargs.get("hide_from_ui") and not additional_kwargs.get("slash_skill_activation"):
            nudges.append(message)
    return nudges


def test_non_design_thread_passes_through() -> None:
    messages = [HumanMessage(content="hello there")]
    result = _run(messages)
    assert list(result.messages) == messages


def test_design_shaped_without_active_skill_gets_activation_nudge() -> None:
    messages = [_design_prompt()]
    result = _run(messages, state={})
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "system-design skill is not active" in content
    assert "Ask ONE question" not in content


def test_active_via_skill_context_fires_contract() -> None:
    messages = [_design_prompt()]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    content = str(nudges[0].content)
    assert "SYSTEM REMINDER" in content
    assert "skill is not active" not in content


def test_active_via_slash_reminder_fires_contract() -> None:
    messages = [_slash_reminder(), _design_prompt()]
    result = _run(messages, state={})
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    content = str(nudges[0].content)
    assert "SYSTEM REMINDER" in content
    assert "skill is not active" not in content


def test_searched_while_inactive_escalates() -> None:
    messages = [
        _design_prompt(),
        ToolMessage(content="some search results", name="web_search", tool_call_id="call-1"),
    ]
    result = _run(messages, state={})
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "STOP designing" in str(nudges[0].content)
