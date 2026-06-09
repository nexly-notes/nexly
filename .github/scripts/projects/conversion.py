"""The ``convert`` workflow: push the groomed backlog to GitHub issues + board.

Reads the groomed backlog (``stories``), creates/updates one GitHub issue per
story, refreshes each issue body (``description`` → Goal → Tasks → Acceptance
Criteria → Notes), applies labels, mirrors ``Status`` / ``Priority`` / ``Size``
/ ``Points`` to the project, sets ``blocked_by`` edges, and writes each story's
``issue_number`` back into the JSON. This is the single GitHub push for the
backlog lifecycle — no per-item state ops live here (those are in
:mod:`projects.state`).
"""
from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from projects import backlog, board, gh
from projects.config import Identity

MAX_WORKERS = 8

# `addProjectV2ItemById` is accepted before `gh project item-list` reflects the
# new items (eventual consistency), so the field pass polls briefly for them.
_ITEM_POLL_ATTEMPTS = 6
_ITEM_POLL_DELAY = 2.0

# The convert field pass syncs the same fields board.CONVERT_FIELDS ensures;
# each project field name maps to the lowercased story key.
_FIELD_SPECS: list[tuple[str, str]] = [(name, name.lower()) for name, _, _ in board.CONVERT_FIELDS]


# ── Issue creation / resolution ────────────────────────────────────────────


_create_lock = threading.Lock()
_created_titles: set[str] = set()


def _claim_title(full_title: str) -> None:
    with _create_lock:
        if full_title in _created_titles:
            raise RuntimeError(f"Duplicate title detected, skipping: {full_title}")
        _created_titles.add(full_title)


def _issue_labels(story: dict[str, Any]) -> list[str]:
    """Return the issue's labels straight from the story's ``labels`` field.

    Blank entries are dropped so ``gh label create`` never sees an empty
    string; author casing is preserved. The groomed backlog carries the
    labels, so this is applied to every story at create time.
    """
    labels = story.get("labels") or []
    return [str(lab) for lab in labels if str(lab).strip()]


def _build_create_issue_cmd(
    repo: str, title: str, body: str, labels: list[str], assignees: list[str]
) -> list[str]:
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    for lab in labels:
        cmd += ["--label", lab]
    for a in assignees:
        cmd += ["--assignee", a]
    return cmd


def _create_issue(story: dict[str, Any], repo: str) -> int:
    """Create a single issue from a story. Returns issue number. Thread-safe."""
    title = backlog._item_title(story)
    _claim_title(title)
    labels = _issue_labels(story)
    for lab in labels:
        gh.ensure_label(lab, repo)
    cmd = _build_create_issue_cmd(
        repo, title, backlog.build_issue_body(story), labels, story.get("assignees") or []
    )
    url = gh.run(cmd).strip()
    if not url:
        raise RuntimeError(f"gh issue create returned no URL for: {title}")
    number = int(url.rstrip("/").split("/")[-1])
    story["issue_number"] = number
    return number


def ensure_issue(
    story: dict[str, Any], repo: str, existing_issues: dict[str, int] | None = None
) -> int:
    """Ensure an issue exists. Returns issue number."""
    if story.get("issue_number"):
        return story["issue_number"]
    title = backlog._item_title(story)
    if existing_issues and title in existing_issues:
        num = existing_issues[title]
        print(f"  ↳ Found existing issue: #{num}")
        story["issue_number"] = num
        return num
    existing = gh.find_existing_issue(repo, title)
    if existing:
        print(f"  ↳ Found existing issue: #{existing}")
        story["issue_number"] = existing
        return existing
    return _create_issue(story, repo)


def _resolve_one(
    s: dict[str, Any], existing_issues: dict[str, int], live: set[int]
) -> bool:
    """True if linked to a live issue; False if creation needed."""
    num = s.get("issue_number")
    if num and num in live:
        print(f"  ↳ Already has issue: #{num}")
        return True
    if num:
        print(f"  ↳ Stale #{num}; re-linking by title or re-creating")
        s.pop("issue_number", None)
    title = backlog._item_title(s)
    if title in existing_issues:
        s["issue_number"] = existing_issues[title]
        print(f"  ↳ Matched existing #{s['issue_number']}")
        return True
    return False


def resolve_existing_issues(
    stories: list[dict[str, Any]], existing_issues: dict[str, int]
) -> list[dict[str, Any]]:
    """Return stories that still need a new issue created."""
    live = set(existing_issues.values())
    return [s for s in stories if not _resolve_one(s, existing_issues, live)]


def _ensure_titles_present(items: list[dict], label: str) -> None:
    for s in items:
        if "title" not in s:
            raise ValueError(f"Item missing 'title': {s}")


