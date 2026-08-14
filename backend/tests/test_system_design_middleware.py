"""Tests for SystemDesignMiddleware's forced skill-context gate."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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


def _intake_prompt(greenfield: bool) -> HumanMessage:
    tail = "greenfield project with no existing code." if greenfield else "existing Flask app to integrate with."
    return HumanMessage(
        content=(
            "Design the architecture for my note sync system. The goal is offline-first sync; "
            "must-have: real-time sync, priority: reliability. It runs on my personal machine "
            "for 5 users. Budget zero, timeline 2 weeks, platform Windows, solo dev, " + tail
        )
    )


def test_intake_blocks_when_wanting_and_constraints_missing() -> None:
    messages = [
        HumanMessage(
            content=(
                "Design the architecture for a system with 5 users running on my personal "
                "machine with a database backend."
            )
        )
    ]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "Grounded intake is incomplete" in str(nudges[0].content)


def test_reality_gate_blocks_before_inspection() -> None:
    messages = [_intake_prompt(greenfield=False)]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "reality has not been inspected" in str(nudges[0].content)


def test_greenfield_statement_waives_reality_gate() -> None:
    messages = [_intake_prompt(greenfield=True)]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "Requirements are not established" in content
    assert "reality has not been inspected" not in content


def test_reality_inspection_evidence_satisfies_gate() -> None:
    messages = [
        _intake_prompt(greenfield=False),
        ToolMessage(content="repo root listing", name="read_file", tool_call_id="call-read-1"),
    ]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "Requirements are not established" in str(nudges[0].content)


def _mature_design_messages() -> list:
    return [
        _intake_prompt(greenfield=True),
        ToolMessage(content="q1", name="web_search", tool_call_id="s1"),
        ToolMessage(content="q2", name="web_search", tool_call_id="s2"),
        ToolMessage(content="q3", name="web_search", tool_call_id="s3"),
        ToolMessage(content="q4", name="web_search", tool_call_id="s4"),
        ToolMessage(content="u1", name="web_fetch", tool_call_id="f1"),
        ToolMessage(content="u2", name="web_fetch", tool_call_id="f2"),
        AIMessage(
            content=(
                "## Scope\n## Functional Requirements\n## Non-Functional Requirements\n"
                "```mermaid\ngraph TD\n A --> B\n```\n"
                "| component | api | http |\n"
                "storage, database, communication async, write path, read path, "
                "deployment topology, tradeoff, | risk |, build order, https://example.com, ok?"
            )
        ),
    ]


def test_grounding_gates_fire_for_mature_design_without_unknowns_or_traceability() -> None:
    result = _run(_mature_design_messages(), state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 2
    joined = " ".join(str(n.content) for n in nudges)
    assert "UNKNOWN" in joined
    assert "Traceability" in joined


def test_grounding_gates_clear_when_unknowns_and_traceability_present() -> None:
    messages = _mature_design_messages()
    ai = messages[-1]
    messages[-1] = AIMessage(
        content=str(ai.content) + " UNKNOWN: none. Traceability: | decision | requirement | ok?"
    )
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert nudges == []


def _chain_docs() -> list:
    return [
        AIMessage(
            content=(
                "# BRD: Note Sync\n## Business Objectives\n- BR-01 Retention\n"
                "budget $0, timeline 2 weeks, solo dev, goal: offline-first sync"
            )
        ),
        AIMessage(
            content=(
                "# PRD: Note Sync\n## Product Vision\nFor users who need sync.\n"
                "## Personas\n| Persona | Goals |\n| Saver | sync |\n"
                "must-have sync, priority reliability, mobile, personal use, 5 users"
            )
        ),
        AIMessage(
            content=(
                "# Software Requirements Specification: Note Sync\n"
                "## Functional Requirements\n| requirement id | REQ-001 |\n"
                "## Data Dictionary\n| Field | Type |\ngreenfield project, no existing code"
            )
        ),
    ]


def test_chain_docs_satisfy_intake_and_reality_gates() -> None:
    messages = [_design_prompt(), *_chain_docs()]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "Grounded intake is incomplete" not in content
    assert "reality has not been inspected" not in content


def test_chain_docs_without_wanting_fall_back_to_interview() -> None:
    docs = [
        AIMessage(
            content=(
                "# Software Requirements Specification: Note Sync\n"
                "## Functional Requirements\n| requirement id | REQ-001 |\n"
                "budget $0, timeline 2 weeks, solo dev, personal use, 5 users"
            )
        )
    ]
    messages = [_design_prompt(), *docs]
    result = _run(messages, state=_active_skill_state())
    nudges = _injected_nudges(result)
    assert len(nudges) == 1
    assert "Grounded intake is incomplete" in str(nudges[0].content)
