"""Tests for ProductRequirementsMiddleware's forced skill-context gate and phase ladder."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.product_requirements_middleware import (
    _QUESTION_SEQUENCE,
    _SKILL_NAME,
    ProductRequirementsMiddleware,
)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _slash_reminder(skill_name: str = "product-requirements") -> HumanMessage:
    return HumanMessage(
        content=(
            "<slash_skill_activation>\n"
            f"The user explicitly activated the `{skill_name}` skill for this turn.\n"
            f'<skill name="{skill_name}" category="product" path="skills/public/{skill_name}" sha256="abc" editable="false">'
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
    middleware = ProductRequirementsMiddleware()
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
    messages = [HumanMessage(content="write me a PRD for an expense tracker")]
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
        AIMessage(content="Who is the target user for this product?"),
    ]
    nudges = ProductRequirementsMiddleware()._build_nudges(messages)
    assert len(nudges) == 1
    assert "has not answered" in str(nudges[0].content)


def test_context_question_sequence_advances_one_at_a_time() -> None:
    messages = [
        HumanMessage(content="hello"),
        AIMessage(content="Who is the target user?"),
        HumanMessage(content="some short answer"),
    ]
    nudges = ProductRequirementsMiddleware()._build_nudges(messages)
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "Ask ONE" in content
    assert _QUESTION_SEQUENCE[0] in content


# ── Phase ladder ──

_CONTEXT_USER = HumanMessage(
    content=(
        "The product targets mobile users who need to track expenses; the core problem "
        "is visibility of spending; the vision is effortless budgeting; success metric "
        "is 40% activation in 3 months; timeline is 3 months; platform is mobile web."
    )
)

_FEATURE_CORE = (
    "As a user\nI want to track expenses\nSo that I can see my spending\n\n"
    "Acceptance Criteria:\n"
    "- [ ] Submitting an expense shows a confirmation within 2 seconds\n"
    "- [ ] The total updates to the correct percentage of the budget\n\n"
    "Must-have"
)


def _nudges(messages: list) -> list[HumanMessage]:
    return ProductRequirementsMiddleware()._build_nudges(messages)


def test_ladder_personas() -> None:
    nudges = _nudges([_CONTEXT_USER])
    assert len(nudges) == 1
    assert "persona" in str(nudges[0].content)


def test_ladder_vision() -> None:
    ai = AIMessage(content="## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |")
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "vision" in str(nudges[0].content)


def test_ladder_success_metrics() -> None:
    ai = AIMessage(content="## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n## Product Vision\nFor users who need budgeting, the app tracks spending.")
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "metric" in str(nudges[0].content)


def test_ladder_scope() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "scope" in str(nudges[0].content)


def test_ladder_stories() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments."
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "As a / I want" in str(nudges[0].content)


def test_ladder_acceptance_criteria() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            "As a user\nI want to track expenses\nSo that I can see my spending"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "acceptance criteria" in str(nudges[0].content)


def test_ladder_testability_vague_words() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            "As a user\nI want to track expenses\nSo that I can see my spending\n\n"
            "Acceptance Criteria:\n- [ ] The app is fast and easy to use\n- [ ] It feels reliable"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "not testable" in str(nudges[0].content)


def test_ladder_priorities() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            "As a user\nI want to track expenses\nSo that I can see my spending\n\n"
            "Acceptance Criteria:\n- [ ] Submitting an expense shows a confirmation within 2 seconds\n"
            "- [ ] The total updates to the correct percentage of the budget"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "MoSCoW" in str(nudges[0].content)


def test_ladder_mermaid() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            + _FEATURE_CORE
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "mermaid" in str(nudges[0].content)


def test_ladder_ux() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            + _FEATURE_CORE
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "UX" in str(nudges[0].content)


def test_ladder_dependencies_risks() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            + _FEATURE_CORE
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\n## UX Considerations\nNavigation and key screens"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "dependencies" in str(nudges[0].content)


def test_ladder_release_criteria() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            + _FEATURE_CORE
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\n## UX Considerations\nNavigation and key screens\n\n"
            "## External Dependencies\n| Dependency | Owner |\n| Auth service | Internal |"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "release criteria" in str(nudges[0].content)


def test_ladder_roadmap() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            + _FEATURE_CORE
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\n## UX Considerations\nNavigation and key screens\n\n"
            "## External Dependencies\n| Dependency | Owner |\n| Auth service | Internal |\n\n"
            "## Release Criteria\n- [ ] Checkout completes in < 5 seconds"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert len(nudges) == 1
    assert "roadmap" in str(nudges[0].content)


def test_ladder_complete_document_no_nudges() -> None:
    ai = AIMessage(
        content=(
            "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
            "## Product Vision\nFor users who need budgeting, the app tracks spending.\n\n"
            "## Success Metrics\n| Metric | Target | Timeframe |\n| Activation | 40% | 3 months |\n\n"
            "## Scope\nIn Scope: expense tracking. Out of Scope: investments.\n\n"
            + _FEATURE_CORE
            + "\n\n```mermaid\nflowchart TD\nA --> B\n```\n\n## UX Considerations\nNavigation and key screens\n\n"
            "## External Dependencies\n| Dependency | Owner |\n| Auth service | Internal |\n\n"
            "## Release Criteria\n- [ ] Checkout completes in < 5 seconds\n\n## Roadmap\n| Phase | Scope |"
        )
    )
    nudges = _nudges([_CONTEXT_USER, ai])
    assert nudges == []
