"""Tests for project_manager.config — guards against data-path / identity drift."""

from __future__ import annotations

import json
from pathlib import Path

from project_manager import config


class TestDataPaths:
    """Ensure configured data paths resolve to files that actually exist."""

    def test_backlog_path_exists(self) -> None:
        # Regression guard: backlog file is project/backlog.json;
        # config.DATA_PATHS must keep pointing at real data.
        backlog_path = Path(config.DATA_PATHS["backlog"])
        assert backlog_path.is_file(), (
            f"config.DATA_PATHS['backlog'] points to {backlog_path}, "
            "which does not exist — did the backlog file get renamed?"
        )


class TestGitHubIdentity:
    """Ensure the GitHub identity is loaded from .github/config.json."""

    def test_config_json_exists(self) -> None:
        assert config._CONFIG_PATH.is_file(), (
            f"config loads identity from {config._CONFIG_PATH}, which does not exist."
        )

    def test_identity_matches_config_json(self) -> None:
        # Source of truth is .github/config.json; config.py is only a loader.
        data = json.loads(config._CONFIG_PATH.read_text(encoding="utf-8"))
        assert config.PROJECT == data["project"]
        assert config.REPO == data["repo"]
        assert config.OWNER == data["owner"]
        assert config.PROJECT_NUMBER == data["project_number"]
