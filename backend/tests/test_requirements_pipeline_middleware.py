"""Tests for RequirementsPipelineMiddleware's BRD -> PRD -> SRS chaining."""

from unittest.mock import MagicMock

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.runtime import Runtime

from deerflow.agents.middlewares.requirements_pipeline_middleware import (
    RequirementsPipelineMiddleware,
)


def _request(messages: list, state: dict | None = None) -> ModelRequest:
    return ModelRequest(
        model=MagicMock(),
        messages=messages,
        tools=[],
        state=state or {},
        runtime=Runtime(context={}),
    )


def _skill_state(name: str, loaded_at: int = 1) -> dict:
    return {
        "skill_context": [
            {"name": name, "path": f"skills/public/{name}/SKILL.md", "description": "", "loaded_at": loaded_at}
        ]
    }


def _slash_reminder(skill_name: str) -> HumanMessage:
    return HumanMessage(
        content=(
            "<slash_skill_activation>\n"
            f"The user explicitly activated the `{skill_name}` skill for this turn.\n"
            f'<skill name="{skill_name}" category="business" path="skills/public/{skill_name}" sha256="abc" editable="false">'
        ),
        additional_kwargs={"hide_from_ui": True, "slash_skill_activation": True},
    )


_BRD_DOC = AIMessage(content="# BRD: Project X\n\n## Business Objectives\n- Objective 1\n- Objective 2\n\nBR-01 Revenue\nBR-02 Retention")
_PRD_DOC = AIMessage(content="# PRD: Expense Tracker\n\n## Product Vision\nFor users who need budgeting.\n\n## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |")
_PRD_DOC_TRACEABLE = AIMessage(
    content=(
        "# PRD: Expense Tracker\n\n## Product Vision\nFor users who need budgeting.\n\n"
        "## Personas\n| Persona | Goals | Pain Points |\n| Saver | save | overspending |\n\n"
        "Traces to BRD objective BR-01 (retention)"
    )
)
_SRS_DOC = AIMessage(content="# Software Requirements Specification: Expense Tracker\n\n## Data Dictionary\n| Field | Type | Required |")
_SRS_DOC_TRACEABLE = AIMessage(content="# Software Requirements Specification: Expense Tracker\n\n## Data Dictionary\n| Field | Type | Required |\n\n| Requirement ID | Type | Source | Test Case |\n| REQ-001 | Functional | US-01 | TC-001 |")


def _nudges(messages: list, state: dict) -> list[HumanMessage]:
    return RequirementsPipelineMiddleware()._build_nudges(messages, state)


# ── Activation scope ──


def test_no_chain_skill_active_no_nudges() -> None:
    assert _nudges([HumanMessage(content="hello there")], {}) == []


def test_brd_only_no_nudges() -> None:
    messages = [HumanMessage(content="business case for X")]
    assert _nudges(messages, _skill_state("business-requirement")) == []


def test_pipeline_passes_through_when_inactive() -> None:
    middleware = RequirementsPipelineMiddleware()
    messages = [HumanMessage(content="write me a PRD")]
    result = middleware.wrap_model_call(_request(messages, {}), lambda req: req)
    assert list(result.messages) == messages


# ── PRD stage ──


def test_prd_without_brd_gets_brd_first_nudge() -> None:
    messages = [HumanMessage(content="write a PRD for an expense tracker")]
    nudges = _nudges(messages, _skill_state("product-requirements"))
    assert len(nudges) == 1
    content = str(nudges[0].content)
    assert "Business case first" in content
    assert "PIPELINE REMINDER" in content


def test_prd_produced_without_brd_escalates() -> None:
    messages = [HumanMessage(content="write a PRD"), _PRD_DOC]
    nudges = _nudges(messages, _skill_state("product-requirements"))
    assert len(nudges) == 1
    assert "STOP" in str(nudges[0].content)


def test_prd_without_brd_waived_no_nudges() -> None:
    messages = [HumanMessage(content="write a PRD, skip the BRD")]
    assert _nudges(messages, _skill_state("product-requirements")) == []


def test_prd_after_brd_not_traceable_gets_traceability_nudge() -> None:
    messages = [HumanMessage(content="write a PRD"), _BRD_DOC, _PRD_DOC]
    nudges = _nudges(messages, _skill_state("product-requirements"))
    assert len(nudges) == 1
    assert "trace" in str(nudges[0].content).lower() or "Map each PRD" in str(nudges[0].content)


def test_prd_after_brd_traceable_no_nudges() -> None:
    messages = [HumanMessage(content="write a PRD"), _BRD_DOC, _PRD_DOC_TRACEABLE]
    assert _nudges(messages, _skill_state("product-requirements")) == []


def test_prd_via_slash_activation_is_detected() -> None:
    messages = [_slash_reminder("product-requirements"), HumanMessage(content="write a PRD")]
    nudges = _nudges(messages, {})
    assert len(nudges) == 1
    assert "Business case first" in str(nudges[0].content)


# ── SRS stage ──


def test_srs_without_prd_gets_prd_first_nudge() -> None:
    messages = [HumanMessage(content="write an SRS for the expense tracker")]
    nudges = _nudges(messages, _skill_state("software-requirements"))
    assert len(nudges) == 1
    assert "Product definition first" in str(nudges[0].content)


def test_srs_without_prd_waived_no_nudges() -> None:
    messages = [HumanMessage(content="write an SRS, straight to SRS, skip the PRD")]
    assert _nudges(messages, _skill_state("software-requirements")) == []


def test_srs_after_prd_not_traceable_gets_traceability_nudge() -> None:
    messages = [HumanMessage(content="write an SRS"), _PRD_DOC, _SRS_DOC]
    nudges = _nudges(messages, _skill_state("software-requirements"))
    assert len(nudges) == 1
    assert "traceability matrix" in str(nudges[0].content)


def test_srs_after_prd_traceable_no_nudges() -> None:
    messages = [HumanMessage(content="write an SRS"), _PRD_DOC, _SRS_DOC_TRACEABLE]
    assert _nudges(messages, _skill_state("software-requirements")) == []


def test_srs_produced_without_prd_escalates() -> None:
    messages = [HumanMessage(content="write an SRS"), _SRS_DOC]
    nudges = _nudges(messages, _skill_state("software-requirements"))
    assert len(nudges) == 1
    assert "STOP" in str(nudges[0].content)


# ── Multi-skill resolution ──


def test_latest_slash_activation_wins() -> None:
    state = _skill_state("product-requirements")
    state["skill_context"] = [
        {"name": "business-requirement", "path": "skills/public/business-requirement/SKILL.md", "description": "", "loaded_at": 1},
        {"name": "product-requirements", "path": "skills/public/product-requirements/SKILL.md", "description": "", "loaded_at": 2},
    ]
    messages = [HumanMessage(content="write a PRD"), _BRD_DOC]
    # Latest loaded skill is product-requirements, BRD exists, PRD not produced
    # yet -> no BRD-first nudge (BRD exists) and no traceability nudge (no PRD).
    assert _nudges(messages, state) == []


def test_full_chain_after_waivers_is_quiet() -> None:
    state = {
        "skill_context": [
            {"name": "software-requirements", "path": "skills/public/software-requirements/SKILL.md", "description": "", "loaded_at": 3},
        ]
    }
    messages = [
        HumanMessage(content="skip the BRD"),
        HumanMessage(content="skip the PRD, straight to SRS"),
        _SRS_DOC,
    ]
    assert _nudges(messages, state) == []
