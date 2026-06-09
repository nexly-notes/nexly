"""GitHub Projects sync library.

Exposes the :class:`Syncer` class plus stateless module-level helpers that
talk to the ``gh`` CLI. The CLI wrapper lives in ``project_manager.cli``.

Every item — story OR sub-issue — is a real GitHub issue with its own
project-board item, ``Status``/``Priority``/``Start date``/``Target date``
fields, ``labels``, and ``blocked_by`` (issue-number) edges. Parent↔child
links are reconciled as native sub-issues. Issue identity is the bare
``title``. ``pull`` mirrors GitHub state back into ``backlog.json``.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import DATA_PATHS, OWNER, PROJECT_NUMBER, REPO
from .utils.gh_utils import gh_json, run

MAX_WORKERS = 8
BATCH_SIZE = 30

# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------


def issue_url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/issues/{number}"


def build_issue_body(item: dict[str, Any]) -> str:
    """Build an issue body from the item's description + AC checklist.

    Tasks are native sub-issues now, so the body carries only the
    description followed by an ``## Acceptance Criteria`` checklist. Empty
    sections are skipped so the body never carries a dangling separator.

    Args:
        item (dict): Item record. Reads ``description`` (str) and
            ``acceptance_criteria`` (list[str]).

    Returns:
        str: Markdown body, or empty string when every section is empty.

    Example:
        >>> build_issue_body({"acceptance_criteria": ["AC1"]})
        '## Acceptance Criteria\\n\\n- [ ] AC1'
    """
    description = (item.get("description") or "").strip()
    criteria = item.get("acceptance_criteria", []) or []
    sections: list[str] = []
    if description:
        sections.append(description)
    if criteria:
        checklist = "\n".join(f"- [ ] {ac}" for ac in criteria)
        sections.append(f"## Acceptance Criteria\n\n{checklist}")
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# GitHub ``gh`` command helpers
# ---------------------------------------------------------------------------


def ensure_label(label: str, repo: str) -> None:
    run(["gh", "label", "create", label, "--repo", repo, "--force"], check=False)


def _gh_issue_list(repo: str, state: str, limit: int = 500) -> list[dict[str, Any]]:
    out = run(
        [
            "gh", "issue", "list", "--repo", repo, "--state", state,
            "--json", "title,number", "--limit", str(limit),
        ],
        check=False,
    )
    return json.loads(out) if out else []


def fetch_all_open_issues(repo: str) -> dict[str, int]:
    """Fetch all open issues in one call. Returns {title: number} map."""
    return {issue["title"]: issue["number"] for issue in _gh_issue_list(repo, "open")}


def find_existing_issue(repo: str, title: str) -> int | None:
    """Search for an open issue by exact title. Returns issue number if found."""
    out = run(
        [
            "gh", "issue", "list", "--repo", repo,
            "--search", f'"{title}" in:title', "--state", "open",
            "--json", "title,number",
        ],
        check=False,
    )
    if not out:
        return None
    for issue in json.loads(out):
        if issue.get("title") == title:
            return issue["number"]
    return None


def _get_issue_node_id(repo: str, issue_num: int) -> str | None:
    """Get the GraphQL node ID for an issue."""
    out = run(
        ["gh", "api", f"repos/{repo}/issues/{issue_num}", "--jq", ".node_id"],
        check=False,
    )
    return out if out else None


def _fetch_all_issues(repo: str, state: str = "all") -> list[dict[str, Any]]:
    """Fetch issues by state (open, closed, all). Returns list of {title, number}."""
    if state == "all":
        return _gh_issue_list(repo, "open") + _gh_issue_list(repo, "closed")
    return _gh_issue_list(repo, state)


# ---------------------------------------------------------------------------
# Flat data load / save
# ---------------------------------------------------------------------------


def _build_metadata(backlog: dict) -> dict:
    return {
        "description": backlog.get("description", ""),
        "dates": backlog.get("dates", {}),
        "project": backlog.get("project", ""),
    }


def load_flat_data(
    backlog_path: Path,
) -> tuple[list[dict], list[dict], dict, dict[str, Any]]:
    """Load the backlog file as issue-bearing items.

    Returns ``(stories, tasks, metadata, backlog_data)`` where ``stories``
    and ``tasks`` are **references** into ``backlog_data`` (so issue-number
    writeback mutates the file structure directly). ``tasks`` now holds the
    full child items — each is its own GitHub issue.

    Args:
        backlog_path (Path): Path to ``backlog.json``.

    Returns:
        tuple: ``(stories, tasks, metadata, backlog_data)``.

    Example:
        >>> load_flat_data(Path("backlog.json"))  # doctest: +SKIP
        Return: ([story...], [child...], {...}, {...})
    """
    backlog_data = json.loads(backlog_path.read_text(encoding="utf-8"))
    metadata = _build_metadata(backlog_data)
    stories = list(backlog_data.get("stories", []))
    tasks: list[dict] = []
    for story in stories:
        tasks.extend(story.get("tasks", []))
    return stories, tasks, metadata, backlog_data


def _title_to_issue_number(all_items: list[dict]) -> dict[str, int]:
    return {
        it["title"]: it["issue_number"]
        for it in all_items
        if it.get("title") and it.get("issue_number")
    }


def _apply_issue_number(item: dict, num_by_title: dict[str, int]) -> None:
    title = item.get("title")
    if title in num_by_title:
        item["issue_number"] = num_by_title[title]


def save_flat_data(
    stories: list[dict],
    tasks: list[dict],
    backlog_path: Path,
    backlog_data: dict[str, Any],
) -> None:
    """Write ``issue_number`` back onto parents AND children, then save.

    Every item is now an issue, so the minted numbers are matched onto the
    on-disk structure by ``title`` (the pre-sync identity) for both stories
    and their nested sub-issues.

    Args:
        stories (list[dict]): Story items carrying minted numbers.
        tasks (list[dict]): Child items carrying minted numbers.
        backlog_path (Path): Destination file.
        backlog_data (dict[str, Any]): Full backlog to rewrite.

    Returns:
        None: Side-effects only.

    SideEffect:
        Sets ``issue_number`` on matching stories + tasks; writes the file.

    Example:
        >>> save_flat_data(s, t, p, data)  # doctest: +SKIP
        Return: None
    """
    num_by_title = _title_to_issue_number(stories + tasks)
    for story in backlog_data.get("stories", []):
        _apply_issue_number(story, num_by_title)
        for task in story.get("tasks", []):
            _apply_issue_number(task, num_by_title)
    backlog_path.write_text(json.dumps(backlog_data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Blocking relationships
# ---------------------------------------------------------------------------


def _collect_blocking_pairs(
    items: list[dict],
) -> tuple[list[tuple[int, int]], set[int]]:
    """Collect ``(blocked_num, blocker_num)`` pairs straight from item data.

    ``blocked_by`` already holds issue numbers, so no id→number map is
    needed — each item contributes one pair per blocker.

    Args:
        items (list[dict]): All issue-bearing items (stories + sub-issues).

    Returns:
        tuple[list[tuple[int, int]], set[int]]: ``(pairs, involved_numbers)``.

    Example:
        >>> _collect_blocking_pairs(
        ...     [{"issue_number": 1, "blocked_by": [2]}])
        ([(1, 2)], {1, 2})
    """
    pairs: list[tuple[int, int]] = []
    involved: set[int] = set()
    for item in items:
        item_num = item.get("issue_number")
        if not item_num:
            continue
        for blocker_num in item.get("blocked_by", []):
            pairs.append((item_num, blocker_num))
            involved.update({item_num, blocker_num})
    return pairs, involved


def _fetch_node_ids(repo: str, issue_nums: set[int]) -> dict[int, str]:
    """Batched node-ID lookup via a single GraphQL query."""
    ids, _, _ = _fetch_node_ids_and_edges(repo, issue_nums)
    return ids


def _fetch_node_ids_and_edges(
    repo: str, issue_nums: set[int]
) -> tuple[dict[int, str], set[tuple[int, int]], dict[int, int]]:
    """Fetch node IDs, blocker edges, and parent links in one GraphQL call.

    Folding the lookups into a single query lets Pass 4 skip already-present
    blocker pairs (``addBlockedBy`` isn't idempotent and rejects the whole
    batch with "Target issue has already been taken"). The ``parent`` link
    in the response is retained for tuple-shape compatibility but is no
    longer consumed by any sync pass.

    Args:
        repo (str): ``owner/name`` slug.
        issue_nums (set[int]): Issue numbers to resolve.

    Returns:
        tuple[dict[int, str], set[tuple[int, int]], dict[int, int]]:
            ``(num→node_id, {(blocked_num, blocker_num)},
            {child_num: parent_num})``.

    Example:
        >>> _fetch_node_ids_and_edges("o/r", {100})  # doctest: +SKIP
        Return: ({100: "NODE-100"}, {(100, 200)}, {100: 300})
    """
    nums = sorted(set(issue_nums))
    if not nums:
        return {}, set(), {}
    query = _build_node_id_edges_query(repo, nums)
    result = gh_json(["gh", "api", "graphql", "-f", f"query={query}"])
    repo_data = (result or {}).get("data", {}).get("repository") or {}
    return _parse_node_id_edges_response(repo_data)


def _build_node_id_edges_query(repo: str, nums: list[int]) -> str:
    """Build the batched GraphQL query for id + blockedBy + parent per issue."""
    owner, name = repo.split("/", 1)
    aliases = " ".join(
        f"i{n}: issue(number: {n}) {{ id number "
        f"blockedBy(first: 100) {{ nodes {{ number }} }} "
        f"parent {{ number }} }}"
        for n in nums
    )
    return f'{{ repository(owner: "{owner}", name: "{name}") {{ {aliases} }} }}'


def _parse_node_id_edges_response(
    repo_data: dict,
) -> tuple[dict[int, str], set[tuple[int, int]], dict[int, int]]:
    """Extract node-id map, existing (blocked, blocker) edges, and parent links."""
    ids: dict[int, str] = {}
    edges: set[tuple[int, int]] = set()
    parents: dict[int, int] = {}
    for val in repo_data.values():
        if not (val and val.get("id")):
            continue
        num = val["number"]
        ids[num] = val["id"]
        for b in (val.get("blockedBy") or {}).get("nodes") or []:
            if b.get("number"):
                edges.add((num, b["number"]))
        parent = val.get("parent") or {}
        if isinstance(parent, dict) and parent.get("number"):
            parents[num] = parent["number"]
    return ids, edges, parents


def _blocking_mutations(
    num_to_node: dict[int, str],
    pairs: list[tuple[int, int]],
    existing_edges: set[tuple[int, int]],
) -> list[str]:
    mutations: list[str] = []
    for bn, kn in pairs:
        if (bn, kn) in existing_edges:
            print(f"  #{bn} already blocked by #{kn} — skipped")
            continue
        b, k = num_to_node.get(bn), num_to_node.get(kn)
        if not b or not k:
            print(f"  ⚠ Missing node ID for #{bn} or #{kn}")
            continue
        print(f"  #{bn} blocked by #{kn}")
        mutations.append(
            f"m{len(mutations)}: addBlockedBy(input: {{"
            f"issueId: {json.dumps(b)}, blockingIssueId: {json.dumps(k)}"
            f"}}) {{ issue {{ number }} blockingIssue {{ number }} }}"
        )
    return mutations


def set_blocking_relationships(
    repo: str,
    items: list[dict],
    node_ids: dict[int, str] | None = None,
    existing_edges: set[tuple[int, int]] | None = None,
) -> None:
    """Set blocking relationships via batched ``addBlockedBy`` mutations.

    ``blocked_by`` holds issue numbers, so pairs are read straight from the
    items. Pairs already present on GitHub (``existing_edges``) and pairs
    whose blocker node isn't found (dangling numbers from the two-pass
    flow) are skipped.

    Args:
        repo (str): ``owner/name`` slug.
        items (list[dict]): All issue-bearing items.
        node_ids (dict[int, str] | None): Pre-fetched ``num → node_id``.
        existing_edges (set | None): Pre-fetched ``{(blocked, blocker)}``.

    Returns:
        None: Side-effects only.

    SideEffect:
        Calls ``gh api graphql`` (batched ``addBlockedBy``).

    Example:
        >>> set_blocking_relationships("o/r", [])  # doctest: +SKIP
        Return: None
    """
    pairs, involved = _collect_blocking_pairs(items)
    if not pairs:
        print("  No blocking relationships to set.")
        return
    if node_ids is None or existing_edges is None:
        print(f"  Fetching node IDs + existing edges for {len(involved)} issues...")
        node_ids, existing_edges, _ = _fetch_node_ids_and_edges(repo, involved)
    execute_batched_mutations(
        _blocking_mutations(node_ids, pairs, existing_edges)
    )


# ---------------------------------------------------------------------------
# Project field creation
# ---------------------------------------------------------------------------


def _create_project_field_mutation(project_id: str, field_name: str, inner: str) -> str:
    return f"""
    mutation {{
      createProjectV2Field(input: {{
        projectId: {json.dumps(project_id)},
        {inner},
        name: {json.dumps(field_name)}
      }}) {{
        projectV2Field {{ ... on ProjectV2Field {{ id }} }}
      }}
    }}
    """


def _create_single_select_field(project_id: str, field_name: str, options: list[str]) -> None:
    options_str = ", ".join(
        f'{{name: {json.dumps(opt)}, color: GRAY, description: ""}}' for opt in options
    )
    mutation = (
        f"mutation {{ createProjectV2Field(input: {{"
        f"projectId: {json.dumps(project_id)},"
        f" dataType: SINGLE_SELECT,"
        f" name: {json.dumps(field_name)},"
        f" singleSelectOptions: [{options_str}]"
        f"}}) {{ projectV2Field {{ ... on ProjectV2SingleSelectField {{ id }} }} }} }}"
    )
    run(["gh", "api", "graphql", "-f", f"query={mutation}"], check=False)


def _create_simple_field(project_id: str, field_name: str, data_type: str) -> None:
    mutation = _create_project_field_mutation(project_id, field_name, f"dataType: {data_type}")
    run(["gh", "api", "graphql", "-f", f"query={mutation}"], check=False)


def ensure_project_field(
    project_id: str,
    field_name: str,
    field_type: str,
    field_map: dict[str, dict],
    options: list[str] | None = None,
) -> bool:
    """Create a project field if it doesn't exist. Returns True if created."""
    if field_name in field_map:
        return False
    print(f"  Creating missing field: {field_name} ({field_type})")
    if field_type == "SINGLE_SELECT" and options:
        _create_single_select_field(project_id, field_name, options)
    elif field_type in ("NUMBER", "TEXT", "DATE"):
        _create_simple_field(project_id, field_name, field_type)
    return True


