"""Tests for the projects gateway router."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.gateway.routers.projects import get_project_store, router
from deerflow.projects.store import ProjectStore

_BRD = "# BRD: Demo\n\n## Business Objectives\n- BR-01 Revenue"


@pytest.fixture
def client(tmp_path) -> TestClient:
    store = ProjectStore(root=tmp_path)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_project_store] = lambda: store
    return TestClient(app)


def test_list_projects_empty(client) -> None:
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_project_lifecycle(client, tmp_path) -> None:
    store = ProjectStore(root=tmp_path)
    store.save_artifact("demo", "brd", _BRD)

    listing = client.get("/api/projects").json()
    assert [p["name"] for p in listing] == ["demo"]
    assert listing[0]["artifacts"]["brd"] == 1

    index = client.get("/api/projects/demo").json()
    assert index["artifacts"]["brd"]["version"] == 1

    artifact = client.get("/api/projects/demo/artifacts/brd").json()
    assert artifact["content"] == _BRD


def test_unknown_project_404(client) -> None:
    assert client.get("/api/projects/missing").status_code == 404
    assert client.get("/api/projects/missing/artifacts/brd").status_code == 404


def test_unknown_artifact_kind_404(client) -> None:
    assert client.get("/api/projects/demo/artifacts/evil").status_code == 404
