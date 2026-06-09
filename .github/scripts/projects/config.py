"""Load the GitHub identity from ``.github/config.json`` and derive paths.

GitHub identity (project / repo / owner / number) is externalized to
``.github/config.json``; edit that file to retarget. Repo-relative paths are
derived here because they track the repo layout, not the GitHub project.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# config.py → projects/ → scripts/ → .github/ → repo root.
_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"
_CONFIG: dict[str, Any] = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))

PROJECT: str = _CONFIG["project"]
REPO: str = _CONFIG["repo"]
OWNER: str = _CONFIG["owner"]
PROJECT_NUMBER: int = _CONFIG["project_number"]

REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_PATHS = {
    "backlog": str(REPO_ROOT / "project" / "backlog.json"),
}


@dataclass(frozen=True)
class Identity:
    """GitHub Projects identity passed to every workflow function."""

    repo: str
    project: int
    owner: str


def resolve_identity(
    repo: str | None = None,
    project: int | None = None,
    owner: str | None = None,
) -> Identity:
    """Resolve a full identity, falling back to the config.json defaults."""
    return Identity(
        repo=repo or REPO,
        project=project or PROJECT_NUMBER,
        owner=owner or OWNER,
    )
