"""Tests for projects.cli — the single argparse tree + subcommand dispatch."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from projects import cli, config


# ── Parser ─────────────────────────────────────────────────────────────────


class TestParser:
    def test_has_core_commands(self):
        help_text = cli._build_parser().format_help()
        for cmd in ["convert", "sync", "validate", "list", "order", "view",
                    "status", "delete", "delete-all"]:
            assert cmd in help_text

    def test_removed_commands_rejected(self):
        # assign / groom collapsed into convert; add / edit / update are long gone.
        for removed in (["assign", "1", "S"], ["groom"], ["add", "X"],
                        ["edit", "1"], ["update", "NEXLY-001"]):
            with pytest.raises(SystemExit):
                cli._build_parser().parse_args(removed)

    def test_convert_dry_run(self):
        args = cli._build_parser().parse_args(["convert", "--dry-run"])
        assert args.command == "convert" and args.dry_run is True

    def test_sync_alias(self):
        assert cli._build_parser().parse_args(["sync"]).command == "sync"

    def test_validate_path(self):
        args = cli._build_parser().parse_args(["validate", "project/backlog.json"])
        assert args.command == "validate" and args.path == "project/backlog.json"

    def test_validate_requires_path(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["validate"])

    def test_order_json(self):
        args = cli._build_parser().parse_args(["order", "--json"])
        assert args.command == "order" and args.json is True

    def test_view_accepts_issue_number(self):
        assert cli._build_parser().parse_args(["view", "42"]).issue_number == "42"

    def test_list_filters(self):
        args = cli._build_parser().parse_args(
            ["list", "--status", "Backlog", "--priority", "P0", "--json"]
        )
        assert args.status == "Backlog"
        assert args.priority == "P0"
        assert args.json is True

    def test_list_has_no_sprint_filter(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args(["list", "--sprint", "Sprint 1"])

    def test_status_positionals(self):
        args = cli._build_parser().parse_args(["status", "42", "Done"])
        assert args.issue_number == 42 and args.value == "Done"

    def test_delete_keep_issue(self):
        args = cli._build_parser().parse_args(["delete", "42", "--keep-issue"])
        assert args.issue_number == 42 and args.keep_issue is True

    def test_delete_all_dry_run(self):
        args = cli._build_parser().parse_args(["delete-all", "--dry-run"])
        assert args.command == "delete-all" and args.dry_run is True

    def test_shared_overrides_on_any_subcommand(self):
        args = cli._build_parser().parse_args(
            ["list", "--repo", "me/r", "--project", "7", "--owner", "me"]
        )
        assert args.repo == "me/r" and args.project == 7 and args.owner == "me"


# ── main() dispatch ────────────────────────────────────────────────────────


class TestMainDispatch:
    @patch.object(cli.conversion, "convert", return_value=0)
    def test_convert(self, mock_convert):
        assert cli.main(["convert", "--dry-run"]) == 0
        ident, path = mock_convert.call_args[0]
        assert mock_convert.call_args[1] == {"dry_run": True}
        assert ident.repo == config.REPO

    @patch.object(cli.conversion, "convert", return_value=0)
    def test_sync_alias_dispatches_convert(self, mock_convert):
        cli.main(["sync"])
        assert mock_convert.call_args[1] == {"dry_run": False}

    @patch.object(cli.validation, "run", return_value=0)
    def test_validate(self, mock_run):
        cli.main(["validate", "project/backlog.json"])
        mock_run.assert_called_once_with("project/backlog.json")

    @patch.object(cli.state, "list_items", return_value=0)
    def test_list(self, mock_list):
        cli.main(["list", "--status", "Done", "--json"])
        assert mock_list.call_args[1] == {
            "status": "Done", "priority": None, "json": True,
        }

    @patch.object(cli.state, "order", return_value=0)
    def test_order(self, mock_order):
        cli.main(["order", "--json"])
        assert mock_order.call_args[1] == {"json": True}

    @patch.object(cli.state, "view", return_value=0)
    def test_view(self, mock_view):
        cli.main(["view", "42"])
        kwargs = mock_view.call_args[1]
        assert kwargs["issue_number"] == "42"
        assert "backlog_path" not in kwargs

    @patch.object(cli.state, "status", return_value=0)
    def test_status(self, mock_status):
        cli.main(["status", "42", "In Progress"])
        assert mock_status.call_args[1] == {"issue_number": 42, "value": "In Progress"}

    @patch.object(cli.state, "delete", return_value=0)
    def test_delete(self, mock_delete):
        cli.main(["delete", "42", "--keep-issue"])
        assert mock_delete.call_args[1] == {"issue_number": 42, "keep_issue": True}

    @patch.object(cli.state, "delete_all", return_value=0)
    def test_delete_all(self, mock_delete_all):
        cli.main(["delete-all", "--dry-run"])
        assert mock_delete_all.call_args[1] == {"dry_run": True}

    @patch.object(cli.state, "list_items", return_value=0)
    def test_identity_overrides_reach_functions(self, mock_list):
        cli.main(["list", "--repo", "o/r", "--project", "5", "--owner", "me"])
        ident = mock_list.call_args[0][0]
        assert (ident.repo, ident.project, ident.owner) == ("o/r", 5, "me")