def _missing_option_mutation(
    field_id: str, existing: list[str], wanted: str
) -> str | None:
    """Build a mutation that appends ``wanted`` to a single-select field.

    GitHub matches single-select options by name, so re-sending the existing
    names preserves those options (and their item assignments) while adding the
    new one. Colors are not readable from ``field-list``, so re-sent options
    reset to GRAY — a one-time cosmetic change on the sync that adds ``wanted``.

    Args:
        field_id (str): The single-select field's node id.
        existing (list[str]): Current option names on the field.
        wanted (str): Option name to ensure is present.

    Returns:
        str | None: The GraphQL mutation, or ``None`` if already present.

    Example:
        >>> _missing_option_mutation("F", ["Backlog"], "Ready")  # doctest: +SKIP
        'mutation { updateProjectV2Field(input: {fieldId: "F", ...}) ... }'
        >>> _missing_option_mutation("F", ["Ready"], "Ready")
    """
    if wanted in existing:
        return None
    opts = ", ".join(
        f'{{name: {json.dumps(n)}, color: GRAY, description: ""}}'
        for n in list(existing) + [wanted]
    )
    return (
        f"mutation {{ updateProjectV2Field(input: {{"
        f"fieldId: {json.dumps(field_id)}, singleSelectOptions: [{opts}]"
        f"}}) {{ projectV2Field {{ ... on ProjectV2SingleSelectField {{ id }} }} }} }}"
    )


def ensure_single_select_option(
    field_name: str, option: str, field_map: dict[str, dict]
) -> bool:
    """Append ``option`` to an existing single-select field if it's missing.

    A no-op when the field is absent (it will be created with full options by
    :func:`ensure_project_field`) or already carries ``option``.

    Args:
        field_name (str): Single-select field to extend (e.g. ``"Status"``).
        option (str): Option name to ensure (e.g. ``"Ready"``).
        field_map (dict[str, dict]): Output of :func:`build_field_map`.

    Returns:
        bool: ``True`` if a mutation was issued (caller should re-fetch fields).

    Example:
        >>> ensure_single_select_option("Status", "Ready", fmap)  # doctest: +SKIP
        Return: True
    """
    field = field_map.get(field_name)
    if not field or "options" not in field:
        return False
    mutation = _missing_option_mutation(field["id"], list(field["options"]), option)
    if mutation is None:
        return False
    print(f"  Adding '{option}' option to {field_name} field")
    run(["gh", "api", "graphql", "-f", f"query={mutation}"], check=False)
    return True


# ---------------------------------------------------------------------------
# Issue creation / resolution
# ---------------------------------------------------------------------------


def _resolve_one(
    t: dict[str, Any], existing_issues: dict[str, int], live: set[int]
) -> bool:
    """True if linked to a live issue; False if creation needed."""
    num = t.get("issue_number")
    if num and num in live:
        print(f"  ↳ Already has issue: #{num}")
        return True
    if num:
        print(f"  ↳ Stale #{num}; re-linking by title or re-creating")
        t.pop("issue_number", None)
    title = t["title"]
    if title in existing_issues:
        t["issue_number"] = existing_issues[title]
        print(f"  ↳ Matched existing #{t['issue_number']}")
        return True
    return False


def resolve_existing_issues(
    tasks: list[dict[str, Any]], existing_issues: dict[str, int]
) -> list[dict[str, Any]]:
    """Return tasks that still need a new issue created."""
    live = set(existing_issues.values())
    return [t for t in tasks if not _resolve_one(t, existing_issues, live)]


_create_lock = threading.Lock()
_created_titles: set[str] = set()


def _claim_title(full_title: str) -> None:
    with _create_lock:
        if full_title in _created_titles:
            raise RuntimeError(f"Duplicate title detected, skipping: {full_title}")
        _created_titles.add(full_title)


def _issue_labels(item: dict[str, Any]) -> list[str]:
    """Return the item's own ``labels``, lowercased for GH uniqueness.

    Args:
        item (dict): Item record. Reads ``labels`` (list[str]).

    Returns:
        list[str]: Lowercased labels (empty when none supplied).

    Example:
        >>> _issue_labels({"labels": ["Infra", "P0"]})
        ['infra', 'p0']
    """
    return [str(lab).lower() for lab in item.get("labels") or []]


