"""Tests for ProjectStateMiddleware's cross-thread artifact capture and resume."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.project_state_middleware import ProjectStateMiddleware
from deerflow.projects.store import ProjectStore

_BRD = "# BRD: Demo\n\n## Business Objectives\n- BR-01 Revenue"
_SRS = "# Software Requirements Specification: Demo\n\n| Requirement ID | Type |\n| REQ-001 | Functional |"


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _middleware(tmp_path) -> ProjectStateMiddleware:
    return ProjectStateMiddleware(store=ProjectStore(root=tmp_path))


def _injected(result: ModelRequest) -> list[HumanMessage]:
    return [
        msg
        for msg in result.messages
        if isinstance(msg, HumanMessage)
        and (msg.additional_kwargs or {}).get("project_context")
    ]


def test_no_project_binding_passes_through(tmp_path) -> None:
    middleware = _middleware(tmp_path)
    result = middleware.wrap_model_call(_request([HumanMessage(content="hello")]), lambda req: req)
    assert list(result.messages) == [HumanMessage(content="hello")]


def test_binding_detection_patterns(tmp_path) -> None:
    middleware = _middleware(tmp_path)
    for text in ("/project demo", "project: demo", "continue project demo", "open project demo"):
        result = middleware.wrap_model_call(_request([HumanMessage(content=text)]), lambda req: req)
        assert len(result.messages) == 1  # no artifacts stored yet, nothing injected


def test_artifacts_extracted_from_ai_messages(tmp_path) -> None:
    store = ProjectStore(root=tmp_path)
    middleware = ProjectStateMiddleware(store=store)
    messages = [
        HumanMessage(content="/project demo"),
        AIMessage(content=_BRD),
    ]
    middleware.wrap_model_call(_request(messages, state={"project": "demo"}), lambda req: req)
    assert store.read_artifact("demo", "brd") == _BRD


def test_resume_injection_on_binding(tmp_path) -> None:
    store = ProjectStore(root=tmp_path)
    store.save_artifact("demo", "srs", _SRS)
    middleware = ProjectStateMiddleware(store=store)
    result = middleware.wrap_model_call(_request([HumanMessage(content="/project demo")]), lambda req: req)
    injected = _injected(result)
    assert len(injected) == 1
    assert "REQ-001" in str(injected[0].content)
    assert injected[0].additional_kwargs["hide_from_ui"] is True


def test_resume_injection_on_project_state_phrase(tmp_path) -> None:
    store = ProjectStore(root=tmp_path)
    store.save_artifact("demo", "brd", _BRD)
    middleware = ProjectStateMiddleware(store=store)
    result = middleware.wrap_model_call(
        _request([HumanMessage(content="where is the project")], state={"project": "demo"}),
        lambda req: req,
    )
    injected = _injected(result)
    assert len(injected) == 1
    assert "BR-01" in str(injected[0].content)


def test_no_resume_when_store_empty(tmp_path) -> None:
    middleware = _middleware(tmp_path)
    result = middleware.wrap_model_call(_request([HumanMessage(content="/project fresh")]), lambda req: req)
    assert _injected(result) == []


def test_no_resume_on_plain_message_with_bound_project(tmp_path) -> None:
    store = ProjectStore(root=tmp_path)
    store.save_artifact("demo", "brd", _BRD)
    middleware = ProjectStateMiddleware(store=store)
    result = middleware.wrap_model_call(
        _request([HumanMessage(content="what should we do next?")], state={"project": "demo"}),
        lambda req: req,
    )
    assert _injected(result) == []


def test_before_model_binds_project_channel(tmp_path) -> None:
    middleware = _middleware(tmp_path)
    state = {"messages": [HumanMessage(content="/project demo")]}
    update = middleware.before_model(state, Runtime(context={}))
    assert update == {"project": "demo"}


def test_after_model_captures_new_artifact(tmp_path) -> None:
    store = ProjectStore(root=tmp_path)
    middleware = ProjectStateMiddleware(store=store)
    state = {
        "messages": [HumanMessage(content="/project demo"), AIMessage(content=_SRS)],
        "project": "demo",
    }
    update = middleware.after_model(state, Runtime(context={}))
    assert update is None  # no state write; persistence happens in the store
    assert store.read_artifact("demo", "srs") == _SRS


def test_awrap_model_call_injects_resume(tmp_path) -> None:
    import asyncio

    store = ProjectStore(root=tmp_path)
    store.save_artifact("demo", "prd", "# PRD: Demo\n\n## Product Vision\nFor users who need budgeting.")
    middleware = ProjectStateMiddleware(store=store)

    async def handler(req: ModelRequest) -> ModelRequest:
        return req

    result = asyncio.run(middleware.awrap_model_call(_request([HumanMessage(content="/project demo")]), handler))
    assert len(_injected(result)) == 1
