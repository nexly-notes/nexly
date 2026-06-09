"""Project configuration — GitHub identity loaded from .github/config.json.

The GitHub identity (project / repo / owner / number) is externalized to
``.github/config.json``; edit that file to retarget. Repo-relative data paths
are derived here because they track the repo layout, not the GitHub project.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# config.py → project_manager/ → .github/ → repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"
_CONFIG: dict[str, Any] = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))

PROJECT: str = _CONFIG["project"]
REPO: str = _CONFIG["repo"]
OWNER: str = _CONFIG["owner"]
PROJECT_NUMBER: int = _CONFIG["project_number"]

DATA_PATHS = {
    "backlog": str(_REPO_ROOT / "project" / "backlog.json"),
}
