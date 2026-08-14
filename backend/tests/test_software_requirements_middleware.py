"""Tests for SoftwareRequirementsMiddleware's forced skill-context gate and phase ladder."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.software_requirements_middleware import (
    _QUESTION_SEQUENCE,
    _SKILL_NAME,
    SoftwareRequirementsMiddleware,
)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _slash_reminder(skill_name: str = "software-requirements") -> HumanMessage:
    return HumanMessage(
        content=(
            "<slash_skill_activation>\n"
            f"The user explicitly activated the `{skill_name}` skill for this turn.\n"
            f'<skill name="{skill_name}" category="engineering" path="skills/public/{skill_name}" sha256="abc" editable="false">'
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
    middleware = SoftwareRequirementsMiddleware()
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


# ── Skill-context gate ──


def test_inactive_skill_passes_through_untouched() -> None:
    messages = [HumanMessage(content="write me an SRS for an expense tracker")]
    result = _run(messages, state={})
    assert list(result.messages) == messages


def test_active_via_skill_context_fires_contract() -> None:
    messages = [HumanMessage(content="hello there")]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    assert "REMINDER]" in str(nudges[0].content)


def test_active_via_slash_reminder_fires_contract() -> None:
    messages = [_slash_reminder(), HumanMessage(content="hello there")]
    result = _run(messages, state={})
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    assert "REMINDER]" in str(nudges[0].content)


# ── Phase 1: context discovery ──


def test_wait_gate_when_question_unanswered() -> None:
    messages = [
        HumanMessage(content="hello"),
        AIMessage(content="What is the target user for this system?"),
    ]
    nudges = SoftwareRequirementsMiddleware()._build_nudges(messages)
    assert len(nudges) == 1
    assert "has not answered" in str(nudges[0].content)


def test_context_question_sequence_advances_one_at_a_time() -> None:
    messages = [
        HumanMessage(content="hello"),
        AIMessage(content="What is the target user?"),
        HumanMessage(content="some short answer"),
    ]
    nudges = SoftwareRequirementsMiddleware()._build_nudges(messages)
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "Ask ONE" in content
    assert _QUESTION_SEQUENCE[0] in content


# ── Phase ladder ──

_CONTEXT_USER = HumanMessage(
    content=(
        "Our app targets mobile users who need to track expenses and share reports "
        "with stakeholders; the business goal is retention; timeline is 3 months; "
        "platform is mobile web."
    )
)

_STORIES = (
    "As a user\nI want to track expenses\nSo that I can save money\n\n"
    "Acceptance Criteria:\n"
    "- [ ] Submitting an expense shows a confirmation within 2 seconds\n"
    "- [ ] The amount field rejects negative numbers\n\n"
    "Must-have"
)


def _nudges(messages: list) -> list[HumanMessage]:
    return SoftwareRequirementsMiddleware()._build_nudges(messages)


def test_ladder_stories() -> None:
    nudges = _nudges([_CONTEXT_USER])
    assert len(nudges) == 1
    assert "As a / I want" in str(nudges[0].content)


def test_ladder_acceptance_criteria() -> None:
    ai = AIMessage(content="As a user\nI want to track expenses\nSo that I can save money")
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "acceptance criteria" in str(nudges[0].content)


def test_ladder_testability_insufficient_checkboxes() -> None:
    ai = AIMessage(content=_STORIES + "\n\nAcceptance Criteria:\n- [ ] It should be fast")
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "not testable" in str(nudges[0].content)


def test_ladder_testability_vague_words() -> None:
    ai = AIMessage(
        content=(
            "As a user\nI want to track expenses\nSo that I can save money\n\n"
            "Acceptance Criteria:\n"
            "- [ ] The app is fast and easy to use\n"
            "- [ ] It feels reliable"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "not testable" in str(nudges[0].content)


def test_ladder_priorities() -> None:
    ai = AIMessage(
        content=(
            "As a user\nI want to track expenses\nSo that I can save money\n\n"
            "Acceptance Criteria:\n"
            "- [ ] Submitting an expense shows a confirmation within 2 seconds\n"
            "- [ ] The amount field rejects negative numbers"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "MoSCoW" in str(nudges[0].content)


def test_ladder_mermaid() -> None:
    nudges = _nudges([_CONTEXT_USER, AIMessage(content=_STORIES)])
    assert len(nudges) == 1
    assert "mermaid" in str(nudges[0].content)


def test_ladder_functional_spec() -> None:
    ai = AIMessage(content=_STORIES + "\n\n```mermaid\nflowchart TD\nA --> B\n```")
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "functional spec" in str(nudges[0].content)


def test_ladder_error_states() -> None:
    ai = AIMessage(content=_STORIES + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\nEdge case: user has no data")
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "error state" in str(nudges[0].content)


def test_ladder_data_dictionary() -> None:
    ai = AIMessage(
        content=(
            _STORIES
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\nEdge case: offline\n\n"
            "Error state: shows retry button"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "data dictionary" in str(nudges[0].content)


def test_ladder_traceability() -> None:
    ai = AIMessage(
        content=(
            _STORIES
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\nEdge case: offline\n\n"
            "Error state: shows retry button\n\n| Field | Type | Required |"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "traceability" in str(nudges[0].content)


def test_ladder_validation() -> None:
    ai = AIMessage(
        content=(
            _STORIES
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\nEdge case: offline\n\n"
            "Error state: shows retry button\n\n| Field | Type | Required |\n\n"
            "| Requirement ID | Type | Source | Test Case |"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "review checklist" in str(nudges[0].content)


def test_ladder_complete_document_no_nudges() -> None:
    ai = AIMessage(
        content=(
            _STORIES
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\nEdge case: offline\n\n"
            "Error state: shows retry button\n\n| Field | Type | Required |\n\n"
            "| Requirement ID | Type | Source | Test Case |\n\nReview Checklist complete"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert nudges == []
