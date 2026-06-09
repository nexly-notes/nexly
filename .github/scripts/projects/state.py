"""Per-item project state ops: list / order / view / status / delete.

These operate directly against issue numbers once ``convert`` has linked the
backlog to the project. ``status`` sets a single project field (``Status``);
``delete`` removes one item (optionally keeping the issue); ``delete-all``
tears down the whole project and clears every ``issue_number`` from the backlog
so the next ``convert`` re-creates fresh.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from projects import backlog, board, gh
from projects.config import Identity


# ── list ───────────────────────────────────────────────────────────────────


def _project_rows(identity: Identity) -> list[dict]:
    rows: list[dict] = []
    for it in board.get_project_items(identity.project, identity.owner):
        content = it.get("content") or {}
        number = content.get("number")
        if not number:
            continue
        rows.append({
            "number": number,
            "title": content.get("title", ""),
            "status": it.get("status", ""),
            "priority": it.get("priority", ""),
            "size": it.get("size", ""),
            "points": it.get("points", ""),
        })
    return rows


def _print_item_rows(rows: list[dict]) -> None:
    """Print a simple table of project items for the ``list`` command."""
    if not rows:
        print("No items found.")
        return
    header = f"{'#':<6} {'STATUS':<12} {'PRI':<4} {'SIZE':<5} {'PTS':<4} TITLE"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['number']:<6} {r.get('status', ''):<12} {r.get('priority', ''):<4} "
            f"{str(r.get('size', '')):<5} {str(r.get('points', '')):<4} {r.get('title', '')}"
        )
    print(f"\n{len(rows)} item(s)")


def list_items(
    identity: Identity,
    *,
    status: str | None = None,
    priority: str | None = None,
    json: bool = False,
) -> int:
    """List project items, optionally filtered by status / priority."""
    rows = _project_rows(identity)
    if status:
        rows = [r for r in rows if r["status"] == status]
    if priority:
        rows = [r for r in rows if r["priority"] == priority]
    if json:
        print(_to_json(rows))
    else:
        _print_item_rows(rows)
    return 0


def _to_json(obj: object) -> str:
    """Serialize to indented JSON (kept separate so the ``json`` flag can't shadow)."""
    import json as _json

    return _json.dumps(obj, indent=2)


# ── order ──────────────────────────────────────────────────────────────────


_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


def _blocker_map(repo: str, numbers: list[int]) -> dict[int, list[int]]:
    """Map each board issue to its in-board blockers via the issue graph.

    Dependencies aren't a project field — they live in the GitHub issue graph,
    so we read them from ``gh._fetch_node_ids_and_edges`` (each edge is a
    ``(blocked_num, blocker_num)`` pair) and keep only edges whose *both*
    endpoints are on the board. Empty input short-circuits the network call.
    """
    if not numbers:
        return {}
    on_board = set(numbers)
    _, edges, _ = gh._fetch_node_ids_and_edges(repo, on_board)
    blockers: dict[int, list[int]] = {n: [] for n in numbers}
    for blocked_num, blocker_num in sorted(edges):
        if blocked_num in on_board and blocker_num in on_board:
            blockers[blocked_num].append(blocker_num)
    return blockers


def _order_rows(
    rows: list[dict], blockers: dict[int, list[int]]
) -> tuple[list[dict], list[dict]]:
    """Priority-respecting topological sort (Kahn); a blocker beats priority.

    Repeatedly emits the highest-priority ready item (in-degree 0), tie-broken
    by ascending issue number, then releases its dependents. Because a blocker
    is always emitted before what it blocks, ``B`` precedes ``A`` whenever
    ``A`` is blocked by ``B`` — even when ``A`` outranks ``B``. Any items still
    unemitted once the ready set drains form a dependency cycle and come back as
    ``unresolved``. Returns ``(ordered, unresolved)``.
    """
    by_number = {r["number"]: r for r in rows}
    in_degree = {n: 0 for n in by_number}
    dependents: dict[int, list[int]] = {n: [] for n in by_number}
    for blocked_num, blocker_nums in blockers.items():
        for blocker_num in blocker_nums:
            if blocked_num in by_number and blocker_num in by_number:
                in_degree[blocked_num] += 1
                dependents[blocker_num].append(blocked_num)
    ready = [n for n, deg in in_degree.items() if deg == 0]
    ordered: list[dict] = []
    emitted: set[int] = set()
    while ready:
        ready.sort(key=lambda n: (_PRIORITY_RANK.get(by_number[n].get("priority", ""), 99), n))
        current = ready.pop(0)
        emitted.add(current)
        ordered.append(by_number[current])
        for dependent in dependents[current]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
    unresolved = [by_number[n] for n in sorted(by_number) if n not in emitted]
    return ordered, unresolved


def _format_blocked_by(blocker_nums: list[int]) -> str:
    """Render a blocker list as ``#a #b`` (or ``-`` when there are none)."""
    if not blocker_nums:
        return "-"
    return " ".join(f"#{n}" for n in blocker_nums)


def _print_order_rows(
    ordered: list[dict], blockers: dict[int, list[int]], unresolved: list[dict]
) -> None:
    """Print the ordered worklist as a table; cycle items go to stderr."""
    if not ordered and not unresolved:
        print("No items found.")
        return
    header = f"{'SEQ':<4} {'#':<6} {'PRI':<4} {'STATUS':<12} {'BLOCKED BY':<16} TITLE"
    print(header)
    print("-" * len(header))
    for seq, r in enumerate(ordered, start=1):
        blocked_by = _format_blocked_by(blockers.get(r["number"], []))
        print(
            f"{seq:<4} {r['number']:<6} {r.get('priority', ''):<4} "
            f"{r.get('status', ''):<12} {blocked_by:<16} {r.get('title', '')}"
        )
    print(f"\n{len(ordered)} item(s) ordered")
    if unresolved:
        nums = ", ".join(f"#{r['number']}" for r in unresolved)
        print(
            f"\n⚠ {len(unresolved)} item(s) in a dependency cycle: {nums}",
            file=sys.stderr,
        )


def order(identity: Identity, *, json: bool = False) -> int:
    """Order project items by priority while honoring blocker dependencies.

    Reads the live board, pulls blocker edges from the issue graph, and runs a
    priority-respecting topological sort: a blocker always precedes what it
    blocks, otherwise higher priority comes first. Returns ``1`` when a
    dependency cycle leaves items unordered, else ``0``.
    """
    rows = _project_rows(identity)
    blockers = _blocker_map(identity.repo, [r["number"] for r in rows])
    ordered, unresolved = _order_rows(rows, blockers)
    if json:
        payload = {
            "order": [
                {**r, "seq": seq, "blocked_by": blockers.get(r["number"], [])}
                for seq, r in enumerate(ordered, start=1)
            ],
            "unresolved": unresolved,
        }
        print(_to_json(payload))
    else:
        _print_order_rows(ordered, blockers, unresolved)
    return 1 if unresolved else 0


# ── view ───────────────────────────────────────────────────────────────────


def _resolve_issue_number(issue_number: str) -> int | None:
    """Resolve a ``view`` argument (a bare GitHub issue number) to an int.

    Returns None when the token is not an integer. Identity is the issue number
    now, so there is no id-to-number mapping step.
    """
    try:
        return int(str(issue_number).strip())
    except ValueError:
        return None


def view(identity: Identity, *, issue_number: str) -> int:
    """View an issue (by GitHub issue number) + its project fields."""
    number = _resolve_issue_number(issue_number)
    if number is None:
        print(f"Could not resolve {issue_number!r} to an issue number", file=sys.stderr)
        return 1
    data = gh.gh_issue_view(identity.repo, number)
    if not data:
        print(f"Issue #{number} not found", file=sys.stderr)
        return 1
    fields = _project_field_values(identity, number)
    print(f"#{number}: {data.get('title', '')}")
    print(f"  Status:   {fields.get('Status', '-')}")
    print(f"  Priority: {fields.get('Priority', '-')}")
    print(f"  Size:     {fields.get('Size', '-')}")
    print(f"  Points:   {fields.get('Points', '-')}")
    body = (data.get("body") or "").strip()
    if body:
        print(f"\n{body}")
    return 0


def _project_field_values(identity: Identity, issue_number: int) -> dict:
    for it in board.get_project_items(identity.project, identity.owner):
        if (it.get("content") or {}).get("number") == issue_number:
            return board.extract_item_field_values(it)
    return {}


# ── status (single field write) ────────────────────────────────────────────


def status(identity: Identity, *, issue_number: int, value: str) -> int:
    """Set an item's project ``Status``."""
    project_id = board.get_project_id(identity.project, identity.owner)
    field_map = board.build_field_map(board.get_project_fields(identity.project, identity.owner))
    item_id = board.find_item_id(board.get_project_items(identity.project, identity.owner), issue_number)
    if not item_id:
        print(f"  ⚠ #{issue_number} not found in project — run `convert` first", file=sys.stderr)
        return 0
    board.set_field(project_id, item_id, field_map, "Status", value)
    print(f"Set #{issue_number} Status -> {value}")
    return 0


# ── delete (single item) ───────────────────────────────────────────────────


def _remove_from_project(identity: Identity, item_id: str) -> None:
    gh.run(
        [
            "gh", "project", "item-delete", str(identity.project),
            "--owner", identity.owner, "--id", item_id,
        ],
        check=False,
    )


def delete(identity: Identity, *, issue_number: int, keep_issue: bool = False) -> int:
    """Remove an item from the project and (unless ``keep_issue``) delete the issue."""
    items = board.get_project_items(identity.project, identity.owner)
    item_id = board.find_item_id(items, issue_number)
    if item_id:
        _remove_from_project(identity, item_id)
        print(f"  Removed #{issue_number} from project")
    else:
        print(f"  #{issue_number} not found in project")
    if keep_issue:
        print(f"Kept issue #{issue_number}")
        return 0
    gh.delete_issue(identity.repo, issue_number)
    print(f"Deleted issue #{issue_number}")
    return 0


# ── delete-all (teardown) ──────────────────────────────────────────────────


def _project_issues(identity: Identity) -> list[dict]:
    """Return ``[{title, number}]`` for every issue attached to the project."""
    result: list[dict] = []
    for it in board.get_project_items(identity.project, identity.owner):
        content = it.get("content") or {}
        number = content.get("number")
        if number:
            result.append({"title": content.get("title", ""), "number": number})
    return result


def _print_delete_dry_run(issues: list[dict]) -> None:
    for issue in issues:
        print(f"  [dry-run] Would delete #{issue['number']}: {issue['title']}")


def _remove_item_mutations(project_id: str, item_ids: list[str]) -> list[str]:
    return [
        f"m{i}: deleteProjectV2Item(input: {{"
        f"projectId: {json.dumps(project_id)}, itemId: {json.dumps(iid)}"
        f"}}) {{ deletedItemId }}"
        for i, iid in enumerate(item_ids)
    ]


def _remove_issues_from_project(identity: Identity, issues: list[dict]) -> None:
    print("\nRemoving from project (batched)...")
    project_id = board.get_project_id(identity.project, identity.owner)
    items = board.get_project_items(identity.project, identity.owner)
    item_ids = [board.find_item_id(items, iss["number"]) for iss in issues]
    item_ids = [iid for iid in item_ids if iid]
    if not item_ids:
        return
    for iss in issues:
        print(f"  ✗ #{iss['number']}")
    gh.execute_batched_mutations(_remove_item_mutations(project_id, item_ids))


def _delete_issues_batched(repo: str, issues: list[dict]) -> None:
    nums = {iss["number"] for iss in issues if iss.get("number")}
    node_ids = gh._fetch_node_ids(repo, nums)
    print(f"\nDeleting {len(issues)} issues permanently (batched)...")
    for iss in issues:
        print(f"  ✗ #{iss['number']}: {iss['title']}")
    gh.execute_batched_mutations(gh.delete_issue_mutations(node_ids))


def _perform_delete(
    identity: Identity, backlog_path: Path, issues: list[dict], backlog_data: dict
) -> None:
    _remove_issues_from_project(identity, issues)
    _delete_issues_batched(identity.repo, issues)
    backlog.clear_issue_numbers(backlog_data, backlog_path)


def delete_all(identity: Identity, backlog_path: Path, *, dry_run: bool = False) -> int:
    """Delete every issue in the project and clear backlog ``issue_number``s."""
    _, _, backlog_data = backlog.load_flat_data(backlog_path)
    print(f"Fetching issues currently in project {identity.project}...")
    issues = _project_issues(identity)
    if not issues:
        print("No issues found in the project.")
        return 0
    print(f"Found {len(issues)} project issue(s) to delete.")
    if dry_run:
        _print_delete_dry_run(issues)
        return 0
    _perform_delete(identity, backlog_path, issues, backlog_data)
    return 0
