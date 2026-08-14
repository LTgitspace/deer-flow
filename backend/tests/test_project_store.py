"""Tests for the file-based ProjectStore."""

import pytest

from deerflow.projects.store import ProjectStore, detect_artifact_kind, safe_project_name


@pytest.fixture
def store(tmp_path) -> ProjectStore:
    return ProjectStore(root=tmp_path)


_BRD = "# BRD: Demo\n\n## Business Objectives\n- BR-01 Revenue"
_PRD = "# PRD: Demo\n\n## Product Vision\nFor users who need budgeting."
_SRS = "# Software Requirements Specification: Demo\n\n| Requirement ID | Type |\n| REQ-001 | Functional |"
_SAD = "# System Design: Demo\n\n## Architecture Overview\n```mermaid\ngraph TD\n A --> B\n```\n| requirement id | REQ-001 |"


def test_save_and_read_artifact(store) -> None:
    entry = store.save_artifact("Demo App", "brd", _BRD)
    assert entry is not None
    assert entry["version"] == 1
    assert store.read_artifact("Demo App", "brd") == _BRD


def test_unchanged_content_does_not_bump_version(store) -> None:
    first = store.save_artifact("demo", "brd", _BRD)
    again = store.save_artifact("demo", "brd", _BRD)
    assert again is None
    assert store.get_index("demo")["artifacts"]["brd"]["version"] == first["version"]


def test_changed_content_bumps_version(store) -> None:
    store.save_artifact("demo", "brd", _BRD)
    entry = store.save_artifact("demo", "brd", _BRD + "\n- BR-02 Retention")
    assert entry is not None
    assert entry["version"] == 2
    assert store.read_artifact("demo", "brd").endswith("BR-02 Retention")


def test_list_projects(store) -> None:
    store.save_artifact("alpha", "brd", _BRD)
    store.save_artifact("beta", "srs", _SRS)
    projects = store.list_projects()
    names = {project["name"] for project in projects}
    assert names == {"alpha", "beta"}
    beta = next(p for p in projects if p["name"] == "beta")
    assert beta["artifacts"]["srs"] == 1


def test_unknown_project_index_is_empty(store) -> None:
    assert store.get_index("missing") == {}
    assert store.read_artifact("missing", "brd") is None


def test_resume_summary_renders_all_artifacts(store) -> None:
    store.save_artifact("demo", "brd", _BRD)
    store.save_artifact("demo", "srs", _SRS)
    summary = store.resume_summary("demo")
    assert "<project_context>" in summary
    assert "## BRD (v1)" in summary
    assert "## SRS (v1)" in summary
    assert "REQ-001" in summary


def test_resume_summary_empty_project(store) -> None:
    assert store.resume_summary("empty") == ""


def test_invalid_artifact_kind_rejected(store) -> None:
    with pytest.raises(ValueError):
        store.save_artifact("demo", "evil", "content")
    with pytest.raises(ValueError):
        store.read_artifact("demo", "evil")


def test_project_name_sanitization() -> None:
    assert safe_project_name("Demo App!") == "demo-app"
    assert safe_project_name("My_Project-v2") == "my_project-v2"
    with pytest.raises(ValueError):
        safe_project_name("..")
    with pytest.raises(ValueError):
        safe_project_name("...")


def test_detect_artifact_kind_orders_sad_before_srs() -> None:
    assert detect_artifact_kind(_BRD) == "brd"
    assert detect_artifact_kind(_PRD) == "prd"
    assert detect_artifact_kind(_SRS) == "srs"
    # A traceable SAD contains an SRS marker; SAD must win.
    assert detect_artifact_kind(_SAD) == "sad"
    assert detect_artifact_kind("hello world") is None
