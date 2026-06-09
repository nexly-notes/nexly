"""Live end-to-end test: convert → re-convert with deps → delete-all.

Hits real GitHub and **destructively** wipes all issues in the configured
project. Gated twice — by the ``e2e`` marker (``pytest -m e2e``) *and* by the
``RUN_LIVE_TESTS=1`` env flag — so it never runs in a normal suite or CI.

``convert`` is the single push for the backlog. Because ``blocked_by`` is keyed
by issue number — which doesn't exist until the first convert mints it — this
test exercises the **two-pass** flow: convert to mint numbers, author
``blocked_by`` by number, then re-convert to set the edge. It asserts the issue
bodies, labels, ``Size`` / ``Points`` board fields, and the ``blocked_by`` edge.

    RUN_LIVE_TESTS=1 python3 -m pytest projects/tests/test_e2e.py -m e2e -q
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from projects import conversion, gh, state
from projects.config import resolve_identity

_E2E_MARKER = "[E2E]"
_RUN_LIVE = os.environ.get("RUN_LIVE_TESTS") == "1"


def _gh_authenticated() -> bool:
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(not _RUN_LIVE, reason="set RUN_LIVE_TESTS=1 to run live e2e"),
    pytest.mark.skipif(not _gh_authenticated(), reason="requires authenticated `gh` CLI"),
]


# A groomed two-story backlog. Both start with no dependency — the blocked_by
# edge (story B blocked by story A) is authored by issue number after the first
# convert mints the numbers, then set by a second convert (the two-pass flow).
_BACKLOG: dict = {
    "project": "E2E Test",
    "description": "End-to-end smoke test for the projects package",
    "dates": {"start": "2026-04-17", "end": "2026-04-24"},
    "stories": [
        {
            "title": "[E2E] Research topic",
            "description": "Smoke-test story A.",
            "status": "Backlog",
            "priority": "P0",
            "goal": "Validate A.",
            "notes": "Edge cases.",
            "tasks": ["[E2E] task 1", "[E2E] task 2"],
            "acceptance_criteria": ["[E2E] criterion 1"],
            "labels": ["spike"],
            "blocked_by": [],
            "size": "M",
            "points": 3,
            "issue_number": 0,
        },
        {
            "title": "[E2E] Infrastructure setup",
            "description": "Smoke-test story B.",
            "status": "Backlog",
            "priority": "P1",
            "goal": "Validate B.",
            "notes": "",
            "tasks": ["[E2E] task 1"],
            "acceptance_criteria": ["[E2E] criterion 2"],
            "labels": ["tech"],
            "blocked_by": [],
            "size": "L",
            "points": 5,
            "issue_number": 0,
        },
    ],
}


def _cleanup_orphans(repo: str) -> None:
    orphans = [i for i in gh._fetch_all_issues(repo, "all") if _E2E_MARKER in i.get("title", "")]
    if not orphans:
        return
    node_ids = gh._fetch_node_ids(repo, {i["number"] for i in orphans})
    gh.execute_batched_mutations(gh.delete_issue_mutations(node_ids))


@pytest.fixture
def backlog_path(tmp_path: Path) -> Path:
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(_BACKLOG, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def identity(backlog_path):
    ident = resolve_identity()
    state.delete_all(ident, backlog_path)
    _cleanup_orphans(ident.repo)
    yield ident
    state.delete_all(ident, backlog_path)
    _cleanup_orphans(ident.repo)


_STORY_A = "[E2E] Research topic"
_STORY_B = "[E2E] Infrastructure setup"


def test_convert_pushes_groomed_backlog(identity, backlog_path):
    # Pass 1: convert the groomed backlog -> issues + board, numbers written back.
    assert conversion.convert(identity, backlog_path) == 0
    data = json.loads(backlog_path.read_text(encoding="utf-8"))
    assert all(s.get("issue_number") for s in data["stories"]), data
    issues = state._project_issues(identity)
    assert len(issues) == 2
    num_by_title = {s["title"]: s["issue_number"] for s in data["stories"]}

    # the issue body carries the groomed acceptance criteria.
    view = gh.gh_issue_view(identity.repo, num_by_title[_STORY_A])
    assert "## Acceptance Criteria" in (view.get("body") or "")

    # labels were applied to the issue.
    labels = {lab.get("name") for lab in view.get("labels", [])}
    assert "spike" in labels

    # the board carries Size + Points for the story.
    fields = state._project_field_values(identity, num_by_title[_STORY_A])
    assert fields.get("Size") == "M"
    assert fields.get("Points") == 3

    # Pass 2: author blocked_by by the now-known issue number, then re-convert.
    for s in data["stories"]:
        if s["title"] == _STORY_B:
            s["blocked_by"] = [num_by_title[_STORY_A]]
    backlog_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    assert conversion.convert(identity, backlog_path) == 0

    # blocked_by edge: story B is blocked by story A.
    _, edges, _ = gh._fetch_node_ids_and_edges(identity.repo, set(num_by_title.values()))
    assert (num_by_title[_STORY_B], num_by_title[_STORY_A]) in edges

    # delete-all clears every issue_number back out of the backlog.
    assert state.delete_all(identity, backlog_path) == 0
    after = json.loads(backlog_path.read_text(encoding="utf-8"))
    assert all("issue_number" not in s for s in after["stories"]), after