def _pre_create_labels(items: list[dict], repo: str) -> None:
    """Ensure all labels exist before fanning out parallel issue creates."""
    unique: set[str] = set()
    for s in items:
        unique.update(_issue_labels(s))
    for lab in sorted(unique):
        gh.ensure_label(lab, repo)


def _create_missing_in_parallel(items: list[dict], repo: str, label: str) -> None:
    print(f"\nPass 1b: Creating {len(items)} new {label} (parallel)...")
    _pre_create_labels(items, repo)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_create_issue, s, repo): s for s in items}
        for fut in as_completed(futures):
            s = futures[fut]
            num = fut.result()
            print(f"  + {s['title']} -> #{num}")


def _resolve_or_create(
    items: list[dict], existing_issues: dict[str, int], repo: str, label: str
) -> bool:
    print(f"\nPass 1a: Resolving existing {label}...")
    _ensure_titles_present(items, label)
    needs_creation = resolve_existing_issues(items, existing_issues)
    if needs_creation:
        _create_missing_in_parallel(needs_creation, repo, label)
        return True
    print(f"  All {label} already have issues.")
    return False


# ── Add to project ─────────────────────────────────────────────────────────


def _add_to_project_mutations(
    project_id: str, node_ids: dict[int, str], items: list[dict]
) -> list[str]:
    mutations: list[str] = []
    idx = 0
    for s in items:
        cid = node_ids.get(s.get("issue_number"))
        if not cid:
            continue
        mutations.append(
            f"m{idx}: addProjectV2ItemById(input: {{"
            f"projectId: {json.dumps(project_id)}, contentId: {json.dumps(cid)}"
            f"}}) {{ item {{ id }} }}"
        )
        idx += 1
    return mutations


def _add_all_to_project_batched(
    all_items: list[dict], project_id: str, repo: str
) -> tuple[dict[int, str], set[tuple[int, int]], dict[int, int]]:
    """Batched addProjectV2ItemById; also returns blocker edges + parents."""
    print("\nAdding issues to project (batched)...")
    nums = {s["issue_number"] for s in all_items if s.get("issue_number")}
    node_ids, existing_edges, existing_parents = gh._fetch_node_ids_and_edges(repo, nums)
    mutations = _add_to_project_mutations(project_id, node_ids, all_items)
    gh.execute_batched_mutations(mutations)
    print(f"  ✓ {len(mutations)} items added/verified")
    return node_ids, existing_edges, existing_parents


# ── Field pass (Status + Priority) ─────────────────────────────────────────


def _field_specs_for_item(item: dict[str, Any]) -> list[tuple[str, str]]:
    # Every story shares one spec list (Status + Priority + Size + Points).
    return list(_FIELD_SPECS)


def _mutations_for_item(
    story: dict[str, Any],
    item_id: str,
    project_id: str,
    field_map: dict[str, dict],
    start_idx: int,
    remote_values: dict[str, Any],
) -> tuple[list[str], int]:
    mutations: list[str] = []
    idx = start_idx
    for field_name, story_key in _field_specs_for_item(story):
        raw = story.get(story_key)
        field = field_map.get(field_name)
        if not field or raw is None or raw == "":
            continue
        if board.should_skip_field(field_name, raw, remote_values):
            print(f"  {story.get('title', '')} {field_name} already {raw!r} — skipped")
            continue
        gql = board.build_field_value(field_map, field_name, raw)
        if gql is None:
            continue
        mutations.append(board.mutation_for_field(project_id, item_id, field["id"], gql, idx))
        idx += 1
    return mutations, idx


def _collect_mutations(
    stories: list[dict[str, Any]],
    items: list[dict],
    project_id: str,
    field_map: dict[str, dict],
    remote_by_item: dict[str, dict[str, Any]],
) -> list[str]:
    """Build GraphQL mutation aliases for all stories with known project items."""
    mutations: list[str] = []
    idx = 0
    for s in stories:
        num = s.get("issue_number")
        if not num:
            continue
        item_id = board.find_item_id(items, num)
        if not item_id:
            print(f"  ⚠ Could not find item ID for #{num}, skipping fields", file=sys.stderr)
            continue
        per_item_remote = remote_by_item.get(item_id, {})
        new_mutations, idx = _mutations_for_item(
            s, item_id, project_id, field_map, idx, per_item_remote
        )
        mutations.extend(new_mutations)
    return mutations


def _log_pass2_progress(stories: list[dict[str, Any]]) -> None:
    for s in stories:
        status = s.get("status") or "no status"
        print(f"  ✓ {s.get('title', '')} [{status}]")


