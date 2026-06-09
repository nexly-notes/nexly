#!/usr/bin/env python3
"""Command-line wrapper for :class:`project_manager.ProjectManager`.

Parses arguments with ``argparse`` and delegates to ``ProjectManager.run``.
All business logic lives in ``project_manager.manager``.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from .manager import ProjectManager

_EPILOG = """\
examples:
  python -m project_manager.cli list
  python -m project_manager.cli list -s priority -w
  python -m project_manager.cli view "Research X"
  python -m project_manager.cli update "Research X" --status "In Progress"
  python -m project_manager.cli update 447 --goal "ship it" --points 3
  python -m project_manager.cli progress
  python -m project_manager.cli add-subissue --story "Research X" --title "New task"
  python -m project_manager.cli add-issue --title "Research X"
  python -m project_manager.cli summary -g priority
  python -m project_manager.cli resolve
  python -m project_manager.cli ready
  python -m project_manager.cli ready --top
  python -m project_manager.cli sync --dry-run
  python -m project_manager.cli sync --delete-all
  python -m project_manager.cli pull --dry-run
"""


def _add_list_filter_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--status", help="Filter by status (Backlog, In Progress, Done)")
    p.add_argument("--priority", help="Filter by priority (P0, P1, P2)")
    p.add_argument("--subissues", help="Show sub-issues of a parent (title or issue number)")


def _add_list_display_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--sort-by", "-s", help="Sort by field")
    p.add_argument("--reverse", "-r", action="store_true", help="Reverse sort order")
    p.add_argument("--wide", "-w", action="store_true", help="Show all columns")
    p.add_argument("--keys-only", "-k", action="store_true", help="Output only item keys")
    p.add_argument(
        "--keys-format", choices=["comma", "newline", "json"], default="comma",
        help="Format for -k output: comma (default), newline, json",
    )
    p.add_argument("--json", action="store_true", help="Output results as JSON")


def _add_list_parser(sub: Any) -> None:
    p = sub.add_parser("list", aliases=["ls"], help="List stories and tasks in a table")
    _add_list_filter_flags(p)
    _add_list_display_flags(p)


def _add_view_parser(sub: Any) -> None:
    p = sub.add_parser("view", help="View a single item by title or issue number")
    p.add_argument("key", help="Item title or issue number")
    p.add_argument("--raw", action="store_true", help="Show raw key-value pairs")
    p.add_argument("--template", help="Path to a custom template")
    p.add_argument("--tasks", action="store_true", help="Show only child sub-issues")
    p.add_argument(
        "--ready-tasks", action="store_true",
        help="Show child sub-issues still in Backlog",
    )
    p.add_argument("--ac", action="store_true", help="Show only acceptance criteria")
    p.add_argument("--json", action="store_true", help="Output results as JSON")


def _add_update_groom_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--goal", help="Set goal (free text)")
    p.add_argument("--notes", help="Set notes (free text)")
    p.add_argument("--size", help="Set size (free text, e.g. S/M/L)")
    p.add_argument("--points", type=int, help="Set story points (int)")
    p.add_argument("--labels", nargs="+", help="Set labels (replaces the list)")
    p.add_argument(
        "--ac", dest="acceptance_criteria", nargs="+",
        help="Set acceptance criteria (replaces the list)",
    )
    p.add_argument("--start-date", help="Set start date (YYYY-MM-DD)")
    p.add_argument("--end-date", help="Set end date (YYYY-MM-DD)")


def _add_update_parser(sub: Any) -> None:
    p = sub.add_parser("update", help="Update any item (story or sub-issue)")
    p.add_argument("key", help="Item title or issue number")
    p.add_argument("--status", help="Set status (Backlog, In Progress, Done)")
    p.add_argument("--priority", help="Set priority (P0, P1, P2)")
    p.add_argument("--title", help="Set title")
    p.add_argument("--description", help="Set description (free text)")
    _add_update_groom_flags(p)
    p.add_argument("--force", action="store_true", help="Bypass status transition guardrail")


def _add_summary_parser(sub: Any) -> None:
    p = sub.add_parser("summary", help="Show item summary grouped by a field")
    p.add_argument(
        "--group-by", "-g", default="status", help="Field to group by (default: status)"
    )


def _add_add_issue_parser(sub: Any) -> None:
    p = sub.add_parser("add-issue", help="Add a lean top-level issue (story)")
    p.add_argument("--title", required=True, help="Issue title (must be unique)")
    p.add_argument("--description", help="Issue description (free text)")


def _add_add_subissue_parser(sub: Any) -> None:
    p = sub.add_parser("add-subissue", help="Add a sub-issue under a parent issue")
    p.add_argument("--story", required=True, help="Parent issue (title or issue number)")
    p.add_argument("--title", required=True, help="Sub-issue title (must be unique)")
    p.add_argument("--description", help="Sub-issue description (free text)")


def _add_sync_override_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--repo", help="Override repo (e.g. owner/repo)")
    p.add_argument("--project", type=int, help="Override project number")
    p.add_argument("--owner", help="Override project owner (user or org)")


def _add_sync_parser(sub: Any) -> None:
    p = sub.add_parser("sync", help="Push backlog items to GitHub Issues + Projects")
    p.add_argument("--dry-run", action="store_true", help="Preview without modifying")
    p.add_argument(
        "--delete-all", action="store_true",
        help="Close all issues and remove them from the project",
    )
    _add_sync_override_flags(p)


def _add_pull_parser(sub: Any) -> None:
    p = sub.add_parser("pull", help="Mirror GitHub state back into backlog.json")
    p.add_argument("--dry-run", action="store_true", help="Print diff without writing")
    _add_sync_override_flags(p)


def _add_ready_parser(sub: Any) -> None:
    p = sub.add_parser(
        "ready", help="List stories already in the Ready status (ranked, read-only)"
    )
    p.add_argument("--story", help="Filter to a single story (title or issue number)")
    p.add_argument(
        "--top", action="store_true",
        help="Return only the top-ranked story (highest priority wins)",
    )
    p.add_argument("--json", action="store_true", help="Output results as JSON")


def _add_resolve_parser(sub: Any) -> None:
    p = sub.add_parser(
        "resolve", help="Promote unblocked Backlog stories to the Ready status"
    )
    p.add_argument("--story", help="Resolve a single story (title or issue number)")
    p.add_argument(
        "--top", action="store_true",
        help="Resolve only the top-ranked candidate (highest priority wins)",
    )


def _register_subparsers(sub: Any) -> None:
    _add_list_parser(sub)
    _add_view_parser(sub)
    _add_update_parser(sub)
    _add_summary_parser(sub)
    _add_add_issue_parser(sub)
    _add_add_subissue_parser(sub)
    sub.add_parser("progress", help="Show backlog completion stats")
    _add_sync_parser(sub)
    _add_pull_parser(sub)
    _add_ready_parser(sub)
    _add_resolve_parser(sub)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Manage a unified-item solo-dev backlog (stories with sub-issues).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EPILOG,
    )
    _register_subparsers(ap.add_subparsers(dest="command", required=True))
    return ap


def _args_to_kwargs(args: argparse.Namespace) -> tuple[str, dict]:
    kwargs = {k: v for k, v in vars(args).items() if not k.startswith("_")}
    command = kwargs.pop("command")
    return command, kwargs


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    command, kwargs = _args_to_kwargs(args)
    return ProjectManager().run(command, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