def _build_create_issue_cmd(
    repo: str, title: str, body: str, labels: list[str], assignees: list[str]
) -> list[str]:
    cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
    for lab in labels:
        cmd += ["--label", lab]
    for a in assignees:
        cmd += ["--assignee", a]
    return cmd


def _create_issue(task: dict[str, Any], repo: str) -> int:
    """Create a single issue. Returns issue number. Thread-safe with dedup guard."""
    title = task["title"]
    _claim_title(title)
    labels = _issue_labels(task)
    for lab in labels:
        ensure_label(lab, repo)
    cmd = _build_create_issue_cmd(
        repo, title, build_issue_body(task), labels, task.get("assignees") or []
    )
    url = run(cmd).strip()
    if not url:
        raise RuntimeError(f"gh issue create returned no URL for: {title}")
    number = int(url.rstrip("/").split("/")[-1])
    task["issue_number"] = number
    return number


def ensure_issue(
    task: dict[str, Any], repo: str, existing_issues: dict[str, int] | None = None
) -> int:
    """Ensure an issue exists. Returns issue number."""
    if task.get("issue_number"):
        return task["issue_number"]
    title = task["title"]
    if existing_issues and title in existing_issues:
        num = existing_issues[title]
        print(f"  ↳ Found existing issue: #{num}")
        task["issue_number"] = num
        return num
    existing = find_existing_issue(repo, title)
    if existing:
        print(f"  ↳ Found existing issue: #{existing}")
        task["issue_number"] = existing
        return existing
    return _create_issue(task, repo)


def _build_body_fetch_query(repo: str, nums: list[int]) -> str:
    """Build batched GraphQL query for ``id`` + ``body`` per issue."""
    owner, name = repo.split("/", 1)
    # One alias per issue keeps everything in a single round trip.
    aliases = " ".join(
        f"i{n}: issue(number: {n}) {{ id number body }}" for n in nums
    )
    return f'{{ repository(owner: "{owner}", name: "{name}") {{ {aliases} }} }}'


def _parse_issue_bodies_response(repo_data: dict) -> dict[int, tuple[str, str]]:
    """Extract ``{number: (node_id, body)}`` from a GraphQL repository payload."""
    out: dict[int, tuple[str, str]] = {}
    for val in repo_data.values():
        if not (val and val.get("id")):
            continue
        out[val["number"]] = (val["id"], val.get("body") or "")
    return out


def _fetch_issue_bodies(
    repo: str, issue_nums: set[int]
) -> dict[int, tuple[str, str]]:
    """Fetch ``(node_id, body)`` for each issue in one GraphQL call.

    Used by Pass 1c to decide whether the remote body needs refreshing.
    Empty input short-circuits so we never issue a wasted query.

    Args:
        repo (str): ``owner/name`` slug.
        issue_nums (set[int]): Issue numbers to resolve.

    Returns:
        dict[int, tuple[str, str]]: ``{number: (node_id, body)}``.

    Example:
        >>> _fetch_issue_bodies("o/r", set())
        {}
    """
    nums = sorted(set(issue_nums))
    if not nums:
        return {}
    # Single GraphQL round trip via aliases — same pattern as
    # `_fetch_node_ids_and_edges`.
    query = _build_body_fetch_query(repo, nums)
    result = gh_json(["gh", "api", "graphql", "-f", f"query={query}"])
    repo_data = (result or {}).get("data", {}).get("repository") or {}
    return _parse_issue_bodies_response(repo_data)


def _update_issue_body_mutation(node_id: str, body: str, idx: int) -> str:
    """Build a single GraphQL ``updateIssue`` mutation alias."""
    return (
        f"m{idx}: updateIssue(input: {{"
        f"id: {json.dumps(node_id)}, "
        f"body: {json.dumps(body)}"
        f"}}) {{ issue {{ number }} }}"
    )


def _collect_body_update_mutations(
    stories: list[dict[str, Any]],
    bodies: dict[int, tuple[str, str]],
) -> list[str]:
    """Build ``updateIssue`` mutations only for stories whose body differs.

    Stories without a known ``issue_number`` (e.g. just created and not yet
    fetched) and stories whose remote body already matches the rebuild are
    both skipped, so an idempotent re-sync emits zero mutations.

    Args:
        stories (list[dict]): Story records with ``issue_number`` populated.
        bodies (dict[int, tuple[str, str]]): Output of
            :func:`_fetch_issue_bodies`.

    Returns:
        list[str]: GraphQL mutation aliases, ready for
        :func:`execute_batched_mutations`.

    Example:
        >>> _collect_body_update_mutations([], {})
        []
    """
    mutations: list[str] = []
    for story in stories:
        num = story.get("issue_number")
        if not num or num not in bodies:
            # No issue yet (or missing from fetch) — skip silently; the
            # creation path already wrote the freshly built body.
            continue
        node_id, remote_body = bodies[num]
        new_body = build_issue_body(story)
        if new_body == remote_body:
            print(f"  {story.get('title', '')} body already current — skipped")
            continue
        mutations.append(
            _update_issue_body_mutation(node_id, new_body, len(mutations))
        )
        print(f"  {story.get('title', '')} body needs refresh -> #{num}")
    return mutations


def update_issue_bodies(repo: str, stories: list[dict[str, Any]]) -> None:
    """Refresh GitHub issue bodies for every story with an ``issue_number``.

    Diffs each story's rebuilt body (description + tasks + AC) against the
    remote snapshot. Only stories that drifted get an ``updateIssue``
    mutation, so the no-op re-sync stays cheap.

    Args:
        repo (str): ``owner/name`` slug.
        stories (list[dict]): Story records.

    Returns:
        None: Side-effects only.

    SideEffect:
        Calls ``gh api graphql`` (one fetch + one batched mutation pass).

    Example:
        >>> update_issue_bodies("o/r", [])  # doctest: +SKIP
        Return: None
    """
    nums = {s["issue_number"] for s in stories if s.get("issue_number")}
    if not nums:
        # Nothing to refresh — typically a first sync where all issues
        # were just created (and already carry the freshly built body).
        return
    bodies = _fetch_issue_bodies(repo, nums)
    execute_batched_mutations(_collect_body_update_mutations(stories, bodies))


def _build_sub_issues_query(repo: str, nums: list[int]) -> str:
    """Build batched GraphQL query for ``id`` + ``title`` + ``subIssues``."""
    owner, name = repo.split("/", 1)
    aliases = " ".join(
        f"i{n}: issue(number: {n}) {{ id number title "
        f"subIssues(first: 100) {{ nodes {{ id number title }} }} }}"
        for n in nums
    )
    return f'{{ repository(owner: "{owner}", name: "{name}") {{ {aliases} }} }}'


def _parse_sub_issues_response(
    repo_data: dict,
) -> tuple[dict[int, str], dict[int, list[tuple[int, str, str]]]]:
    """Extract node ids and sub-issue lists from a GraphQL repository payload."""
    node_ids: dict[int, str] = {}
    subs_by_num: dict[int, list[tuple[int, str, str]]] = {}
    for val in repo_data.values():
        if not (val and val.get("id")):
            continue
        num = val["number"]
        node_ids[num] = val["id"]
        # Flatten to ``(number, node_id, title)`` so both reconcile (push)
        # and tree-rebuild (pull) can address sub-issues directly.
        subs_by_num[num] = [
            (s["number"], s["id"], s.get("title", ""))
            for s in (val.get("subIssues") or {}).get("nodes") or []
        ]
    return node_ids, subs_by_num


def _fetch_sub_issues(
    repo: str, parent_nums: set[int]
) -> tuple[dict[int, str], dict[int, list[tuple[int, str, str]]]]:
    """Fetch existing sub-issue links for each parent issue.

    Empty input short-circuits to avoid a wasted call.

    Args:
        repo (str): ``owner/name`` slug.
        parent_nums (set[int]): Parent issue numbers to inspect.

    Returns:
        tuple: ``(node_ids, subs_by_num)`` where ``subs_by_num`` is
        ``{parent_num: [(sub_num, sub_node_id, sub_title), ...]}``.

    Example:
        >>> _fetch_sub_issues("o/r", set())
        ({}, {})
    """
    nums = sorted(set(parent_nums))
    if not nums:
        return {}, {}
    query = _build_sub_issues_query(repo, nums)
    result = gh_json(["gh", "api", "graphql", "-f", f"query={query}"])
    repo_data = (result or {}).get("data", {}).get("repository") or {}
    return _parse_sub_issues_response(repo_data)


def _add_sub_issue_mutation(parent_id: str, sub_id: str, idx: int) -> str:
    """Build a single GraphQL ``addSubIssue`` mutation alias."""
    return (
        f"m{idx}: addSubIssue(input: {{"
        f"issueId: {json.dumps(parent_id)}, "
        f"subIssueId: {json.dumps(sub_id)}"
        f"}}) {{ issue {{ number }} }}"
    )


def _remove_sub_issue_mutation(parent_id: str, sub_id: str, idx: int) -> str:
    """Build a single GraphQL ``removeSubIssue`` mutation alias."""
    return (
        f"m{idx}: removeSubIssue(input: {{"
        f"issueId: {json.dumps(parent_id)}, "
        f"subIssueId: {json.dumps(sub_id)}"
        f"}}) {{ issue {{ number }} }}"
    )


