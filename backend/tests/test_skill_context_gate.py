"""Tests for the shared skill-context activation gate.

Covers the two activation signals recognized by ``skill_is_active``:
slash activation (hidden reminder message) and loaded skill context
(``skill_context`` state entries), plus defensive edge cases.
"""

from langchain_core.messages import HumanMessage

from deerflow.agents.middlewares.skill_context import skill_is_active

SKILL = "deep-research"


def _slash_reminder(skill_name: str) -> HumanMessage:
    return HumanMessage(
        content=(
            "<slash_skill_activation>\n"
            f"The user explicitly activated the `{skill_name}` skill for this turn.\n"
            f'<skill name="{skill_name}" category="research" path="skills/public/{skill_name}" sha256="abc" editable="false">'
        ),
        additional_kwargs={"hide_from_ui": True, "slash_skill_activation": True},
    )


def _state_with_skill(name: str) -> dict:
    return {"skill_context": [{"name": name, "path": f"skills/public/{name}/SKILL.md", "description": "", "loaded_at": 0}]}


def test_loaded_skill_context_entry_matches() -> None:
    assert skill_is_active([], _state_with_skill(SKILL), SKILL) is True


def test_loaded_skill_context_entry_mismatch() -> None:
    assert skill_is_active([], _state_with_skill("system-design"), SKILL) is False


def test_slash_activation_reminder_matches() -> None:
    assert skill_is_active([_slash_reminder(SKILL)], {}, SKILL) is True


def test_slash_activation_reminder_other_skill() -> None:
    assert skill_is_active([_slash_reminder("system-design")], {}, SKILL) is False


def test_slash_reminder_without_name_in_content() -> None:
    reminder = HumanMessage(
        content="<slash_skill_activation>\nThe user activated some skill.",
        additional_kwargs={"hide_from_ui": True, "slash_skill_activation": True},
    )
    assert skill_is_active([reminder], {}, SKILL) is False


def test_none_state() -> None:
    assert skill_is_active([], None, SKILL) is False


def test_missing_skill_context_key() -> None:
    assert skill_is_active([], {}, SKILL) is False


def test_substring_name_does_not_match() -> None:
    # Exact match required: "research" must not satisfy "deep-research".
    assert skill_is_active([], _state_with_skill("research"), SKILL) is False


def test_empty_inputs() -> None:
    assert skill_is_active(None, None, SKILL) is False
    assert skill_is_active([], {}, SKILL) is False


def test_invalid_skill_name() -> None:
    assert skill_is_active([_slash_reminder(SKILL)], {}, "") is False
    assert skill_is_active([], _state_with_skill(SKILL), "") is False


def test_both_signals_one_matches() -> None:
    messages = [_slash_reminder("system-design")]
    assert skill_is_active(messages, _state_with_skill(SKILL), SKILL) is True
