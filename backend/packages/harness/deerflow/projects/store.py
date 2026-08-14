"""File-based project store: versioned contract artifacts across threads.

Layout under ``DEER_FLOW_HOME/projects``::

    <safe-project-name>/
        project.json            # index: name, timestamps, artifact versions + hashes
        artifacts/
            brd.md              # latest content per artifact kind
            brd.v1.md           # historical versions
            brd.v2.md

Versioning is content-driven: an artifact is only written (and versioned)
when its sha256 differs from the last saved version. Unchanged documents
never bump versions.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

from deerflow.config.runtime_paths import runtime_home

ARTIFACT_KINDS: tuple[str, ...] = ("brd", "prd", "srs", "sad")

# Document markers aligned with the requirements pipeline middlewares.
# SAD is checked first: a traceable SAD legitimately contains SRS markers
# (| requirement id |) and must not be misclassified as an SRS.
_ARTIFACT_MARKERS: dict[str, tuple[str, ...]] = {
    "sad": ("# system design",),
    "brd": ("# brd", "business requirements document"),
    "prd": ("# prd", "product vision"),
    "srs": ("software requirements specification", "| requirement id |"),
}

_MAX_ARTIFACT_BYTES = 512 * 1024
_SAFE_NAME_PATTERN = re.compile(r"[^a-z0-9\-_]+")


def safe_project_name(name: str) -> str:
    """Normalize a user-supplied project name into a filesystem-safe slug."""
    slug = _SAFE_NAME_PATTERN.sub("-", name.strip().lower()).strip("-")
    if not slug or slug in {".", ".."}:
        raise ValueError(f"Invalid project name: {name!r}")
    return slug[:64]


def detect_artifact_kind(content: str) -> str | None:
    """Return the contract kind of an AI message body, or None."""
    lowered = content.lower()
    for kind, markers in _ARTIFACT_MARKERS.items():
        if any(marker in lowered for marker in markers):
            return kind
    return None


class ProjectStore:
    """Versioned artifact persistence under DEER_FLOW_HOME/projects."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or runtime_home() / "projects").resolve()

    def _project_dir(self, project: str) -> Path:
        return self._root / safe_project_name(project)

    def _artifacts_dir(self, project: str) -> Path:
        return self._project_dir(project) / "artifacts"

    def _index_path(self, project: str) -> Path:
        return self._project_dir(project) / "project.json"

    def _load_index(self, project: str) -> dict:
        try:
            return json.loads(self._index_path(project).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _write_index(self, project: str, index: dict) -> None:
        path = self._index_path(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def save_artifact(self, project: str, kind: str, content: str) -> dict | None:
        """Persist an artifact version.

        Returns the new index entry, or None when the content is unchanged
        (deduplicated by sha256) or empty.
        """
        if kind not in ARTIFACT_KINDS:
            raise ValueError(f"Unknown artifact kind: {kind}")
        content = content.strip()
        if not content:
            return None
        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_ARTIFACT_BYTES:
            encoded = encoded[:_MAX_ARTIFACT_BYTES]
            content = encoded.decode("utf-8", errors="ignore")
        digest = hashlib.sha256(encoded).hexdigest()

        index = self._load_index(project)
        artifacts = index.setdefault("artifacts", {})
        entry = artifacts.get(kind)
        if isinstance(entry, dict) and entry.get("sha256") == digest:
            return None

        version = (entry.get("version") + 1) if isinstance(entry, dict) else 1
        artifacts_dir = self._artifacts_dir(project)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / f"{kind}.md").write_text(content, encoding="utf-8")
        (artifacts_dir / f"{kind}.v{version}.md").write_text(content, encoding="utf-8")

        entry = {
            "version": version,
            "sha256": digest,
            "updated_at": time.time(),
            "chars": len(content),
        }
        artifacts[kind] = entry
        index.setdefault("name", safe_project_name(project))
        index.setdefault("created_at", time.time())
        index["updated_at"] = time.time()
        self._write_index(project, index)
        return entry

    def list_projects(self) -> list[dict]:
        """List all stored projects with their artifact version map."""
        if not self._root.exists():
            return []
        projects: list[dict] = []
        for child in sorted(self._root.iterdir()):
            if not child.is_dir():
                continue
            try:
                index = json.loads((child / "project.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                continue
            projects.append(
                {
                    "name": index.get("name", child.name),
                    "created_at": index.get("created_at"),
                    "updated_at": index.get("updated_at"),
                    "artifacts": {
                        kind: entry.get("version")
                        for kind, entry in index.get("artifacts", {}).items()
                        if isinstance(entry, dict)
                    },
                }
            )
        return projects

    def get_index(self, project: str) -> dict:
        """Return the raw project index (empty dict when unknown)."""
        return self._load_index(project)

    def read_artifact(self, project: str, kind: str) -> str | None:
        """Return the latest content for an artifact kind, or None."""
        if kind not in ARTIFACT_KINDS:
            raise ValueError(f"Unknown artifact kind: {kind}")
        try:
            return (self._artifacts_dir(project) / f"{kind}.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            return None

    def resume_summary(self, project: str, char_budget_per_artifact: int = 4000) -> str:
        """Render the project context block injected on cross-thread resume."""
        index = self._load_index(project)
        artifacts = index.get("artifacts", {})
        parts: list[str] = []
        for kind in ARTIFACT_KINDS:
            entry = artifacts.get(kind)
            if not isinstance(entry, dict):
                continue
            content = self.read_artifact(project, kind) or ""
            if len(content) > char_budget_per_artifact:
                head = char_budget_per_artifact * 2 // 3
                tail = max(0, char_budget_per_artifact - head)
                content = content[:head] + "\n...\n" + (content[-tail:] if tail else "")
            parts.append(f"## {kind.upper()} (v{entry.get('version')})\n{content}")
        if not parts:
            return ""
        return (
            f"<project_context>\nProject: {index.get('name', project)}\n\n"
            + "\n\n".join(parts)
            + "\n</project_context>"
        )