def _desired_sub_issue_pairs(stories: list[dict[str, Any]]) -> set[tuple[int, int]]:
    """Return ``{(parent_num, child_num)}`` the backlog wants linked.

    Args:
        stories (list[dict]): Story records with numbered ``tasks``.

    Returns:
        set[tuple[int, int]]: Desired parent↔child links (numbered only).

    Example:
        >>> _desired_sub_issue_pairs(
        ...     [{"issue_number": 1, "tasks": [{"issue_number": 2}]}])
        {(1, 2)}
    """
    pairs: set[tuple[int, int]] = set()
    for story in stories:
        pnum = story.get("issue_number")
        if not pnum:
            continue
        for task in story.get("tasks", []):
            cnum = task.get("issue_number")
            if cnum:
                pairs.add((pnum, cnum))
    return pairs


def _existing_sub_issue_pairs(
    subs_by_num: dict[int, list[tuple[int, str, str]]],
) -> set[tuple[int, int]]:
    """Return ``{(parent_num, child_num)}`` currently linked on GitHub."""
    pairs: set[tuple[int, int]] = set()
    for pnum, subs in subs_by_num.items():
        for cnum, _node, _title in subs:
            pairs.add((pnum, cnum))
    return pairs


def _link_mutation(
    node_ids: dict[int, str], pnum: int, cnum: int, idx: int, *, add: bool
) -> str | None:
    pnode, cnode = node_ids.get(pnum), node_ids.get(cnum)
    if not pnode or not cnode:
        print(f"  ⚠ Missing node id for #{pnum} or #{cnum}")
        return None
    if add:
        print(f"  Linking sub-issue #{cnum} under #{pnum}")
        return _add_sub_issue_mutation(pnode, cnode, idx)
    print(f"  Detaching sub-issue #{cnum} from #{pnum}")
    return _remove_sub_issue_mutation(pnode, cnode, idx)


def _reconcile_sub_issue_mutations(
    desired: set[tuple[int, int]],
    existing: set[tuple[int, int]],
    node_ids: dict[int, str],
) -> list[str]:
    """Link desired-but-missing pairs and detach existing-but-undesired ones.

    Args:
        desired (set): Parent↔child links the backlog wants.
        existing (set): Parent↔child links currently on GitHub.
        node_ids (dict[int, str]): ``num → node_id`` for all involved issues.

    Returns:
        list[str]: ``addSubIssue`` then ``removeSubIssue`` mutation aliases.

    Example:
        >>> _reconcile_sub_issue_mutations({(1, 2)}, {(1, 2)}, {})
        []
    """
    mutations: list[str] = []
    for pnum, cnum in sorted(desired - existing):
        m = _link_mutation(node_ids, pnum, cnum, len(mutations), add=True)
        if m:
            mutations.append(m)
    for pnum, cnum in sorted(existing - desired):
        m = _link_mutation(node_ids, pnum, cnum, len(mutations), add=False)
        if m:
            mutations.append(m)
    return mutations


def reconcile_sub_issues(repo: str, stories: list[dict[str, Any]]) -> None:
    """Reconcile native sub-issue links to match the backlog tree.

    Each story's ``tasks`` are the desired children; GitHub's current
    sub-issue links are fetched and the difference is linked/detached.

    Args:
        repo (str): ``owner/name`` slug.
        stories (list[dict]): Story records with numbered tasks.

    Returns:
        None: Side-effects only.

    SideEffect:
        Calls ``gh api graphql`` (fetches + one batched mutation pass).

    Example:
        >>> reconcile_sub_issues("o/r", [])  # doctest: +SKIP
        Return: None
    """
    parent_nums = {s["issue_number"] for s in stories if s.get("issue_number")}
    if not parent_nums:
        print("  No parent issues to reconcile sub-issues for.")
        return
    desired = _desired_sub_issue_pairs(stories)
    involved = parent_nums | {c for _p, c in desired}
    node_ids, _, _ = _fetch_node_ids_and_edges(repo, involved)
    _, subs_by_num = _fetch_sub_issues(repo, parent_nums)
    mutations = _reconcile_sub_issue_mutations(
        desired, _existing_sub_issue_pairs(subs_by_num), node_ids
    )
    if not mutations:
        print("  Sub-issue links already current.")
        return
    execute_batched_mutations(mutations)


def _ensure_issue_labels(repo: str, item: dict[str, Any]) -> None:
    """Add the item's labels to its existing GitHub issue (idempotent).

    ``gh issue edit --add-label`` is a no-op for labels already present, so
    re-running is safe.

    Args:
        repo (str): ``owner/name`` slug.
        item (dict): Item with ``issue_number`` and ``labels``.

    Returns:
        None: Side-effects only.

    SideEffect:
        Creates labels then calls ``gh issue edit`` when both number and
        labels are present.

    Example:
        >>> _ensure_issue_labels("o/r", {"labels": []})  # doctest: +SKIP
        Return: None
    """
    num = item.get("issue_number")
    labels = _issue_labels(item)
    if not num or not labels:
        return
    for lab in labels:
        ensure_label(lab, repo)
    cmd = ["gh", "issue", "edit", str(num), "--repo", repo]
    for lab in labels:
        cmd += ["--add-label", lab]
    run(cmd, check=False)


def reconcile_labels(repo: str, items: list[dict[str, Any]]) -> None:
    """Reconcile labels on every already-numbered item's issue."""
    for item in items:
        _ensure_issue_labels(repo, item)


