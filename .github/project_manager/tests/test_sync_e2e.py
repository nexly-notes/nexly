"""Live end-to-end tests for project_manager.sync.Syncer.

These hit real GitHub and **destructively** wipe all issues in the
configured project before each run. They are gated behind the ``e2e``
pytest marker — run with ``pytest -m e2e``.

Unified-item schema: every item (story OR sub-issue) becomes a real
issue + project-board item. ``pull`` mirrors GitHub state back.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from project_manager import Syncer
from project_manager import sync as sp

_E2E_MARKER = "[E2E]"


def _cleanup_orphan_e2e_issues(repo: str) -> None:
    """Batched delete of any [E2E]-marked issues outside the project."""
    orphans = [
        i for i in sp._fetch_all_issues(repo, "all")
        if _E2E_MARKER in i.get("title", "")
    ]
    if not orphans:
        return
    node_ids = sp._fetch_node_ids(repo, [i["number"] for i in orphans])
    sp.execute_batched_mutations(sp._delete_issue_mutations(node_ids))


def _gh_authenticated() -> bool:
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=10)
        return r.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


_requires_gh = pytest.mark.skipif(
    not _gh_authenticated(),
    reason="requires `gh` CLI authenticated to GitHub",
)


# ---------------------------------------------------------------------------
# Sample backlog — unified items (sub-issues are full items)
# ---------------------------------------------------------------------------


def _child(title, *, status="Backlog", priority="P2"):
    return {
        "title": title, "description": f"{title} desc",
        "status": status, "priority": priority,
        "goal": "", "notes": "", "start_date": "", "end_date": "",
        "acceptance_criteria": [], "labels": [], "blocked_by": [],
        "size": "", "points": None, "issue_number": None,
    }


_SAMPLE_BACKLOG: dict = {
    "project": "E2E Test",
    "description": "End-to-end smoke test for Syncer",
    "dates": {"start": "2026-04-17", "end": "2026-04-24"},
    "stories": [
        {
            "title": "[E2E] Research topic",
            "description": "Investigate.", "status": "In Progress", "priority": "P0",
            "goal": "g", "notes": "n",
            "start_date": "2026-04-17", "end_date": "2026-04-20",
            "acceptance_criteria": ["criterion 1", "criterion 2"],
            "labels": ["spike"], "blocked_by": [], "size": "M", "points": 3,
            "issue_number": None,
            "tasks": [
                _child("[E2E] Task A1"),
                _child("[E2E] Task A2", status="Done"),
            ],
        },
        {
            "title": "[E2E] Infrastructure setup",
            "description": "Bootstrap.", "status": "Backlog", "priority": "P1",
            "goal": "", "notes": "", "start_date": "", "end_date": "",
            "acceptance_criteria": [], "labels": ["infra"], "blocked_by": [],
            "size": "", "points": None, "issue_number": None,
            "tasks": [
                _child("[E2E] Task B1"),
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_created_titles():
    sp._created_titles.clear()
    yield
    sp._created_titles.clear()


@pytest.fixture
def backlog_path(tmp_path: Path) -> Path:
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(_SAMPLE_BACKLOG, indent=2), encoding="utf-8")
    return p


@pytest.fixture
def syncer(backlog_path: Path):
    """Yield a Syncer with the GitHub project pre-wiped + orphans cleared."""
    s = Syncer(backlog_path=backlog_path)
    s.run("delete-all")
    _cleanup_orphan_e2e_issues(s.repo)
    yield s
    s.run("delete-all")
    _cleanup_orphan_e2e_issues(s.repo)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_items(backlog_data: dict) -> list[dict]:
    items: list[dict] = []
    for story in backlog_data.get("stories", []):
        items.append(story)
        items.extend(story.get("tasks", []))
    return items


def _every_item_numbered(backlog_data: dict) -> bool:
    return all(it.get("issue_number") for it in _all_items(backlog_data))


def _no_issue_numbers(backlog_data: dict) -> bool:
    return all(it.get("issue_number") is None for it in _all_items(backlog_data))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@_requires_gh
class TestSyncerE2E:
    def test_sync_numbers_every_item_with_board_items(
        self, syncer: Syncer, backlog_path: Path
    ) -> None:
        assert syncer.run("sync") == 0
        data = json.loads(backlog_path.read_text(encoding="utf-8"))
        assert _every_item_numbered(data), (
            f"Every story AND sub-issue must get an issue_number; got: {data}"
        )
        project_issues = sp._project_issues(syncer.project, syncer.owner)
        # 2 stories + 3 sub-issues = 5 board items.
        assert len(project_issues) == 5, (
            f"Expected 5 project items (stories + sub-issues); found "
            f"{len(project_issues)}: {[iss['title'] for iss in project_issues]}"
        )

    def test_second_sync_is_idempotent(
        self, syncer: Syncer, backlog_path: Path
    ) -> None:
        assert syncer.run("sync") == 0
        first = json.loads(backlog_path.read_text(encoding="utf-8"))
        first_nums = sorted(it["issue_number"] for it in _all_items(first))
        assert syncer.run("sync") == 0
        second = json.loads(backlog_path.read_text(encoding="utf-8"))
        second_nums = sorted(it["issue_number"] for it in _all_items(second))
        assert first_nums == second_nums, "re-sync must not re-create issues"

    def test_pull_round_trips_and_preserves_local(
        self, syncer: Syncer, backlog_path: Path
    ) -> None:
        syncer.run("sync")
        assert syncer.run("pull") == 0
        data = json.loads(backlog_path.read_text(encoding="utf-8"))
        research = data["stories"][0]
        # Local-authoritative fields survive the pull.
        assert research["status"] == "In Progress"
        assert research["start_date"] == "2026-04-17"
        assert research["acceptance_criteria"] == ["criterion 1", "criterion 2"]
        assert data["dates"]["start"] == "2026-04-17"
        # Sub-issue structure survives the pull.
        assert len(research["tasks"]) == 2

    def test_delete_all_clears_issue_numbers(
        self, syncer: Syncer, backlog_path: Path
    ) -> None:
        syncer.run("sync")
        mid = json.loads(backlog_path.read_text(encoding="utf-8"))
        assert _every_item_numbered(mid), "sync should assign issue_numbers"
        assert syncer.run("delete-all") == 0
        after = json.loads(backlog_path.read_text(encoding="utf-8"))
        assert _no_issue_numbers(after), (
            f"delete-all should clear issue_numbers; got: {after}"
        )

    def test_dry_run_is_read_only(
        self, syncer: Syncer, backlog_path: Path
    ) -> None:
        # Project is pre-wiped by the fixture, so a read-only dry-run must
        # leave it empty AND must not write issue_numbers back to disk.
        assert syncer.run("sync", dry_run=True) == 0
        created = sp._project_issues(syncer.project, syncer.owner)
        assert created == [], (
            f"dry-run must not create project issues; got: {created}"
        )
        data = json.loads(backlog_path.read_text(encoding="utf-8"))
        assert _no_issue_numbers(data), (
            f"dry-run must not write issue_numbers back to disk; got: {data}"
        )
