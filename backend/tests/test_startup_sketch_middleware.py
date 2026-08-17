"""Tests for StartupSketchMiddleware's product-first lean sketching gate."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.startup_sketch_middleware import (
    _SKILL_NAME,
    StartupSketchMiddleware,
)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _active_skill_state() -> dict:
    return {
        "skill_context": [
            {"name": _SKILL_NAME, "path": f"skills/public/{_SKILL_NAME}/SKILL.md", "description": "", "loaded_at": 0}
        ]
    }


def _slash_reminder() -> HumanMessage:
    return HumanMessage(
        content=(
            "<slash_skill_activation>\n"
            f"The user explicitly activated the `{_SKILL_NAME}` skill for this turn.\n"
            f'<skill name="{_SKILL_NAME}" category="design" path="skills/public/{_SKILL_NAME}" sha256="abc" editable="false">'
        ),
        additional_kwargs={"hide_from_ui": True, "slash_skill_activation": True},
    )


def _run(messages: list, state: dict | None = None) -> ModelRequest:
    middleware = StartupSketchMiddleware()
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


def _sketch_prompt() -> HumanMessage:
    return HumanMessage(content="Can you help me sketch a startup idea for a local produce marketplace?")


def _idea_answered_prompt() -> HumanMessage:
    return HumanMessage(
        content=(
            "Sketch this startup idea: the problem is that local farmers cannot reach nearby "
            "buyers, the customer is urban families who want fresh produce, and the vision is "
            "a neighborhood farm-to-table marketplace."
        )
    )


def _mermaid_ai() -> AIMessage:
    return AIMessage(content="```mermaid\ngraph TD\n A[Farmers] --> B[Marketplace]\n B --> C[Buyers]\n```")


def _product_ai() -> AIMessage:
    return AIMessage(
        content=(
            "## Product Description\n- **Vision**: neighborhood farm-to-table marketplace\n"
            "- **Core features**: listing, ordering, pickup\n"
            "- **MVP scope**: listings + orders\n"
            "- **Explicitly out of scope**: delivery logistics"
        )
    )


def _business_ai() -> AIMessage:
    return AIMessage(
        content=(
            "## Business Description\n- **Problem**: farmers cannot reach buyers\n"
            "- **Solution**: a marketplace\n"
            "- **Value proposition**: fresh and local\n"
            "- **Customer**: urban families\n"
            "- **Revenue model**: 10% commission"
        )
    )


def _landing_ai() -> AIMessage:
    return AIMessage(
        content=(
            "<!DOCTYPE html>\n<html><head><style>body{font-family:sans-serif}</style></head>\n"
            "<body><h1>Local Produce</h1><p>Farm fresh, nearby.</p></body></html>"
        )
    )


# ── Activation ──


def test_non_sketch_thread_passes_through() -> None:
    messages = [HumanMessage(content="hello there")]
    result = _run(messages)
    assert list(result.messages) == messages


def test_sketch_shaped_without_active_skill_passes_through() -> None:
    """Casual queries with sketch-shaped words get NO inactive-skill nudge."""
    result = _run([_sketch_prompt()], state={})
    assert _injected_nudges(result) == []


def test_active_via_slash_fires_contract() -> None:
    result = _run([_slash_reminder(), _sketch_prompt()], state={})
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "SKETCH REMINDER" in str(nudges[0].content)


# ── Gate sequencing: idea -> sketch -> product -> business -> landing ──


def test_idea_unanswered_gets_question_nudge() -> None:
    result = _run([_sketch_prompt()], state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "Next question" in str(nudges[0].content)


def test_idea_answered_but_no_sketch_gets_sketch_nudge() -> None:
    result = _run([_idea_answered_prompt()], state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "mermaid" in str(nudges[0].content).lower()


def test_sketch_exists_but_no_product_gets_product_nudge() -> None:
    messages = [_idea_answered_prompt(), _mermaid_ai()]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "Product Description" in str(nudges[0].content)


def test_product_exists_but_no_business_gets_business_nudge() -> None:
    messages = [_idea_answered_prompt(), _mermaid_ai(), _product_ai()]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "Business Description" in str(nudges[0].content)


def test_business_exists_but_no_landing_gets_landing_nudge() -> None:
    messages = [_idea_answered_prompt(), _mermaid_ai(), _product_ai(), _business_ai()]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "landing page" in str(nudges[0].content).lower()


def test_complete_flow_is_quiet() -> None:
    messages = [_idea_answered_prompt(), _mermaid_ai(), _product_ai(), _business_ai(), _landing_ai()]
    result = _run(messages, state=_active_skill_state())
    assert _injected_nudges(result) == []


# ── Landing-page framework guard ──


def test_landing_with_framework_markers_gets_plain_html_nudge() -> None:
    framework_landing = AIMessage(
        content=(
            "<!DOCTYPE html>\n<html><head></head><body>\n"
            "<script src=\"https://cdn.example.com/app.js\"></script>\n"
            "<div class=\"container\">tailwind-based landing</div></body></html>"
        )
    )
    messages = [_idea_answered_prompt(), _mermaid_ai(), _product_ai(), _business_ai(), framework_landing]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "pure HTML" in str(nudges[0].content)


def test_pure_html_landing_passes_framework_guard() -> None:
    messages = [_idea_answered_prompt(), _mermaid_ai(), _product_ai(), _business_ai(), _landing_ai()]
    result = _run(messages, state=_active_skill_state())
    assert _injected_nudges(result) == []


def test_active_via_skill_context_fires_contract() -> None:
    result = _run([_sketch_prompt()], state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) >= 1
    assert "skill is not active" not in str(nudges[0].content)


def test_unrelated_message_after_flow_is_quiet() -> None:
    messages = [
        _idea_answered_prompt(),
        _mermaid_ai(),
        _product_ai(),
        _business_ai(),
        _landing_ai(),
        HumanMessage(content="thanks, that looks great"),
    ]
    result = _run(messages, state=_active_skill_state())
    assert _injected_nudges(result) == []
