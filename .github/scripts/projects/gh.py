"""Shared ``gh`` / GraphQL client for the projects package.

The low-level client: process runner, JSON parser, batched GraphQL
mutations, node-id lookups, issue list/view, labels, plus the issue-body
refresh and ``blocked_by`` edges used by ``convert``. Keeping these here
(once) honors the package's DRY rule: shared gh helpers live in the client.

The body-refresh path rebuilds bodies with :func:`projects.backlog.build_issue_body`,
so this module imports the (pure) backlog module; the dependency is one-way.
"""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from projects import backlog

BATCH_SIZE = 30


# ── Process / JSON helpers ─────────────────────────────────────────────────


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


def issue_url(repo: str, number: int) -> str:
    return f"https://github.com/{repo}/issues/{number}"


# ── Labels ─────────────────────────────────────────────────────────────────


def ensure_label(label: str, repo: str) -> None:
    run(["gh", "label", "create", label, "--repo", repo, "--force"], check=False)


def add_labels(repo: str, issue_number: int, labels: list[str] | None) -> None:
    """Ensure each label exists, then add all of them to an existing issue.

    Used by ``convert`` to apply a story's groomed ``labels``; blank entries
    are dropped and an empty list is a no-op (no ``gh`` call).
    """
    clean = [str(lab) for lab in (labels or []) if str(lab).strip()]
    if not clean:
        return
    for lab in clean:
        ensure_label(lab, repo)
    cmd = ["gh", "issue", "edit", str(issue_number), "--repo", repo]
    for lab in clean:
        cmd += ["--add-label", lab]
    run(cmd, check=False)


# ── Issue list / view ──────────────────────────────────────────────────────


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
    """Fetch all open issues in one call. Returns ``{title: number}`` map."""
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


def _fetch_all_issues(repo: str, state: str = "all") -> list[dict[str, Any]]:
    """Fetch issues by state (open, closed, all). Returns list of ``{title, number}``."""
    if state == "all":
        return _gh_issue_list(repo, "open") + _gh_issue_list(repo, "closed")
    return _gh_issue_list(repo, state)


def gh_issue_view(repo: str, issue_number: int) -> dict[str, Any]:
    """Fetch a single issue's title/body/state/labels via ``gh issue view``."""
    out = run(
        [
            "gh", "issue", "view", str(issue_number), "--repo", repo,
            "--json", "number,title,body,state,labels",
        ],
        check=False,
    )
    return json.loads(out) if out else {}


# ── Node-id + blocker-edge lookups ─────────────────────────────────────────


def _get_issue_node_id(repo: str, issue_num: int) -> str | None:
    """Get the GraphQL node ID for an issue."""
    out = run(
        ["gh", "api", f"repos/{repo}/issues/{issue_num}", "--jq", ".node_id"],
        check=False,
    )
    return out if out else None


def _fetch_node_ids(repo: str, issue_nums: set[int]) -> dict[int, str]:
    """Batched node-ID lookup via a single GraphQL query."""
    ids, _, _ = _fetch_node_ids_and_edges(repo, issue_nums)
    return ids


