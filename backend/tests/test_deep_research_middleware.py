"""Tests for DeepResearchMiddleware's forced skill-context gate."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.deep_research_middleware import (
    _SKILL_NAME,
    MIN_CLARIFY_QUESTIONS,
    DeepResearchMiddleware,
)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _research_prompt() -> HumanMessage:
    return HumanMessage(content="Can you do a deep dive on rooftop solar in Vietnam?")


def _slash_reminder(skill_name: str = "deep-research") -> HumanMessage:
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
    middleware = DeepResearchMiddleware()
    return middleware.wrap_model_call(_request(messages, state), lambda req: req)


def _injected_nudges(result: ModelRequest) -> list[HumanMessage]:
    """Extract hidden nudge messages injected by the middleware.

    Slash-activation reminders are also hidden HumanMessages; exclude them by
    their marker so only middleware nudges are returned.
    """
    nudges: list[HumanMessage] = []
    for message in result.messages:
        if not isinstance(message, HumanMessage):
            continue
        additional_kwargs = message.additional_kwargs or {}
        if additional_kwargs.get("hide_from_ui") and not additional_kwargs.get("slash_skill_activation"):
            nudges.append(message)
    return nudges


def test_non_research_thread_passes_through() -> None:
    messages = [HumanMessage(content="hello there")]
    result = _run(messages)
    assert list(result.messages) == messages


def test_research_shaped_without_active_skill_passes_through() -> None:
    """Casual queries with research-shaped words get NO inactive-skill nudge."""
    messages = [_research_prompt()]
    result = _run(messages, state={})
    nudges = _injected_nudges(result)
    assert nudges == []
    # Messages pass through unchanged (no activation nudge injected).
    assert len(result.messages) == len(messages)


def test_active_via_skill_context_fires_contract() -> None:
    messages = [_research_prompt()]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    content = str(nudges[0].content)
    assert f"{MIN_CLARIFY_QUESTIONS} clarification questions" in content


def test_active_via_slash_reminder_fires_contract() -> None:
    messages = [_slash_reminder(), _research_prompt()]
    result = _run(messages, state={})
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    content = str(nudges[0].content)
    assert f"{MIN_CLARIFY_QUESTIONS} clarification questions" in content


def test_searched_while_inactive_passes_through() -> None:
    """Searching without the skill active is no longer escalated — fast exit."""
    messages = [
        _research_prompt(),
        ToolMessage(content="some search results", name="web_search", tool_call_id="call-1"),
    ]
    result = _run(messages, state={})
    assert _injected_nudges(result) == []


def test_build_nudges_keyword_only_regression() -> None:
    middleware = DeepResearchMiddleware()
    nudges = middleware._build_nudges(search_count=0, fetch_count=0, unique_queries=set(), messages=[_research_prompt()])
    assert isinstance(nudges, list)
    assert len(nudges) >= 1
    assert "clarification questions" in str(nudges[0].content)