def run_pass2_batched(
    stories: list[dict[str, Any]],
    items: list[dict],
    project_id: str,
    field_map: dict[str, dict],
    repo: str,
    remote_by_item: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Batched GraphQL field updates for Status + Priority."""
    remote_by_item = remote_by_item or {}
    gh.execute_batched_mutations(
        _collect_mutations(stories, items, project_id, field_map, remote_by_item)
    )
    _log_pass2_progress(stories)


# ── Writeback ──────────────────────────────────────────────────────────────


def _writeback_numbers(
    stories: list[dict], backlog_data: dict[str, Any], backlog_path: Path
) -> None:
    backlog.save_flat_data(stories, backlog_path, backlog_data)
    print(f"\nUpdated: {backlog_path}")


# ── convert orchestration ──────────────────────────────────────────────────


def convert(identity: Identity, backlog_path: Path, *, dry_run: bool = False) -> int:
    """Create/update issues from the lean backlog and mirror them to the board."""
    _created_titles.clear()
    stories, _, backlog_data = backlog.load_flat_data(backlog_path)
    print(f"Convert mode: {len(stories)} story(ies)")
    numbers_before = [s.get("issue_number") for s in stories]
    project_id, field_map = _fetch_project_metadata(identity)
    changed = _ensure_all_issues(stories, identity.repo)
    # Re-linking an existing issue by title also populates issue_number in
    # memory; persist it even when no new issue was created.
    relinked = any(
        s.get("issue_number") != before for s, before in zip(stories, numbers_before)
    )
    _refresh_issue_bodies(stories, identity.repo)
    _run_remote_passes(stories, project_id, field_map, identity)
    if (changed or relinked) and not dry_run:
        _writeback_numbers(stories, backlog_data, backlog_path)
    return 0


def _fetch_project_metadata(identity: Identity) -> tuple[str, dict[str, dict]]:
    print("Fetching project metadata...")
    project_id = board.get_project_id(identity.project, identity.owner)
    field_map = board.build_field_map(board.get_project_fields(identity.project, identity.owner))
    print(f"  Project ID: {project_id}")
    print(f"  Fields: {list(field_map.keys())}")
    if _ensure_required_fields(project_id, field_map):
        field_map = board.build_field_map(
            board.get_project_fields(identity.project, identity.owner)
        )
        print(f"  Fields: {list(field_map.keys())}")
    return project_id, field_map


def _ensure_required_fields(project_id: str, field_map: dict[str, dict]) -> bool:
    created = False
    for fname, ftype, foptions in board.CONVERT_FIELDS:
        if board.ensure_project_field(project_id, fname, ftype, field_map, foptions):
            created = True
    if created:
        print("  Re-fetching fields after creation...")
    return created


def _ensure_all_issues(stories: list[dict], repo: str) -> bool:
    print("\nFetching existing issues...")
    existing = gh.fetch_all_open_issues(repo)
    print(f"  Found {len(existing)} open issues")
    return _resolve_or_create(stories, existing, repo, "stories")


def _refresh_issue_bodies(stories: list[dict], repo: str) -> None:
    print("\nRefreshing issue bodies...")
    gh.update_issue_bodies(repo, stories)


def _apply_labels(stories: list[dict], repo: str) -> None:
    """Add each story's groomed ``labels`` to its issue (idempotent ``--add-label``)."""
    print("\nApplying labels...")
    for story in stories:
        num = story.get("issue_number")
        if num and story.get("labels"):
            gh.add_labels(repo, num, story["labels"])


def _await_project_items(
    identity: Identity,
    expected_numbers: set[int],
    attempts: int = _ITEM_POLL_ATTEMPTS,
    delay: float = _ITEM_POLL_DELAY,
) -> list[dict]:
    """Poll the project until the just-added items appear (eventual consistency).

    A naive read immediately after ``addProjectV2ItemById`` can miss the new
    items, which would make the field pass skip Status/Priority. Poll briefly
    until every expected issue number is present, or attempts run out.
    """
    items = board.get_project_items(identity.project, identity.owner)
    if not expected_numbers:
        return items
    for _ in range(max(0, attempts - 1)):
        present = {(it.get("content") or {}).get("number") for it in items}
        if expected_numbers <= present:
            return items
        time.sleep(delay)
        items = board.get_project_items(identity.project, identity.owner)
    return items


def _run_remote_passes(
    stories: list[dict], project_id: str, field_map: dict[str, dict], identity: Identity
) -> None:
    _apply_labels(stories, identity.repo)
    node_ids, existing_edges, _ = _add_all_to_project_batched(stories, project_id, identity.repo)
    print("\nFetching project items...")
    expected = {s["issue_number"] for s in stories if s.get("issue_number")}
    items = _await_project_items(identity, expected)
    print(f"  Found {len(items)} items in project")
    remote_by_item = board.build_remote_values_map(items)
    print("\nSetting project fields (batched GraphQL)...")
    run_pass2_batched(stories, items, project_id, field_map, identity.repo, remote_by_item=remote_by_item)
    print("\nSetting blocking relationships...")
    gh.set_blocking_relationships(
        identity.repo, stories, node_ids=node_ids, existing_edges=existing_edges
    )
