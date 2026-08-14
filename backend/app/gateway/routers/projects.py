"""Project store API: cross-thread project artifact state."""

from fastapi import APIRouter, Depends, HTTPException

from deerflow.projects.store import ARTIFACT_KINDS, ProjectStore

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_project_store() -> ProjectStore:
    """Store dependency; overridable in tests."""
    return ProjectStore()


@router.get("")
async def list_projects(store: ProjectStore = Depends(get_project_store)) -> list[dict]:
    """List stored projects with artifact versions."""
    return store.list_projects()


@router.get("/{name}")
async def get_project(name: str, store: ProjectStore = Depends(get_project_store)) -> dict:
    """Return a project's artifact index."""
    index = store.get_index(name)
    if not index.get("artifacts"):
        raise HTTPException(status_code=404, detail=f"Project not found: {name}")
    return index


@router.get("/{name}/artifacts/{kind}")
async def get_project_artifact(name: str, kind: str, store: ProjectStore = Depends(get_project_store)) -> dict:
    """Return the latest content of one contract artifact."""
    if kind not in ARTIFACT_KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown artifact kind: {kind}")
    content = store.read_artifact(name, kind)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {name}/{kind}")
    return {"project": name, "kind": kind, "content": content}
