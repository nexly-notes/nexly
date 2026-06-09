"""Tests for projects.config — guards against data-path / identity drift."""
from __future__ import annotations

from pathlib import Path

from projects import config


class TestDataPaths:
    def test_backlog_path_exists(self) -> None:
        # Regression guard: backlog file is project/backlog.json;
        # config.DATA_PATHS must keep pointing at real data.
        backlog_path = Path(config.DATA_PATHS["backlog"])
        assert backlog_path.is_file(), (
            f"config.DATA_PATHS['backlog'] points to {backlog_path}, "
            "which does not exist — did the backlog file get renamed?"
        )

    def test_repo_root_is_repo(self) -> None:
        assert (config.REPO_ROOT / ".github" / "config.json").is_file()


class TestGitHubIdentity:
    def test_identity_loaded_from_config_json(self) -> None:
        assert config.REPO
        assert config.OWNER
        assert config.PROJECT_NUMBER

    def test_resolve_identity_defaults(self) -> None:
        ident = config.resolve_identity()
        assert ident.repo == config.REPO
        assert ident.project == config.PROJECT_NUMBER
        assert ident.owner == config.OWNER

    def test_resolve_identity_overrides(self) -> None:
        ident = config.resolve_identity(repo="o/r", project=7, owner="me")
        assert (ident.repo, ident.project, ident.owner) == ("o/r", 7, "me")