def _fetch_node_ids_and_edges(
    repo: str, issue_nums: set[int]
) -> tuple[dict[int, str], set[tuple[int, int]], dict[int, int]]:
    """Fetch node IDs and existing blocker edges in one GraphQL call.

    Folding the lookups into a single query lets the blocking pass skip
    already-present pairs (``addBlockedBy`` isn't idempotent and rejects the
    whole batch with "Target issue has already been taken").

    Returns ``(num→node_id, {(blocked_num, blocker_num)}, {child_num: parent_num})``.
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


# ── Batched GraphQL mutations ──────────────────────────────────────────────


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


# ── Issue-body refresh (used by convert) ───────────────────────────────────


def _build_body_fetch_query(repo: str, nums: list[int]) -> str:
    """Build batched GraphQL query for ``id`` + ``body`` per issue."""
    owner, name = repo.split("/", 1)
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


def _fetch_issue_bodies(repo: str, issue_nums: set[int]) -> dict[int, tuple[str, str]]:
    """Fetch ``(node_id, body)`` for each issue in one GraphQL call.

    Empty input short-circuits so we never issue a wasted query.
    """
    nums = sorted(set(issue_nums))
    if not nums:
        return {}
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

    Stories without a known ``issue_number`` and stories whose remote body
    already matches the rebuild are both skipped, so an idempotent re-run
    emits zero mutations.
    """
    mutations: list[str] = []
    for story in stories:
        num = story.get("issue_number")
        if not num or num not in bodies:
            continue
        node_id, remote_body = bodies[num]
        new_body = backlog.build_issue_body(story)
        if new_body == remote_body:
            print(f"  {story.get('title', '')} body already current — skipped")
            continue
        mutations.append(_update_issue_body_mutation(node_id, new_body, len(mutations)))
        print(f"  {story.get('title', '')} body needs refresh -> #{num}")
    return mutations


def update_issue_bodies(repo: str, stories: list[dict[str, Any]]) -> None:
    """Refresh GitHub issue bodies for every story with an ``issue_number``.

    Diffs each story's rebuilt body against the remote snapshot; only stories
    that drifted get an ``updateIssue`` mutation, so the no-op re-run is cheap.
    """
    nums = {s["issue_number"] for s in stories if s.get("issue_number")}
    if not nums:
        return
    bodies = _fetch_issue_bodies(repo, nums)
    execute_batched_mutations(_collect_body_update_mutations(stories, bodies))


# ── Blocking relationships (used by convert) ───────────────────────────────


def _collect_blocking_pairs(
    items: list[dict],
) -> tuple[list[tuple[int, int]], set[int]]:
    """Collect ``(blocked_num, blocker_num)`` pairs straight from ``blocked_by``.

    Each ``blocked_by`` entry is already the blocker's issue number, so no
    lookup table is needed — pairs are read directly from items that have an
    ``issue_number``.
    """
    pairs: list[tuple[int, int]] = []
    involved: set[int] = set()
    for item in items:
        item_num = item.get("issue_number")
        if not item_num:
            continue
        for blocker_num in item.get("blocked_by", []):
            if blocker_num:
                pairs.append((item_num, blocker_num))
                involved.update({item_num, blocker_num})
    return pairs, involved


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
    """Set blocking relationships via batched ``addBlockedBy`` mutations."""
    pairs, involved = _collect_blocking_pairs(items)
    if not pairs:
        print("  No blocking relationships to set.")
        return
    if node_ids is None or existing_edges is None:
        print(f"  Fetching node IDs + existing edges for {len(involved)} issues...")
        node_ids, existing_edges, _ = _fetch_node_ids_and_edges(repo, involved)
    execute_batched_mutations(_blocking_mutations(node_ids, pairs, existing_edges))


# ── Issue deletion primitives ──────────────────────────────────────────────


def delete_issue(repo: str, issue_num: int) -> None:
    """Permanently delete an issue via GraphQL ``deleteIssue`` mutation."""
    node_id = _get_issue_node_id(repo, issue_num)
    if not node_id:
        print(f"  ⚠ Could not get node ID for #{issue_num}", file=sys.stderr)
        return
    mutation = f'mutation {{ deleteIssue(input: {{issueId: "{node_id}"}}) {{ clientMutationId }} }}'
    run(["gh", "api", "graphql", "-f", f"query={mutation}"], check=False)


def delete_issue_mutations(node_ids: dict[int, str]) -> list[str]:
    """Build batched ``deleteIssue`` mutation aliases for many node ids."""
    return [
        f"m{i}: deleteIssue(input: {{issueId: {json.dumps(nid)}}}) {{ clientMutationId }}"
        for i, nid in enumerate(node_ids.values())
    ]
