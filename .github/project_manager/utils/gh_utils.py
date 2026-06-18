"""Shared utilities for GitHub CLI wrappers."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str], *, check: bool = True) -> str:
    """Run a command and return stdout."""
    p = subprocess.run(cmd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}\n\nSTDERR:\n{p.stderr}"
        )
    return p.stdout.strip()


def gh_json(cmd: list[str]) -> Any:
    """Run a command and parse JSON output."""
    out = run(cmd)
    if not out:
        return None
    return json.loads(out)


def load_config() -> dict[str, Any]:
    """Return project configuration."""
    from ..config import DATA_PATHS, OWNER, PROJECT_NUMBER, REPO

    return {
        "repo": REPO,
        "owner": OWNER,
        "project": PROJECT_NUMBER,
        "data_paths": DATA_PATHS,
    }