def add_to_project(project_number: int, owner: str, url: str) -> None:
    p = subprocess.run(
        [
            "gh", "project", "item-add", str(project_number),
            "--owner", owner, "--url", url,
        ],
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        print(f"  ⚠ item-add failed for {url}: {p.stderr.strip()}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Project metadata
# ---------------------------------------------------------------------------


_PROJECT_ID_QUERY = """
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) { id }
  }
}
"""


def get_project_id(project_number: int, owner: str) -> str:
    """Get the project node ID via GraphQL."""
    result = gh_json(
        [
            "gh", "api", "graphql",
            "-f", f"query={_PROJECT_ID_QUERY}", "-f", f"owner={owner}",
            "-F", f"number={project_number}",
        ]
    )
    return result["data"]["user"]["projectV2"]["id"]


def get_project_fields(project_number: int, owner: str) -> list[dict]:
    """Get all project fields with their IDs and options."""
    return gh_json(
        [
            "gh", "project", "field-list", str(project_number),
            "--owner", owner, "--format", "json",
        ]
    ).get("fields", [])


def get_project_items(project_number: int, owner: str) -> list[dict]:
    """Get all project items."""
    return gh_json(
        [
            "gh", "project", "item-list", str(project_number),
            "--owner", owner, "--format", "json", "--limit", "200",
        ]
    ).get("items", [])


def _project_issues(project_number: int, owner: str) -> list[dict[str, Any]]:
    """Return ``[{title, number}]`` for every issue attached to the project."""
    items = get_project_items(project_number, owner)
    result: list[dict[str, Any]] = []
    for it in items:
        content = it.get("content") or {}
        number = content.get("number")
        if number:
            result.append({"title": content.get("title", ""), "number": number})
    return result


def build_field_map(fields: list[dict]) -> dict[str, dict]:
    """Build a lookup: ``field_name -> {id, type, options: {option_name: option_id}}``."""
    fmap: dict[str, dict] = {}
    for f in fields:
        entry: dict[str, Any] = {"id": f["id"], "type": f.get("type", "")}
        if "options" in f:
            entry["options"] = {opt["name"]: opt["id"] for opt in f["options"]}
        fmap[f.get("name", "")] = entry
    return fmap


def find_item_id(items: list[dict], number: int) -> str | None:
    """Find the project item ID that matches the given issue number."""
    for item in items:
        if item.get("content", {}).get("number") == number:
            return item["id"]
    return None


# ---------------------------------------------------------------------------
# Field value / mutation helpers
# ---------------------------------------------------------------------------


def _value_flag(value: Any) -> tuple[str, str] | None:
    if isinstance(value, (int, float)):
        return "--number", str(value)
    if isinstance(value, str):
        return "--text", str(value)
    return None


def _append_value_flag(cmd: list[str], field_name: str, value: Any) -> bool:
    flag = _value_flag(value)
    if flag is None:
        print(f"  ⚠ Unsupported value type for '{field_name}': {type(value)}", file=sys.stderr)
        return False
    cmd += list(flag)
    return True


def _append_option_flag(
    cmd: list[str], field_name: str, options: dict[str, str], value: Any
) -> bool:
    option_id = options.get(value)
    if not option_id:
        print(
            f"  ⚠ Option '{value}' not found for field '{field_name}'. "
            f"Available: {list(options.keys())}",
            file=sys.stderr,
        )
        return False
    cmd += ["--single-select-option-id", option_id]
    return True


def _item_edit_cmd(project_id: str, item_id: str, field_id: str) -> list[str]:
    return [
        "gh", "project", "item-edit", "--id", item_id,
        "--field-id", field_id, "--project-id", project_id,
    ]


def set_field(
    project_id: str,
    item_id: str,
    field_map: dict[str, dict],
    field_name: str,
    value: Any,
) -> None:
    """Set a project field value using the correct flags for its type."""
    if value is None or value == "":
        return
    field = field_map.get(field_name)
    if not field:
        print(f"  ⚠ Field '{field_name}' not found in project", file=sys.stderr)
        return
    cmd = _item_edit_cmd(project_id, item_id, field["id"])
    ok = (
        _append_option_flag(cmd, field_name, field["options"], value)
        if field.get("options")
        else _append_value_flag(cmd, field_name, value)
    )
    if ok:
        run(cmd, check=False)


def _gql_value(
    field_map: dict[str, dict], field_name: str, value: Any
) -> dict[str, str] | None:
    if isinstance(value, (int, float)):
        return {"number": str(value)}
    if isinstance(value, str):
        return {"text": json.dumps(value)}
    print(f"  ⚠ Unsupported value type for '{field_name}': {type(value)}", file=sys.stderr)
    return None


# Board fields that take a native date value (``{date: "YYYY-MM-DD"}``)
# rather than a single-select option or number/text.
_DATE_FIELD_NAMES = {"Start date", "Target date"}


def _gql_option_value(
    options: dict[str, str], field_name: str, value: Any
) -> dict[str, str] | None:
    option_id = options.get(value)
    if not option_id:
        print(
            f"  ⚠ Option '{value}' not found for field '{field_name}'. "
            f"Available: {list(options.keys())}",
            file=sys.stderr,
        )
        return None
    return {"singleSelectOptionId": json.dumps(option_id)}


def _build_field_value(
    field_map: dict[str, dict], field_name: str, value: Any
) -> dict[str, str] | None:
    """Convert a field name + value into the GraphQL ``value`` input object."""
    if value is None or value == "":
        return None
    field = field_map.get(field_name)
    if not field:
        print(f"  ⚠ Field '{field_name}' not found in project", file=sys.stderr)
        return None
    if field.get("options"):
        return _gql_option_value(field["options"], field_name, value)
    if field_name in _DATE_FIELD_NAMES:
        return {"date": json.dumps(value)}
    return _gql_value(field_map, field_name, value)


# Every item (story or sub-issue) syncs Status + Priority (single-select)
# plus Start/Target date (native date fields). ``(field_name, item_key)``.
# Local ``end_date`` maps to GitHub's built-in "Target date" board field.
_BASE_FIELD_SPECS: list[tuple[str, str]] = [
    ("Status", "status"),
    ("Priority", "priority"),
    ("Start date", "start_date"),
    ("Target date", "end_date"),
]


# Keys `gh project item-list --format json` emits alongside `id`/`content`
# when the corresponding project field is set; mapped to the canonical
# field names used in `_BASE_FIELD_SPECS`. Dates are best-effort (a missed
# key just re-pushes an unchanged value).
_REMOTE_RAW_KEYS: list[tuple[str, str]] = [
    ("Status", "status"),
    ("Priority", "priority"),
    ("Start date", "start date"),
    ("Target date", "target date"),
]


def _field_specs_for_item(item: dict[str, Any]) -> list[tuple[str, str]]:
    # Stories and sub-issues share one unified field spec list.
    return list(_BASE_FIELD_SPECS)


def _extract_item_field_values(raw_item: dict[str, Any]) -> dict[str, Any]:
    """Pull known project-field values from a ``gh project item-list`` entry.

    Reads the top-level keys the CLI emits (``status``, ``priority``) and
    translates them to the canonical field names the mutation builder
    uses. Absent / empty values are dropped so the caller can treat
    ``key in result`` as "remote has a value for this field".

    Args:
        raw_item (dict): One item dict from ``gh project item-list``.

    Returns:
        dict[str, Any]: ``{canonical_field_name: value}``.

    Example:
        >>> _extract_item_field_values({"id": "X", "status": "Backlog"})
        {'Status': 'Backlog'}
    """
    result: dict[str, Any] = {}
    for canonical, raw_key in _REMOTE_RAW_KEYS:
        val = raw_item.get(raw_key)
        if val is None or val == "":
            continue
        result[canonical] = val
    return result


def _build_remote_values_map(items: list[dict]) -> dict[str, dict[str, Any]]:
    """Build ``{item_id: {field_name: current_value}}`` for all project items.

    The outer key matches the ``item_id`` used as the mutation target in
    ``_mutations_for_item``, so the diff filter can look up the remote
    snapshot in O(1) per field.

    Args:
        items (list[dict]): Items from :func:`get_project_items`.

    Returns:
        dict[str, dict[str, Any]]: Nested map of project-item id to
        per-field remote value.

    Example:
        >>> _build_remote_values_map([{"id": "I1", "status": "Backlog"}])
        {'I1': {'Status': 'Backlog'}}
    """
    return {
        item["id"]: _extract_item_field_values(item)
        for item in items if item.get("id")
    }


def _should_skip_field(
    field_name: str, raw: Any, remote_values: dict[str, Any]
) -> bool:
    """True when the in-memory value already matches the remote snapshot."""
    if field_name not in remote_values:
        return False
    return remote_values[field_name] == raw


def _mutation_for_field(
    project_id: str, item_id: str, field_id: str, gql_value: dict[str, str], idx: int
) -> str:
    value_parts = ", ".join(f"{k}: {v}" for k, v in gql_value.items())
    return (
        f"m{idx}: updateProjectV2ItemFieldValue(input: {{"
        f"projectId: {json.dumps(project_id)}, "
        f"itemId: {json.dumps(item_id)}, "
        f"fieldId: {json.dumps(field_id)}, "
        f"value: {{{value_parts}}}"
        f"}}) {{ projectV2Item {{ id }} }}"
    )


def _mutations_for_item(
    task: dict[str, Any],
    item_id: str,
    project_id: str,
    field_map: dict[str, dict],
    start_idx: int,
    remote_values: dict[str, Any],
) -> tuple[list[str], int]:
    mutations: list[str] = []
    idx = start_idx
    for field_name, task_key in _field_specs_for_item(task):
        raw = task.get(task_key)
        field = field_map.get(field_name)
        if not field or raw is None or raw == "":
            continue
        # Skip the write if the remote snapshot already matches.
        if _should_skip_field(field_name, raw, remote_values):
            print(f"  {task.get('id', '')} {field_name} already {raw!r} — skipped")
            continue
        gql = _build_field_value(field_map, field_name, raw)
        if gql is None:
            continue
        mutations.append(_mutation_for_field(project_id, item_id, field["id"], gql, idx))
        idx += 1
    return mutations, idx


def _collect_mutations(
    tasks: list[dict[str, Any]],
    items: list[dict],
    project_id: str,
    field_map: dict[str, dict],
    remote_by_item: dict[str, dict[str, Any]],
) -> list[str]:
    """Build GraphQL mutation aliases for all tasks with known project items.

    ``remote_by_item`` is the ``{item_id: {field_name: value}}`` map produced
    by :func:`_build_remote_values_map`; fields whose in-memory value already
    matches the remote snapshot are filtered out before a mutation is built.
    """
    mutations: list[str] = []
    idx = 0
    for t in tasks:
        item_id = find_item_id(items, t["issue_number"])
        if not item_id:
            print(
                f"  ⚠ Could not find item ID for #{t['issue_number']}, skipping fields",
                file=sys.stderr,
            )
            continue
        per_item_remote = remote_by_item.get(item_id, {})
        new_mutations, idx = _mutations_for_item(
            t, item_id, project_id, field_map, idx, per_item_remote
        )
        mutations.extend(new_mutations)
    return mutations


def _log_batch_errors(stdout: str) -> None:
    if not stdout:
        return
    try:
        resp = json.loads(stdout)
    except json.JSONDecodeError:
        return
    for err in resp.get("errors", []):
        print(f"    GraphQL error: {err.get('message', err)}", file=sys.stderr)


def _run_mutation_batch(batch: list[str], batch_num: int, batch_total: int) -> None:
    body = "mutation {\n  " + "\n  ".join(batch) + "\n}"
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={body}"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        print(
            f"  ⚠ Batch {batch_num}/{batch_total} failed: {result.stderr.strip()}",
            file=sys.stderr,
        )
        _log_batch_errors(result.stdout)
    else:
        print(f"  ✓ Batch {batch_num}/{batch_total} ({len(batch)} mutations)")


def execute_batched_mutations(mutations: list[str]) -> None:
    """Send mutations in batches using ``gh api graphql``."""
    total = len(mutations)
    if total == 0:
        print("  No field updates to send.")
        return
    print(f"  Sending {total} field updates in batches of {BATCH_SIZE}...")
    batch_total = (total + BATCH_SIZE - 1) // BATCH_SIZE
    for start in range(0, total, BATCH_SIZE):
        _run_mutation_batch(
            mutations[start : start + BATCH_SIZE],
            start // BATCH_SIZE + 1, batch_total,
        )


def create_branch_for_issue(repo: str, issue_num: int, branch_name: str) -> str | None:
    """Create a branch linked to an issue via ``gh issue develop``."""
    if not branch_name:
        return None
    run(
        [
            "gh", "issue", "develop", str(issue_num), "--repo", repo,
            "--name", branch_name, "--base", "main",
        ],
        check=False,
    )
    return branch_name


# ---------------------------------------------------------------------------
# Pass 2: field updates
# ---------------------------------------------------------------------------


def _log_pass2_progress(tasks: list[dict[str, Any]]) -> None:
    for t in tasks:
        status = t.get("status") or "no status"
        print(f"  ✓ {t['title']} [{status}]")


def run_pass2_batched(
    tasks: list[dict[str, Any]],
    items: list[dict],
    project_id: str,
    field_map: dict[str, dict],
    repo: str,
    remote_by_item: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Pass 2: batched GraphQL field updates for Status + Priority.

    The lean schema dropped milestone, dates, points and complexity, so
    Pass 2 collapses to a single GraphQL fan-out — no per-issue
    subprocesses, no parallel issue-level edits.

    Args:
        tasks (list[dict]): Story records carrying ``issue_number`` and
            the canonical field values.
        items (list[dict]): Items from ``gh project item-list`` used to
            resolve ``issue_number → project item id``.
        project_id (str): Project's GraphQL node id.
        field_map (dict[str, dict]): Output of :func:`build_field_map`.
        repo (str): ``owner/name`` slug (unused now; kept for caller
            signature compatibility).
        remote_by_item (dict | None): Optional remote snapshot used to
            skip fields whose in-memory value already matches.

    Returns:
        None: Side-effects only.

    SideEffect:
        Invokes ``gh api graphql`` in batches of ``BATCH_SIZE``.

    Example:
        >>> run_pass2_batched([], [], "PID", {}, "o/r")  # doctest: +SKIP
        Return: None
    """
    remote_by_item = remote_by_item or {}
    execute_batched_mutations(
        _collect_mutations(tasks, items, project_id, field_map, remote_by_item)
    )
    _log_pass2_progress(tasks)


# ---------------------------------------------------------------------------
# Delete workflow
# ---------------------------------------------------------------------------


def _close_issue(repo: str, issue_num: int) -> None:
    """Close a single issue."""
    run(["gh", "issue", "close", str(issue_num), "--repo", repo], check=False)


def _delete_issue(repo: str, issue_num: int) -> None:
    """Permanently delete an issue via GraphQL ``deleteIssue`` mutation."""
    node_id = _get_issue_node_id(repo, issue_num)
    if not node_id:
        print(f"  ⚠ Could not get node ID for #{issue_num}", file=sys.stderr)
        return
    mutation = f'mutation {{ deleteIssue(input: {{issueId: "{node_id}"}}) {{ clientMutationId }} }}'
    run(["gh", "api", "graphql", "-f", f"query={mutation}"], check=False)


def _delete_branch(repo: str, branch_name: str) -> None:
    """Delete a remote branch."""
    run(
        [
            "gh", "api", f"repos/{repo}/git/refs/heads/{branch_name}",
            "--method", "DELETE",
        ],
        check=False,
    )


def _remove_from_project(project_number: int, owner: str, item_id: str) -> None:
    """Remove an item from the project."""
    run(
        [
            "gh", "project", "item-delete", str(project_number),
            "--owner", owner, "--id", item_id,
        ],
        check=False,
    )


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


def _remove_issues_from_project(
    project_number: int, owner: str, issues: list[dict[str, Any]]
) -> None:
    print("\nRemoving from project (batched)...")
    project_id = get_project_id(project_number, owner)
    items = get_project_items(project_number, owner)
    item_ids = [find_item_id(items, iss["number"]) for iss in issues]
    item_ids = [iid for iid in item_ids if iid]
    if not item_ids:
        return
    for iss in issues:
        print(f"  ✗ #{iss['number']}")
    execute_batched_mutations(_remove_item_mutations(project_id, item_ids))


def _delete_issue_mutations(node_ids: dict[int, str]) -> list[str]:
    return [
        f"m{i}: deleteIssue(input: {{issueId: {json.dumps(nid)}}}) {{ clientMutationId }}"
        for i, nid in enumerate(node_ids.values())
    ]


def _delete_issues_batched(repo: str, issues: list[dict[str, Any]]) -> None:
    nums = {iss["number"] for iss in issues if iss.get("number")}
    node_ids = _fetch_node_ids(repo, nums)
    print(f"\nDeleting {len(issues)} issues permanently (batched)...")
    for iss in issues:
        print(f"  ✗ #{iss['number']}: {iss['title']}")
    execute_batched_mutations(_delete_issue_mutations(node_ids))


def _clear_issue_numbers(backlog_data: dict[str, Any], backlog_path: Path) -> None:
    # Every item is an issue now, so clear numbers on stories AND children.
    for story in backlog_data.get("stories", []):
        story["issue_number"] = None
        for task in story.get("tasks", []):
            task["issue_number"] = None
    backlog_path.write_text(json.dumps(backlog_data, indent=2), encoding="utf-8")
    print(f"\nCleared issue numbers from {backlog_path}")


# ---------------------------------------------------------------------------
# Sync workflow helpers
# ---------------------------------------------------------------------------


def _ensure_titles_present(items: list[dict], label: str) -> None:
    for t in items:
        if "title" not in t:
            raise ValueError(f"Item missing 'title': {t}")


def _pre_create_labels(items: list[dict], repo: str) -> None:
    """Ensure all labels exist before we fan out parallel issue creates."""
    unique: set[str] = set()
    for t in items:
        unique.update(_issue_labels(t))
    for lab in sorted(unique):
        ensure_label(lab, repo)


def _create_missing_in_parallel(items: list[dict], repo: str, label: str) -> None:
    print(f"\nPass 1b: Creating {len(items)} new {label} (parallel)...")
    _pre_create_labels(items, repo)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_create_issue, t, repo): t for t in items}
        for fut in as_completed(futures):
            t = futures[fut]
            num = fut.result()
            print(f"  + {t.get('id','')} {t['title']} -> #{num}")


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


def _add_to_project_mutations(
    project_id: str, node_ids: dict[int, str], items: list[dict]
) -> list[str]:
    mutations: list[str] = []
    idx = 0
    for t in items:
        cid = node_ids.get(t.get("issue_number"))
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
    nums = {t["issue_number"] for t in all_items if t.get("issue_number")}
    node_ids, existing_edges, existing_parents = _fetch_node_ids_and_edges(repo, nums)
    mutations = _add_to_project_mutations(project_id, node_ids, all_items)
    execute_batched_mutations(mutations)
    print(f"  ✓ {len(mutations)} items added/verified")
    return node_ids, existing_edges, existing_parents


def _writeback_numbers(
    stories: list[dict],
    tasks: list[dict],
    backlog_data: dict[str, Any],
    backlog_path: Path,
) -> None:
    save_flat_data(stories, tasks, backlog_path, backlog_data)
    print(f"\nUpdated: {backlog_path}")


# Project-side fields the sync expects: Status + Priority (single-select)
# and Start/Target date (native date fields, created if missing). "Target
# date" is a GitHub built-in; local ``end_date`` pushes to it.
_REQUIRED_FIELDS: list[tuple[str, str, list[str] | None]] = [
    ("Status", "SINGLE_SELECT", ["Backlog", "Ready", "In Progress", "Done"]),
    ("Priority", "SINGLE_SELECT", ["P0", "P1", "P2"]),
    ("Start date", "DATE", None),
    ("Target date", "DATE", None),
]

# Single-select options that must exist on an already-present field. `resolve`
# emits the "Ready" status, so the board's Status field needs that option even
# when the field predates this tool.
_REQUIRED_OPTIONS: list[tuple[str, str]] = [("Status", "Ready")]


def _print_sync_plan(
    items: list[dict], existing: dict[str, int], field_map: dict[str, dict]
) -> None:
    """Print what a real ``sync`` would create/update. No side effects.

    Args:
        items (list[dict]): Flattened stories + sub-issues.
        existing (dict[str, int]): ``{open issue title: number}`` from GitHub.
        field_map (dict[str, dict]): Output of :func:`build_field_map`.

    Returns:
        None: Prints only.

    Example:
        >>> _print_sync_plan([{"title": "X"}], {}, {})  # doctest: +SKIP
          Would create 1 new issue(s):
            + X
    """
    creates = [i for i in items if i.get("title") not in existing]
    print(f"  Would create {len(creates)} new issue(s):")
    for item in creates:
        print(f"    + {item.get('title')}")
    print(
        f"  Would update {len(items) - len(creates)} existing issue(s): "
        "bodies, labels, board fields, blocked_by, sub-issue links."
    )
    _print_board_plan(field_map)


def _print_board_plan(field_map: dict[str, dict]) -> None:
    """Report board fields/options a real ``sync`` would create. No side effects."""
    missing = [name for name, _, _ in _REQUIRED_FIELDS if name not in field_map]
    if missing:
        print(f"  Would create missing board field(s): {missing}")
    for fname, option in _REQUIRED_OPTIONS:
        field = field_map.get(fname)
        if field and option not in field.get("options", {}):
            print(f"  Would add '{option}' option to the {fname} field")


# ---------------------------------------------------------------------------
# pull: mirror GitHub state back into the backlog
# ---------------------------------------------------------------------------


# A fresh item minted from a GitHub issue that has no local match. Local-only
# fields stay empty / Backlog; GitHub-sourced fields are filled by the merge.
_PULLED_ITEM_BASE: dict[str, Any] = {
    "title": "", "description": "", "status": "Backlog", "priority": "",
    "goal": "", "notes": "", "start_date": "", "end_date": "",
    "acceptance_criteria": [], "labels": [], "blocked_by": [],
    "size": "", "points": None, "issue_number": None,
}

# Fields GitHub is authoritative for on pull (overwrite the local value).
_PULL_GITHUB_FIELDS = ("title", "description", "labels", "priority", "blocked_by")


def _invert_edges(edges: set[tuple[int, int]]) -> dict[int, list[int]]:
    """Invert ``{(blocked, blocker)}`` edges to ``{blocked: [blocker, ...]}``.

    Args:
        edges (set[tuple[int, int]]): ``(blocked_num, blocker_num)`` pairs.

    Returns:
        dict[int, list[int]]: Per-issue blocker lists (issue numbers).

    Example:
        >>> _invert_edges({(1, 2)})
        {1: [2]}
    """
    out: dict[int, list[int]] = {}
    for blocked, blocker in edges:
        out.setdefault(blocked, []).append(blocker)
    return out


def _body_to_description(body: str) -> str:
    """Return the issue body minus its ``## Acceptance Criteria`` section.

    AC stays local-authoritative, so the pulled description drops the AC
    checklist to avoid round-tripping it into ``description``.

    Args:
        body (str): Raw GitHub issue body.

    Returns:
        str: Stripped, trimmed description text.

    Example:
        >>> _body_to_description("Ctx.\\n\\n## Acceptance Criteria\\n\\n- [ ] x")
        'Ctx.'
    """
    idx = body.find("## Acceptance Criteria")
    return (body if idx == -1 else body[:idx]).strip()


def _pull_board_priority(board: list[dict]) -> dict[int, str]:
    """Build ``{issue_number: priority}`` from project board items."""
    out: dict[int, str] = {}
    for it in board:
        num = (it.get("content") or {}).get("number")
        pri = it.get("priority")
        if num and pri:
            out[num] = pri
    return out


def _assemble_pulled_issues(
    nums: set[int],
    details: dict[int, dict],
    priority: dict[int, str],
    blocked: dict[int, list[int]],
) -> dict[int, dict]:
    """Combine per-issue GitHub facts into the pull ``issues`` payload.

    Args:
        nums (set[int]): Issue numbers on the board.
        details (dict): ``{num: {title, body, labels, state}}``.
        priority (dict): ``{num: priority}`` from the board.
        blocked (dict): ``{num: [blocker_num, ...]}`` from inverted edges.

    Returns:
        dict[int, dict]: ``{num: {title, description, labels, priority,
        blocked_by}}``.

    Example:
        >>> _assemble_pulled_issues({1}, {1: {"title": "A", "body": ""}}, {}, {})
        {1: {'title': 'A', 'description': '', 'labels': [], 'priority': '', 'blocked_by': []}}
    """
    issues: dict[int, dict] = {}
    for num in nums:
        d = details.get(num, {})
        issues[num] = {
            "title": d.get("title", ""),
            "description": _body_to_description(d.get("body", "") or ""),
            "labels": d.get("labels", []),
            "priority": priority.get(num, ""),
            "blocked_by": sorted(blocked.get(num, [])),
        }
    return issues


def _build_issue_details_query(repo: str, nums: list[int]) -> str:
    """Build the batched GraphQL query for title/body/labels/state per issue."""
    owner, name = repo.split("/", 1)
    aliases = " ".join(
        f"i{n}: issue(number: {n}) {{ id number title body state "
        f"labels(first: 50) {{ nodes {{ name }} }} }}"
        for n in nums
    )
    return f'{{ repository(owner: "{owner}", name: "{name}") {{ {aliases} }} }}'


def _parse_issue_details(repo_data: dict) -> dict[int, dict]:
    """Extract ``{num: {title, body, labels, state}}`` from a GraphQL payload."""
    out: dict[int, dict] = {}
    for val in repo_data.values():
        if not (val and val.get("id")):
            continue
        out[val["number"]] = {
            "title": val.get("title", ""),
            "body": val.get("body", "") or "",
            "labels": [lab["name"] for lab in (val.get("labels") or {}).get("nodes") or []],
            "state": (val.get("state") or "").lower(),
        }
    return out


def _fetch_issue_details(repo: str, issue_nums: set[int]) -> dict[int, dict]:
    """Fetch title/body/labels/state for each issue in one GraphQL call."""
    nums = sorted(set(issue_nums))
    if not nums:
        return {}
    query = _build_issue_details_query(repo, nums)
    result = gh_json(["gh", "api", "graphql", "-f", f"query={query}"])
    repo_data = (result or {}).get("data", {}).get("repository") or {}
    return _parse_issue_details(repo_data)


def _index_one_local(item: dict, by_num: dict, by_title: dict) -> None:
    num = item.get("issue_number")
    if num is not None:
        by_num[num] = item
    title = item.get("title")
    if title:
        by_title.setdefault(title.lower(), item)


def _index_local_items(backlog_data: dict) -> tuple[dict[int, dict], dict[str, dict]]:
    """Index local items (stories + sub-issues) by number and lowercased title."""
    by_num: dict[int, dict] = {}
    by_title: dict[str, dict] = {}
    for story in backlog_data.get("stories", []):
        _index_one_local(story, by_num, by_title)
        for task in story.get("tasks", []):
            _index_one_local(task, by_num, by_title)
    return by_num, by_title


def _adopt_numbers(by_title: dict[str, dict], issues: dict[int, dict]) -> None:
    """Adopt a pulled issue's number onto a numberless local title match.

    SideEffect:
        Sets ``issue_number`` on matched numberless local items so the
        merge treats them as the same item (dedup by title).
    """
    for num, data in issues.items():
        local = by_title.get((data.get("title") or "").lower())
        if local is not None and local.get("issue_number") is None:
            local["issue_number"] = num


def _merge_github_fields(item: dict, data: dict) -> None:
    for field in _PULL_GITHUB_FIELDS:
        if field in data:
            item[field] = data[field]


def _build_pulled_item(num: int, data: dict) -> dict:
    item = json.loads(json.dumps(_PULLED_ITEM_BASE))
    item["issue_number"] = num
    _merge_github_fields(item, data)
    return item


def _merge_numbered_items(
    by_num: dict[int, dict], issues: dict[int, dict]
) -> dict[int, dict]:
    """Merge each pulled issue onto its local match (or mint a new item)."""
    merged: dict[int, dict] = {}
    for num, data in issues.items():
        local = by_num.get(num)
        if local is not None:
            _merge_github_fields(local, data)
            merged[num] = local
        else:
            merged[num] = _build_pulled_item(num, data)
    return merged


def _resolve_root(num: int, parents: dict[int, int], present: set[int]) -> int:
    """Walk parent links (capped) to the top-level ancestor in ``present``."""
    seen: set[int] = set()
    cur = num
    while cur in parents and parents[cur] in present and cur not in seen:
        seen.add(cur)
        cur = parents[cur]
    return cur


def _pull_order(backlog_data: dict, merged: dict[int, dict]) -> list[int]:
    """Order merged numbers: existing local order first, new issues appended."""
    order: list[int] = []
    seen: set[int] = set()
    for story in backlog_data.get("stories", []):
        for item in [story, *story.get("tasks", [])]:
            num = item.get("issue_number")
            if num in merged and num not in seen:
                order.append(num)
                seen.add(num)
    for num in sorted(merged):
        if num not in seen:
            order.append(num)
            seen.add(num)
    return order


def _as_leaf(item: dict) -> dict:
    item.pop("tasks", None)
    return item


def _assemble_story(merged: dict[int, dict], num: int, children: dict[int, list[int]]) -> dict:
    item = merged[num]
    item["tasks"] = [_as_leaf(merged[c]) for c in children.get(num, [])]
    return item


def _rebuild_pulled_tree(
    merged: dict[int, dict], parents: dict[int, int], order: list[int]
) -> list[dict]:
    """Rebuild the story tree from GitHub sub-issue links (one level deep)."""
    present = set(merged)
    roots: list[int] = []
    children: dict[int, list[int]] = {}
    for num in order:
        root = _resolve_root(num, parents, present)
        if root == num:
            roots.append(num)
        else:
            children.setdefault(root, []).append(num)
    return [_assemble_story(merged, num, children) for num in roots]


def _carry_unpulled_locals(
    backlog_data: dict, stories: list[dict], pulled_nums: set[int]
) -> list[dict]:
    """Append local stories absent from the board so unsynced work survives."""
    out = list(stories)
    for story in backlog_data.get("stories", []):
        if story.get("issue_number") not in pulled_nums:
            out.append(story)
    return out


def merge_pulled(backlog_data: dict, pulled: dict) -> dict:
    """Merge pulled GitHub state into the backlog (GitHub-wins where stated).

    GitHub wins per item for ``title/description/labels/priority/blocked_by``
    and the parent↔child structure; local ``status``, dates, ``goal``,
    ``notes``, ``size``, ``points``, ``acceptance_criteria`` and the root
    ``dates`` are preserved. New issues become stories (or sub-issues of a
    known parent); board-absent local stories are kept as-is.

    Args:
        backlog_data (dict): Current parsed backlog.
        pulled (dict): ``{"issues": {num: {...}}, "parents": {child: parent}}``.

    Returns:
        dict: New backlog dict with a rebuilt ``stories`` list.

    Example:
        >>> merge_pulled({"stories": []}, {"issues": {}, "parents": {}})["stories"]
        []
    """
    issues = pulled.get("issues", {})
    parents = pulled.get("parents", {})
    _, by_title = _index_local_items(backlog_data)
    _adopt_numbers(by_title, issues)
    by_num, _ = _index_local_items(backlog_data)
    merged = _merge_numbered_items(by_num, issues)
    stories = _rebuild_pulled_tree(merged, parents, _pull_order(backlog_data, merged))
    stories = _carry_unpulled_locals(backlog_data, stories, set(merged))
    result = dict(backlog_data)
    result["stories"] = stories
    return result


def _print_item_diff(num: int, old_item: dict | None, new_item: dict) -> None:
    if old_item is None:
        print(f"  + new #{num}: {new_item.get('title', '')}")
        return
    for field in _PULL_GITHUB_FIELDS:
        if old_item.get(field) != new_item.get(field):
            print(f"  ~ #{num} {field}: {old_item.get(field)!r} -> {new_item.get(field)!r}")


def print_pull_diff(old: dict, new: dict) -> None:
    """Print a per-item field diff of a pull (used by ``--dry-run``)."""
    old_by_num, _ = _index_local_items(old)
    new_by_num, _ = _index_local_items(new)
    for num, item in new_by_num.items():
        _print_item_diff(num, old_by_num.get(num), item)


# ---------------------------------------------------------------------------
# Syncer
# ---------------------------------------------------------------------------


class Syncer:
    """Orchestrates syncing stories JSON files to GitHub Projects."""

    _MODE_MAP: dict[str, str] = {
        "sync": "sync",
        "delete-all": "delete_all",
        "delete_all": "delete_all",
        "pull": "pull",
    }

    def __init__(
        self,
        *,
        backlog_path: Path | None = None,
        repo: str | None = None,
        project: int | None = None,
        owner: str | None = None,
    ) -> None:
        self.backlog_path = Path(backlog_path or DATA_PATHS["backlog"])
        self.repo = repo or REPO
        self.project = project or PROJECT_NUMBER
        self.owner = owner or OWNER

    def run(self, mode: str, **kwargs: Any) -> int:
        method_name = self._MODE_MAP.get(mode)
        if method_name is None:
            raise ValueError(f"Unknown sync mode: {mode}")
        # Reset the process-global title dedup set so a long-running
        # watcher doesn't carry forward claims from earlier syncs.
        _created_titles.clear()
        return getattr(self, method_name)(**kwargs)

    def sync(self, *, dry_run: bool = False) -> int:
        # Every item (story + sub-issue) is an issue, so all_items drives
        # creation, bodies, labels, board items + fields, and blocked_by.
        stories, tasks, _, backlog_data = load_flat_data(self.backlog_path)
        all_items = stories + tasks
        print(f"Sync mode: {len(stories)} stories, {len(tasks)} sub-issues")
        if dry_run:
            return self._sync_dry_run(all_items)
        project_id, field_map = self._fetch_project_metadata()
        changed = self._ensure_all_issues(all_items)
        self._refresh_issue_bodies(all_items)
        self._reconcile_labels(all_items)
        self._run_remote_passes(all_items, project_id, field_map, backlog_data)
        self._reconcile_sub_issues(stories)
        self._maybe_writeback(stories, tasks, backlog_data, changed, dry_run)
        return 0

    def _sync_dry_run(self, all_items: list[dict]) -> int:
        """Read-only ``sync`` preview: report planned writes, mutate nothing.

        Only read APIs run (the open-issue list and the project field-list);
        every create/edit/link/field/writeback pass is skipped, so the repo
        and the board are left untouched.

        Args:
            all_items (list[dict]): Flattened stories + sub-issues.

        Returns:
            int: ``0`` always.

        Example:
            >>> Syncer(backlog_path=p).sync(dry_run=True)  # doctest: +SKIP
            [dry-run] Read-only preview — no GitHub writes will be made.
              Would create 2 new issue(s): ...
            Return: 0
        """
        print("\n[dry-run] Read-only preview — no GitHub writes will be made.")
        existing = fetch_all_open_issues(self.repo)
        field_map = build_field_map(get_project_fields(self.project, self.owner))
        _print_sync_plan(all_items, existing, field_map)
        return 0

    def _refresh_issue_bodies(self, items: list[dict]) -> None:
        # Pass 1c: refresh remote issue bodies (description + AC) for every
        # item whose remote body drifted from the rebuilt body.
        print("\nPass 1c: Refreshing issue bodies...")
        update_issue_bodies(self.repo, items)

    def _reconcile_labels(self, items: list[dict]) -> None:
        # Pass 1d: add each item's labels to its existing issue (idempotent).
        print("\nPass 1d: Reconciling labels...")
        reconcile_labels(self.repo, items)

    def _reconcile_sub_issues(self, stories: list[dict]) -> None:
        # Pass 4: link each story's tasks as native sub-issues, detaching
        # any child no longer present in the backlog tree.
        print("\nPass 4: Reconciling sub-issue links...")
        reconcile_sub_issues(self.repo, stories)

    def _maybe_writeback(
        self,
        stories: list[dict],
        tasks: list[dict],
        backlog_data: dict,
        changed: bool,
        dry_run: bool,
    ) -> None:
        if not changed or dry_run:
            return
        _writeback_numbers(stories, tasks, backlog_data, self.backlog_path)

    def delete_all(self, *, dry_run: bool = False) -> int:
        stories, tasks, _, backlog_data = load_flat_data(self.backlog_path)
        print(f"Fetching issues currently in project {self.project}...")
        issues = _project_issues(self.project, self.owner)
        if not issues:
            print("No issues found in the project.")
            return 0
        print(f"Found {len(issues)} project issue(s) to delete.")
        if dry_run:
            _print_delete_dry_run(issues)
            return 0
        self._perform_delete(issues, backlog_data)
        return 0

    def _perform_delete(self, issues: list[dict], backlog_data: dict) -> None:
        _remove_issues_from_project(self.project, self.owner, issues)
        _delete_issues_batched(self.repo, issues)
        _clear_issue_numbers(backlog_data, self.backlog_path)

    def pull(self, *, dry_run: bool = False) -> int:
        """Mirror GitHub board + issue state back into ``backlog.json``.

        Args:
            dry_run (bool): Print a per-item diff and write nothing.

        Returns:
            int: 0.

        SideEffect:
            Rewrites ``backlog.json`` with the merged state unless
            ``dry_run``.

        Example:
            >>> Syncer(backlog_path=p).pull(dry_run=True)  # doctest: +SKIP
            Return: 0
        """
        backlog_data = json.loads(self.backlog_path.read_text(encoding="utf-8"))
        print(f"Pull mode: mirroring project {self.project} into backlog...")
        merged = merge_pulled(backlog_data, self._fetch_pull_state())
        if dry_run:
            print("\nPull dry-run (no writes):")
            print_pull_diff(backlog_data, merged)
            return 0
        self._save_pulled(merged)
        return 0

    def _fetch_pull_state(self) -> dict:
        board = get_project_items(self.project, self.owner)
        nums = {
            (it.get("content") or {}).get("number")
            for it in board if (it.get("content") or {}).get("number")
        }
        priority = _pull_board_priority(board)
        details = _fetch_issue_details(self.repo, nums)
        _, edges, parents = _fetch_node_ids_and_edges(self.repo, nums)
        issues = _assemble_pulled_issues(nums, details, priority, _invert_edges(edges))
        return {"issues": issues, "parents": parents}

    def _save_pulled(self, merged: dict) -> None:
        self.backlog_path.write_text(
            json.dumps(merged, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nPulled GitHub state into {self.backlog_path}")

    def _fetch_project_metadata(self) -> tuple[str, dict[str, dict]]:
        print("Fetching project metadata...")
        project_id = get_project_id(self.project, self.owner)
        fields = get_project_fields(self.project, self.owner)
        field_map = build_field_map(fields)
        print(f"  Project ID: {project_id}")
        print(f"  Fields: {list(field_map.keys())}")
        if self._ensure_required_fields(project_id, field_map):
            field_map = build_field_map(get_project_fields(self.project, self.owner))
            print(f"  Fields: {list(field_map.keys())}")
        return project_id, field_map

    def _ensure_required_fields(self, project_id: str, field_map: dict[str, dict]) -> bool:
        created = False
        for fname, ftype, foptions in _REQUIRED_FIELDS:
            if ensure_project_field(project_id, fname, ftype, field_map, foptions):
                created = True
        for fname, option in _REQUIRED_OPTIONS:
            if ensure_single_select_option(fname, option, field_map):
                created = True
        if created:
            print("  Re-fetching fields after creation...")
        return created

    def _ensure_all_issues(self, all_items: list[dict]) -> bool:
        print("\nFetching existing issues...")
        existing = fetch_all_open_issues(self.repo)
        print(f"  Found {len(existing)} open issues")
        return _resolve_or_create(all_items, existing, self.repo, "items")

    def _run_remote_passes(
        self,
        all_items: list[dict],
        project_id: str,
        field_map: dict[str, dict],
        backlog_data: dict,
    ) -> None:
        node_ids, existing_edges, _ = _add_all_to_project_batched(
            all_items, project_id, self.repo
        )
        items = self._fetch_project_items_for_pass2()
        remote_by_item = _build_remote_values_map(items)
        self._run_pass2(all_items, items, project_id, field_map, remote_by_item)
        print("\nPass 3: Setting blocking relationships...")
        set_blocking_relationships(
            self.repo, all_items,
            node_ids=node_ids, existing_edges=existing_edges,
        )

    def _fetch_project_items_for_pass2(self) -> list[dict]:
        print("\nFetching project items...")
        items = get_project_items(self.project, self.owner)
        print(f"  Found {len(items)} items in project")
        return items

    def _run_pass2(
        self,
        all_items: list[dict],
        items: list[dict],
        project_id: str,
        field_map: dict[str, dict],
        remote_by_item: dict[str, dict[str, Any]],
    ) -> None:
        print("\nPass 2: Setting project fields (batched GraphQL)...")
        run_pass2_batched(
            all_items, items, project_id, field_map, self.repo,
            remote_by_item=remote_by_item,
        )
