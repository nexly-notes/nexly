"""Tests for project_manager.cli — argparse wrapper, unified-item schema."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from project_manager import cli


class _FakePM:
    def __init__(self, *_args, **_kwargs) -> None:
        self.calls: list[tuple[str, dict]] = []

    def run(self, command: str, **kwargs) -> int:
        self.calls.append((command, kwargs))
        return 0


@pytest.fixture
def fake_pm(monkeypatch):
    instance = _FakePM()
    monkeypatch.setattr(cli, "ProjectManager", lambda *a, **k: instance)
    return instance


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class TestParser:
    def test_has_core_commands(self):
        help_text = cli._build_parser().format_help()
        for cmd in [
            "list", "view", "update", "summary", "add-issue", "add-subissue",
            "progress", "sync", "pull", "ready", "resolve",
        ]:
            assert cmd in help_text

    def test_no_watch_command(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["watch"])

    def test_update_done_flag_removed(self):
        # Tasks are full items now — `done` is gone.
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["update", "T", "--done", "true"])

    def test_list_type_flag_removed(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["list", "--type", "Spike"])

    def test_add_story_type_flag_removed(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(
                ["add-issue", "--type", "Spike", "--title", "X"]
            )

    def test_add_story_priority_flag_removed(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(
                ["add-issue", "--title", "X", "--priority", "P0"]
            )

    def test_add_story_requires_title(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["add-issue"])

    def test_add_story_minimal(self):
        args = cli._build_parser().parse_args(["add-issue", "--title", "X"])
        assert args.title == "X"

    def test_add_story_description(self):
        args = cli._build_parser().parse_args(
            ["add-issue", "--title", "X", "--description", "why"]
        )
        assert args.description == "why"

    def test_add_task_uses_story_flag(self):
        args = cli._build_parser().parse_args(
            ["add-subissue", "--story", "42", "--title", "Y"]
        )
        assert args.story == "42"
        assert args.title == "Y"

    def test_add_task_parent_story_id_removed(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(
                ["add-subissue", "--parent-story-id", "X", "--title", "Y"]
            )

    def test_add_task_description(self):
        args = cli._build_parser().parse_args(
            ["add-subissue", "--story", "P", "--title", "Y", "--description", "why"]
        )
        assert args.description == "why"

    def test_ls_alias(self):
        assert cli._build_parser().parse_args(["ls"]).command == "ls"

    def test_list_flags(self):
        args = cli._build_parser().parse_args(
            ["list", "--status", "Done", "--sort-by", "priority", "--wide"]
        )
        assert args.status == "Done"
        assert args.sort_by == "priority"
        assert args.wide is True

    def test_list_subissues_filter(self):
        args = cli._build_parser().parse_args(["list", "--subissues", "Research X"])
        assert args.subissues == "Research X"

    def test_list_story_flag_removed(self):
        # The list filter is `--subissues` now, not `--story`.
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["list", "--story", "Research X"])

    def test_old_command_names_removed(self):
        for old in ("add-story", "add-task"):
            with pytest.raises(SystemExit):
                cli._build_parser().parse_args([old, "--title", "X"])

    def test_view_positional_key(self):
        args = cli._build_parser().parse_args(["view", "Research X", "--raw"])
        assert args.key == "Research X"
        assert args.raw is True

    def test_update_status_and_priority(self):
        args = cli._build_parser().parse_args(
            ["update", "S", "--status", "In Progress", "--priority", "P0"]
        )
        assert args.status == "In Progress"
        assert args.priority == "P0"

    def test_update_groom_fields(self):
        args = cli._build_parser().parse_args([
            "update", "S", "--goal", "g", "--notes", "n", "--size", "L",
            "--points", "5", "--start-date", "2026-02-01", "--end-date", "2026-02-05",
        ])
        assert args.goal == "g"
        assert args.notes == "n"
        assert args.size == "L"
        assert args.points == 5
        assert args.start_date == "2026-02-01"
        assert args.end_date == "2026-02-05"

    def test_update_list_fields(self):
        args = cli._build_parser().parse_args([
            "update", "S", "--labels", "infra", "p0", "--ac", "crit one", "crit two",
        ])
        assert args.labels == ["infra", "p0"]
        assert args.acceptance_criteria == ["crit one", "crit two"]

    def test_ready_flags(self):
        args = cli._build_parser().parse_args(["ready", "--json", "--top", "--story", "S"])
        assert args.json is True and args.top is True and args.story == "S"

    def test_ready_promote_flag_removed(self):
        # Promotion moved to the `resolve` command.
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["ready", "--promote"])

    def test_resolve_minimal(self):
        args = cli._build_parser().parse_args(["resolve"])
        assert args.command == "resolve"

    def test_resolve_flags(self):
        args = cli._build_parser().parse_args(["resolve", "--story", "S", "--top"])
        assert args.story == "S" and args.top is True

    def test_sync_accepts_overrides(self):
        args = cli._build_parser().parse_args(
            ["sync", "--repo", "me/r", "--project", "7", "--owner", "me"]
        )
        assert args.repo == "me/r" and args.project == 7 and args.owner == "me"

    def test_pull_parser(self):
        args = cli._build_parser().parse_args(
            ["pull", "--dry-run", "--repo", "me/r", "--project", "7", "--owner", "me"]
        )
        assert args.dry_run is True
        assert args.repo == "me/r" and args.project == 7 and args.owner == "me"


# ---------------------------------------------------------------------------
# _args_to_kwargs
# ---------------------------------------------------------------------------


class TestArgsToKwargs:
    def test_strips_command(self):
        args = cli._build_parser().parse_args(["list", "--wide"])
        command, kwargs = cli._args_to_kwargs(args)
        assert command == "list"
        assert "command" not in kwargs
        assert kwargs["wide"] is True

    def test_hyphens_to_underscores(self):
        args = cli._build_parser().parse_args(
            ["list", "--sort-by", "priority", "--keys-only"]
        )
        _, kwargs = cli._args_to_kwargs(args)
        assert kwargs["sort_by"] == "priority"
        assert kwargs["keys_only"] is True

    def test_add_task_kwargs(self):
        args = cli._build_parser().parse_args(
            ["add-subissue", "--story", "P", "--title", "Hi"]
        )
        command, kwargs = cli._args_to_kwargs(args)
        assert command == "add-subissue"
        assert kwargs["story"] == "P"
        assert kwargs["title"] == "Hi"


# ---------------------------------------------------------------------------
# main() dispatch
# ---------------------------------------------------------------------------


class TestMain:
    def test_dispatches_progress(self, fake_pm):
        assert cli.main(["progress"]) == 0
        assert fake_pm.calls == [("progress", {})]

    def test_dispatches_list_kwargs(self, fake_pm):
        cli.main(["list", "--status", "Done", "--wide"])
        command, kwargs = fake_pm.calls[0]
        assert command == "list"
        assert kwargs["status"] == "Done" and kwargs["wide"] is True

    def test_dispatches_list_subissues(self, fake_pm):
        cli.main(["list", "--subissues", "42"])
        command, kwargs = fake_pm.calls[0]
        assert command == "list"
        assert kwargs["subissues"] == "42"

    def test_dispatches_view(self, fake_pm):
        cli.main(["view", "Research X", "--raw"])
        command, kwargs = fake_pm.calls[0]
        assert command == "view"
        assert kwargs["key"] == "Research X" and kwargs["raw"] is True

    def test_dispatches_update_groom(self, fake_pm):
        cli.main(["update", "S", "--goal", "g", "--points", "3"])
        command, kwargs = fake_pm.calls[0]
        assert command == "update"
        assert kwargs["goal"] == "g" and kwargs["points"] == 3

    def test_dispatches_add_story(self, fake_pm):
        cli.main(["add-issue", "--title", "Crash"])
        command, kwargs = fake_pm.calls[0]
        assert command == "add-issue"
        assert kwargs["title"] == "Crash"
        assert "type" not in kwargs

    def test_dispatches_add_task(self, fake_pm):
        cli.main(["add-subissue", "--story", "42", "--title", "T"])
        command, kwargs = fake_pm.calls[0]
        assert command == "add-subissue"
        assert kwargs["story"] == "42"

    def test_dispatches_resolve(self, fake_pm):
        cli.main(["resolve", "--top"])
        command, kwargs = fake_pm.calls[0]
        assert command == "resolve" and kwargs["top"] is True

    def test_sync_dry_run(self, fake_pm):
        cli.main(["sync", "--dry-run"])
        command, kwargs = fake_pm.calls[0]
        assert command == "sync" and kwargs["dry_run"] is True

    def test_pull_dispatch(self, fake_pm):
        cli.main(["pull", "--dry-run"])
        command, kwargs = fake_pm.calls[0]
        assert command == "pull" and kwargs["dry_run"] is True

    def test_pull_overrides(self, fake_pm):
        cli.main(["pull", "--repo", "o/r", "--project", "5", "--owner", "me"])
        _, kwargs = fake_pm.calls[0]
        assert kwargs["repo"] == "o/r" and kwargs["project"] == 5 and kwargs["owner"] == "me"
