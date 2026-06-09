"""The one CLI for the projects package: argparse tree + subcommand dispatch.

Run either way:

    python3 .github/scripts/projects/cli.py <command> …   # canonical (path-robust)
    python3 -m projects <command> …                       # from .github/scripts/

The package parent (``.github/scripts/``) is prepended to ``sys.path`` so the
script form resolves ``from projects import …`` regardless of cwd (matching
``.claude/scripts/codex_review.py``). Shared identity overrides
(``--repo``/``--project``/``--owner``) hang off every subcommand.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `from projects import …` resolve when run as a bare script from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from projects import config, conversion, state, validation  # noqa: E402


_EPILOG = """\
examples:
  python3 .github/scripts/projects/cli.py validate project/backlog.json
  python3 .github/scripts/projects/cli.py convert
  python3 .github/scripts/projects/cli.py convert --dry-run
  python3 .github/scripts/projects/cli.py list --status Backlog
  python3 .github/scripts/projects/cli.py order
  python3 .github/scripts/projects/cli.py view 42
  python3 .github/scripts/projects/cli.py status 42 Done
  python3 .github/scripts/projects/cli.py delete 42 --keep-issue
"""


def _shared_parent() -> argparse.ArgumentParser:
    """Parent parser carrying the GitHub identity overrides for every subcommand."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--repo", help="Override repo (e.g. owner/repo)")
    parent.add_argument("--project", type=int, help="Override project number")
    parent.add_argument("--owner", help="Override project owner (user or org)")
    return parent


def _add_convert_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser(
        "convert", aliases=["sync"], parents=[parent],
        help="Create/update GitHub issues from backlog.json and write issue numbers back",
    )
    p.add_argument("--dry-run", action="store_true", help="Run passes without writing numbers back")


def _add_validate_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser("validate", parents=[parent], help="Validate a groomed backlog JSON file")
    p.add_argument("path", help="Path to the backlog JSON file")


def _add_list_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser("list", parents=[parent], help="List project items (number, title, status, priority, size, points)")
    p.add_argument("--status", help="Filter by status (Backlog, In Progress, Done)")
    p.add_argument("--priority", help="Filter by priority (P0, P1, P2)")
    p.add_argument("--json", action="store_true", help="Output rows as JSON")


def _add_order_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser(
        "order", parents=[parent],
        help="Order issues by priority while respecting blocker dependencies",
    )
    p.add_argument("--json", action="store_true", help="Output the ordering as JSON")


def _add_view_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser("view", parents=[parent], help="View an issue + its project fields")
    p.add_argument("issue_number", metavar="issue_number", help="GitHub issue number")


def _add_status_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser("status", parents=[parent], help="Set an item's project Status")
    p.add_argument("issue_number", type=int, help="GitHub issue number")
    p.add_argument("value", help="Status value (Backlog, In Progress, Done)")


def _add_delete_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser("delete", parents=[parent], help="Remove an item from the project (and delete the issue)")
    p.add_argument("issue_number", type=int, help="GitHub issue number")
    p.add_argument(
        "--keep-issue", action="store_true",
        help="Only remove from the project; do not delete the underlying issue",
    )


def _add_delete_all_parser(sub, parent: argparse.ArgumentParser) -> None:
    p = sub.add_parser("delete-all", parents=[parent], help="Delete every project issue + clear backlog numbers")
    p.add_argument("--dry-run", action="store_true", help="List what would be deleted, without deleting")


def _register_subparsers(sub, parent: argparse.ArgumentParser) -> None:
    _add_convert_parser(sub, parent)
    _add_validate_parser(sub, parent)
    _add_list_parser(sub, parent)
    _add_order_parser(sub, parent)
    _add_view_parser(sub, parent)
    _add_status_parser(sub, parent)
    _add_delete_parser(sub, parent)
    _add_delete_all_parser(sub, parent)


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="A GitHub Projects (v2) CLI for the groomed backlog lifecycle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_EPILOG,
    )
    parent = _shared_parent()
    _register_subparsers(ap.add_subparsers(dest="command", required=True), parent)
    return ap


def _dispatch(args: argparse.Namespace) -> int:
    """Route a parsed namespace to the owning module function."""
    identity = config.resolve_identity(repo=args.repo, project=args.project, owner=args.owner)
    backlog_path = Path(config.DATA_PATHS["backlog"])
    command = args.command
    if command in ("convert", "sync"):
        return conversion.convert(identity, backlog_path, dry_run=args.dry_run)
    if command == "validate":
        return validation.run(args.path)
    if command == "list":
        return state.list_items(
            identity, status=args.status, priority=args.priority, json=args.json,
        )
    if command == "order":
        return state.order(identity, json=args.json)
    if command == "view":
        return state.view(identity, issue_number=args.issue_number)
    if command == "status":
        return state.status(identity, issue_number=args.issue_number, value=args.value)
    if command == "delete":
        return state.delete(identity, issue_number=args.issue_number, keep_issue=args.keep_issue)
    if command == "delete-all":
        return state.delete_all(identity, backlog_path, dry_run=args.dry_run)
    raise ValueError(f"Unknown command: {command}")


def main(argv: list[str] | None = None) -> int:
    return _dispatch(_build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
