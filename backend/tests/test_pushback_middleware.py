"""Tests for PushbackMiddleware's informed-consent enforcement."""

import asyncio
from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.pushback_middleware import PushbackMiddleware
from deerflow.config.pushback_config import PushbackConfig


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _run(messages: list, config: PushbackConfig | None = None) -> ModelRequest:
    middleware = PushbackMiddleware(pushback_config=config or PushbackConfig())
    return middleware.wrap_model_call(_request(messages), lambda req: req)


def _injected(result: ModelRequest) -> list[HumanMessage]:
    return [
        msg
        for msg in result.messages
        if isinstance(msg, HumanMessage) and "PUSHBACK REMINDER" in str(msg.content)
    ]


# ── Silence ──


def test_no_commitment_history_passes_through() -> None:
    result = _run([HumanMessage(content="please add a config loader to the project")])
    assert _injected(result) == []


def test_trivial_message_passes_through() -> None:
    result = _run([HumanMessage(content="hi")])
    assert _injected(result) == []


def test_disabled_config_stays_silent() -> None:
    config = PushbackConfig(enabled=False)
    result = _run(
        [
            HumanMessage(content="we will never use docker for deployment in this project"),
            HumanMessage(content="please add docker support to the deployment setup"),
        ],
        config=config,
    )
    assert _injected(result) == []


# ── Hard conflicts ──


def test_hard_commitment_then_reversal_gets_confirm_nudge() -> None:
    messages = [
        HumanMessage(content="we will never use docker for deployment in this project"),
        HumanMessage(content="please add docker support to the deployment setup"),
    ]
    nudges = _injected(_run(messages))
    assert len(nudges) == 1
    assert "confirm" in str(nudges[0].content).lower()
    assert "docker" in str(nudges[0].content)


def test_same_polarity_commitment_no_nudge() -> None:
    messages = [
        HumanMessage(content="we will never use docker for deployment"),
        HumanMessage(content="please avoid docker in the deployment as well"),
    ]
    assert _injected(_run(messages)) == []


# ── Soft conflicts ──


def test_soft_commitment_then_removal_gets_tradeoff_nudge() -> None:
    messages = [
        HumanMessage(content="we must always keep the planner middleware enabled in this project"),
        HumanMessage(content="please remove the planner middleware from the chain"),
    ]
    nudges = _injected(_run(messages))
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "tradeoff" in content.lower()
    assert "proceed" in content.lower()


# ── Memory avoid facts ──


def test_memory_avoid_fact_creates_hard_commitment() -> None:
    memory = HumanMessage(
        content="<memory>\nFacts:\n- [correction] avoid: agent must never generate DOCX files in this environment\n</memory>",
        additional_kwargs={"hide_from_ui": True},
    )
    messages = [memory, HumanMessage(content="please generate a DOCX version of the report for me")]
    nudges = _injected(_run(messages))
    assert len(nudges) == 1
    assert "confirm" in str(nudges[0].content).lower()


# ── Discharge ──


def test_tradeoff_voiced_discharges_obligation() -> None:
    messages = [
        HumanMessage(content="we will never use docker for deployment in this project"),
        HumanMessage(content="please add docker support to the deployment setup"),
        AIMessage(
            content=(
                "Tradeoff: docker adds portability but contradicts your earlier no-docker "
                "constraint. I will proceed if you confirm."
            )
        ),
    ]
    assert _injected(_run(messages)) == []


def test_new_user_message_rearms() -> None:
    messages = [
        HumanMessage(content="we will never use docker for deployment"),
        HumanMessage(content="please add docker support"),
        HumanMessage(content="thanks, moving on"),
    ]
    assert _injected(_run(messages)) == []


def test_unrelated_directive_no_nudge() -> None:
    messages = [
        HumanMessage(content="we will never use docker for deployment"),
        HumanMessage(content="please add a logging section to the documentation"),
    ]
    assert _injected(_run(messages)) == []


# ── Lifecycle and defaults ──


def test_awrap_model_call_injects_nudge() -> None:
    middleware = PushbackMiddleware(pushback_config=PushbackConfig())

    async def handler(req: ModelRequest) -> ModelRequest:
        return req

    result = asyncio.run(
        middleware.awrap_model_call(
            _request(
                [
                    HumanMessage(content="we will never use docker for deployment"),
                    HumanMessage(content="please add docker support to the deployment"),
                ]
            ),
            handler,
        )
    )
    assert len(_injected(result)) == 1


def test_config_defaults() -> None:
    config = PushbackConfig()
    assert config.enabled is True
    assert config.min_chars == 30
    assert config.lookback == 24
    assert "never" in config.hard_markers
    assert "always" in config.soft_markers
    assert "remove" in config.negative_verbs
    assert "add" in config.positive_verbs
    assert "tradeoff" in config.tradeoff_markers
