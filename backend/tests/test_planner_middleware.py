"""Tests for PlannerMiddleware's plan-first enforcement."""

import asyncio
from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.planner_middleware import PlannerMiddleware
from deerflow.config.planner_config import PlannerConfig


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _run(messages: list, state: dict | None = None, config: PlannerConfig | None = None) -> ModelRequest:
    middleware = PlannerMiddleware(planner_config=config or PlannerConfig())
    return middleware.wrap_model_call(_request(messages, state), lambda req: req)


def _injected(result: ModelRequest) -> list[HumanMessage]:
    return [
        msg
        for msg in result.messages
        if isinstance(msg, HumanMessage) and "PLANNER REMINDER" in str(msg.content)
    ]


def _complex_two_verbs() -> HumanMessage:
    return HumanMessage(
        content="Please add user authentication and refactor the error handling in the api module."
    )


def _numbered_request() -> HumanMessage:
    return HumanMessage(content="Do the following for me:\n1. Add a config loader\n2. Fix the import cycle\n3. Update the tests")


def _file_request() -> HumanMessage:
    return HumanMessage(content="Update the schema in models.py and the routes in api.py to match it.")


def _plan_ai() -> AIMessage:
    return AIMessage(content="## Plan\n1. Add auth middleware in auth.py\n2. Refactor errors in errors.py")


def _edit_call(path: str, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "write_file", "args": {"path": path, "content": "x"}, "id": call_id}],
    )


def _edit_ok(call_id: str) -> ToolMessage:
    return ToolMessage(content="OK", name="write_file", tool_call_id=call_id)


# ── Classification ──


def test_trivial_message_passes_through() -> None:
    result = _run([HumanMessage(content="hello there")])
    assert _injected(result) == []


def test_short_multi_verb_message_not_complex() -> None:
    result = _run([HumanMessage(content="add and remove")])
    assert _injected(result) == []


def test_two_verbs_classify_multi_step() -> None:
    result = _run([_complex_two_verbs()])
    nudges = _injected(result)
    assert len(nudges) == 1
    assert "numbered plan" in str(nudges[0].content)


def test_numbered_directive_classifies_multi_step() -> None:
    result = _run([_numbered_request()])
    assert len(_injected(result)) == 1


def test_file_mentions_classify_multi_step() -> None:
    result = _run([_file_request()])
    assert len(_injected(result)) == 1


# ── Gate A: plan first ──


def test_plan_in_exchange_satisfies_gate_a() -> None:
    result = _run([_complex_two_verbs(), _plan_ai()])
    assert _injected(result) == []


def test_todos_state_satisfies_gate_a() -> None:
    state = {"todos": [{"id": "t1", "content": "plan step"}]}
    result = _run([_complex_two_verbs()], state=state)
    assert _injected(result) == []


# ── Gate B: edits without plan ──


def test_edits_without_plan_get_stop_nudge() -> None:
    messages = [_complex_two_verbs(), _edit_call("auth.py", "call-1"), _edit_ok("call-1")]
    nudges = _injected(_run(messages))
    assert len(nudges) == 1
    assert "STOP" in str(nudges[0].content)


def test_error_edit_completion_ignored() -> None:
    messages = [
        _complex_two_verbs(),
        _edit_call("auth.py", "call-1"),
        ToolMessage(content="Error", name="write_file", tool_call_id="call-1", status="error"),
    ]
    # No successful edits: falls back to Gate A (plan first), not STOP.
    nudges = _injected(_run(messages))
    assert len(nudges) == 1
    assert "STOP" not in str(nudges[0].content)


# ── Gate C: deviation ──


def test_edit_path_in_plan_is_quiet() -> None:
    messages = [
        _complex_two_verbs(),
        _plan_ai(),
        _edit_call("auth.py", "call-1"),
        _edit_ok("call-1"),
    ]
    assert _injected(_run(messages)) == []


def test_edit_path_not_in_plan_gets_deviation_nudge() -> None:
    messages = [
        _complex_two_verbs(),
        _plan_ai(),
        _edit_call("unplanned.py", "call-1"),
        _edit_ok("call-1"),
    ]
    nudges = _injected(_run(messages))
    assert len(nudges) == 1
    assert "does not appear in the plan" in str(nudges[0].content)
    assert "unplanned.py" in str(nudges[0].content)


# ── Re-arm and lifecycle ──


def test_new_trivial_message_rearms_silently() -> None:
    messages = [
        _complex_two_verbs(),
        _edit_call("auth.py", "call-1"),
        _edit_ok("call-1"),
        HumanMessage(content="thanks"),
    ]
    assert _injected(_run(messages)) == []


def test_disabled_config_stays_silent() -> None:
    config = PlannerConfig(enabled=False)
    result = _run([_complex_two_verbs()], config=config)
    assert _injected(result) == []


def test_awrap_model_call_injects_plan_nudge() -> None:
    middleware = PlannerMiddleware(planner_config=PlannerConfig())

    async def handler(req: ModelRequest) -> ModelRequest:
        return req

    result = asyncio.run(middleware.awrap_model_call(_request([_complex_two_verbs()]), handler))
    assert len(_injected(result)) == 1


def test_config_defaults() -> None:
    config = PlannerConfig()
    assert config.enabled is True
    assert config.min_chars == 40
    assert config.min_plan_steps == 2
    assert "refactor" in config.action_verbs
    assert "py" in config.file_extensions
