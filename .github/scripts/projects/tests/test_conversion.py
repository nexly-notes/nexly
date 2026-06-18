"""Tests for projects.conversion — the convert workflow. Mocks gh/board."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from projects import board, conversion
from projects.config import Identity


@pytest.fixture(autouse=True)
def clear_created_titles():
    conversion._created_titles.clear()


_IDENT = Identity(repo="org/repo", project=1, owner="me")

_FIELD_MAP = {
    "Status": {"id": "FS", "options": {"Backlog": "OS_B", "In Progress": "OS_IP", "Done": "OS_D"}},
    "Priority": {"id": "FP", "options": {"P0": "OP0", "P1": "OP1", "P2": "OP2"}},
    "Size": {"id": "FSZ", "options": {"XS": "Z0", "S": "Z1", "M": "Z2", "L": "Z3", "XL": "Z4"}},
    "Points": {"id": "FPT", "type": "NUMBER"},
}


# ── Labels / resolution ────────────────────────────────────────────────────


class TestIssueLabels:
    def test_reads_labels_field(self):
        assert conversion._issue_labels({"labels": ["tech", "backend"]}) == ["tech", "backend"]

    def test_no_labels(self):
        assert conversion._issue_labels({}) == []

    def test_filters_blank(self):
        assert conversion._issue_labels({"labels": ["tech", "", "  "]}) == ["tech"]


class TestResolveExistingIssues:
    def test_live_issue_number_kept(self):
        stories = [{"title": "X", "issue_number": 42}]
        assert conversion.resolve_existing_issues(stories, {"X": 42}) == []
        assert stories[0]["issue_number"] == 42

    def test_stale_issue_number_dropped(self):
        stories = [{"title": "X", "issue_number": 999}]
        assert conversion.resolve_existing_issues(stories, {}) == stories
        assert "issue_number" not in stories[0]

    def test_matches_existing_by_title(self):
        stories = [{"title": "X"}]
        assert conversion.resolve_existing_issues(stories, {"X": 99}) == []
        assert stories[0]["issue_number"] == 99

    def test_needs_creation(self):
        stories = [{"title": "New"}]
        assert conversion.resolve_existing_issues(stories, {}) == stories


# ── Field pass ─────────────────────────────────────────────────────────────


class TestFieldSpecs:
    def test_field_specs_for_item(self):
        assert conversion._field_specs_for_item({}) == [
            ("Status", "status"), ("Priority", "priority"),
            ("Size", "size"), ("Points", "points"),
        ]


class TestCollectMutations:
    _ITEMS = [{"id": "ITEM-1", "content": {"number": 1}}]

    def test_emits_status_and_priority(self):
        story = {"title": "X", "issue_number": 1, "status": "In Progress", "priority": "P0"}
        mutations = conversion._collect_mutations([story], self._ITEMS, "PID", _FIELD_MAP, {})
        assert len(mutations) == 2
        flat = " ".join(mutations)
        assert "FS" in flat and "FP" in flat

    def test_emits_size_and_points(self):
        # The field pass now also syncs Size + Points from the groomed story.
        story = {"title": "X", "issue_number": 1, "size": "M", "points": 5}
        mutations = conversion._collect_mutations([story], self._ITEMS, "PID", _FIELD_MAP, {})
        assert len(mutations) == 2
        flat = " ".join(mutations)
        assert "FSZ" in flat and "FPT" in flat

    def test_emits_all_four_fields(self):
        story = {"title": "X", "issue_number": 1, "status": "Done",
                 "priority": "P0", "size": "L", "points": 8}
        mutations = conversion._collect_mutations([story], self._ITEMS, "PID", _FIELD_MAP, {})
        assert len(mutations) == 4

    def test_empty(self):
        assert conversion._collect_mutations([], [], "PID", {}, {}) == []

    def test_skips_field_when_value_unchanged(self):
        story = {"title": "X", "issue_number": 1, "status": "In Progress"}
        remote = {"ITEM-1": {"Status": "In Progress"}}
        assert conversion._collect_mutations([story], self._ITEMS, "PID", _FIELD_MAP, remote) == []

    def test_emits_when_status_changes(self):
        story = {"title": "X", "issue_number": 1, "status": "In Progress"}
        remote = {"ITEM-1": {"Status": "Backlog"}}
        mutations = conversion._collect_mutations([story], self._ITEMS, "PID", _FIELD_MAP, remote)
        assert len(mutations) == 1 and "FS" in mutations[0]


class TestRunPass2Batched:
    def _item(self, item_id, num):
        return {"id": item_id, "content": {"number": num}, "status": "In Progress", "priority": "P0"}

    def _story(self, sid, num):
        return {"issue_number": num, "status": "In Progress", "priority": "P0", "title": sid}

    @patch.object(conversion.gh, "execute_batched_mutations")
    def test_no_mutations_when_all_match(self, mock_exec):
        # issue numbers start at 1 (0 is the "not converted" placeholder).
        items = [self._item(f"ITEM-{i}", i) for i in range(1, 4)]
        stories = [self._story(f"NEXLY-{i:03d}", i) for i in range(1, 4)]
        remote = board.build_remote_values_map(items)
        conversion.run_pass2_batched(stories, items, "PID", _FIELD_MAP, "o/r", remote_by_item=remote)
        assert mock_exec.call_args[0][0] == []

    @patch.object(conversion.gh, "execute_batched_mutations")
    def test_one_mutation_when_single_status_differs(self, mock_exec):
        items = [self._item(f"ITEM-{i}", i) for i in range(1, 4)]
        items[0]["status"] = "Backlog"
        stories = [self._story(f"NEXLY-{i:03d}", i) for i in range(1, 4)]
        remote = board.build_remote_values_map(items)
        conversion.run_pass2_batched(stories, items, "PID", _FIELD_MAP, "o/r", remote_by_item=remote)
        mutations = mock_exec.call_args[0][0]
        assert len(mutations) == 1 and "FS" in mutations[0]

    @patch.object(conversion.gh, "execute_batched_mutations")
    def test_story_without_issue_number_is_skipped(self, mock_exec):
        # issue_number 0/absent (un-converted) must not raise or mutate.
        stories = [{"title": "A", "status": "Done"}, {"title": "B", "issue_number": 0, "status": "Done"}]
        conversion.run_pass2_batched(stories, [], "PID", _FIELD_MAP, "o/r", remote_by_item={})
        assert mock_exec.call_args[0][0] == []


# ── _create_issue / ensure_issue ───────────────────────────────────────────


class TestCreateIssue:
    @patch.object(conversion.gh, "run", return_value="https://github.com/org/repo/issues/5")
    @patch.object(conversion.gh, "ensure_label")
    def test_returns_number(self, mock_label, mock_run):
        story = {"title": "New", "labels": ["spike"]}
        assert conversion._create_issue(story, "org/repo") == 5
        assert story["issue_number"] == 5

    @patch.object(conversion.gh, "run", return_value="https://github.com/org/repo/issues/1")
    @patch.object(conversion.gh, "ensure_label")
    def test_applies_labels(self, mock_label, mock_run):
        conversion._create_issue({"title": "X", "labels": ["feature", "backend"]}, "org/repo")
        cmd = mock_run.call_args[0][0]
        assert "feature" in cmd and "backend" in cmd

    @patch.object(conversion.gh, "run", return_value="https://github.com/org/repo/issues/1")
    @patch.object(conversion.gh, "ensure_label")
    def test_dedup_guard(self, mock_label, mock_run):
        conversion._create_issue({"title": "X"}, "org/repo")
        with pytest.raises(RuntimeError, match="Duplicate"):
            conversion._create_issue({"title": "X"}, "org/repo")

    @patch.object(conversion.gh, "run", return_value="")
    @patch.object(conversion.gh, "ensure_label")
    def test_raises_on_empty_url(self, mock_label, mock_run):
        with pytest.raises(RuntimeError, match="returned no URL"):
            conversion._create_issue({"title": "X"}, "org/repo")


class TestEnsureIssue:
    def test_returns_existing_number(self):
        assert conversion.ensure_issue({"title": "X", "issue_number": 5}, "org/repo") == 5

    def test_uses_cache(self):
        assert conversion.ensure_issue({"title": "X"}, "org/repo", {"X": 10}) == 10

    @patch.object(conversion.gh, "find_existing_issue", return_value=20)
    def test_fallback_search(self, mock_find):
        assert conversion.ensure_issue({"title": "X"}, "org/repo", {}) == 20

    @patch.object(conversion.gh, "find_existing_issue", return_value=None)
    @patch.object(conversion, "_create_issue", return_value=30)
    def test_creates_if_not_found(self, mock_create, mock_find):
        assert conversion.ensure_issue({"title": "X"}, "org/repo", {}) == 30


# ── labels pass ────────────────────────────────────────────────────────────


class TestApplyLabels:
    @patch.object(conversion.gh, "add_labels")
    def test_applies_when_labels_and_number(self, mock_add):
        conversion._apply_labels([{"issue_number": 5, "labels": ["feature"]}], "o/r")
        mock_add.assert_called_once_with("o/r", 5, ["feature"])

    @patch.object(conversion.gh, "add_labels")
    def test_skips_when_no_labels(self, mock_add):
        conversion._apply_labels([{"issue_number": 5}], "o/r")
        mock_add.assert_not_called()

    @patch.object(conversion.gh, "add_labels")
    def test_skips_when_no_number(self, mock_add):
        conversion._apply_labels([{"labels": ["feature"]}], "o/r")
        mock_add.assert_not_called()


# ── remote passes (labels + fields + blocking wiring) ──────────────────────


class TestRunRemotePasses:
    @patch.object(conversion.gh, "set_blocking_relationships")
    @patch.object(conversion, "run_pass2_batched")
    @patch.object(conversion, "_await_project_items", return_value=[])
    @patch.object(conversion, "_add_all_to_project_batched", return_value=({}, set(), {}))
    @patch.object(conversion, "_apply_labels")
    def test_applies_labels_and_sets_blocking(
        self, mock_labels, mock_add, mock_await, mock_pass2, mock_block
    ):
        stories = [
            {"title": "A", "issue_number": 5, "labels": ["feature"], "blocked_by": []},
            {"title": "B", "issue_number": 6, "labels": ["tech"], "blocked_by": [5]},
        ]
        conversion._run_remote_passes(stories, "PID", _FIELD_MAP, _IDENT)
        mock_labels.assert_called_once_with(stories, _IDENT.repo)
        mock_pass2.assert_called_once()
        mock_block.assert_called_once()
        # blocking is set straight from numeric blocked_by — no id map is threaded.
        assert mock_block.call_args[0][1] == stories
        assert "id_map" not in mock_block.call_args[1]


# ── convert orchestration / dry-run ────────────────────────────────────────


_BACKLOG = {
    "project": "P", "description": "d",
    "dates": {"start": "2026-02-17", "end": "2026-03-16"},
    "stories": [{"title": "X", "description": "d", "status": "Backlog",
                 "priority": "P0", "issue_number": 0}],
}


@pytest.fixture
def backlog_file(tmp_path):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(_BACKLOG), encoding="utf-8")
    return p


class TestAwaitProjectItems:
    _ITEMS = [{"id": "I4", "content": {"number": 4}}, {"id": "I5", "content": {"number": 5}}]

    @patch.object(conversion.board, "get_project_items")
    @patch.object(conversion.time, "sleep")
    def test_returns_immediately_when_present(self, mock_sleep, mock_items):
        mock_items.return_value = self._ITEMS
        out = conversion._await_project_items(_IDENT, {4, 5})
        assert len(out) == 2
        mock_sleep.assert_not_called()

    @patch.object(conversion.board, "get_project_items")
    @patch.object(conversion.time, "sleep")
    def test_polls_until_items_propagate(self, mock_sleep, mock_items):
        # first read empty (lag), second read has the items.
        mock_items.side_effect = [[], self._ITEMS]
        out = conversion._await_project_items(_IDENT, {4, 5}, attempts=3, delay=0)
        assert len(out) == 2
        assert mock_sleep.call_count == 1

    @patch.object(conversion.board, "get_project_items", return_value=[])
    @patch.object(conversion.time, "sleep")
    def test_gives_up_after_attempts(self, mock_sleep, mock_items):
        out = conversion._await_project_items(_IDENT, {4, 5}, attempts=3, delay=0)
        assert out == []
        assert mock_items.call_count == 3

    @patch.object(conversion.board, "get_project_items", return_value=[])
    @patch.object(conversion.time, "sleep")
    def test_no_expected_skips_polling(self, mock_sleep, mock_items):
        conversion._await_project_items(_IDENT, set())
        mock_items.assert_called_once()
        mock_sleep.assert_not_called()


class TestConvert:
    @patch.object(conversion, "_run_remote_passes")
    @patch.object(conversion, "_refresh_issue_bodies")
    @patch.object(conversion, "_fetch_project_metadata", return_value=("PID", {}))
    @patch.object(conversion, "_writeback_numbers")
    def test_dry_run_skips_writeback(self, mock_wb, mock_meta, mock_bodies, mock_passes, backlog_file):
        with patch.object(conversion, "_ensure_all_issues", return_value=True):
            assert conversion.convert(_IDENT, backlog_file, dry_run=True) == 0
        mock_wb.assert_not_called()

    @patch.object(conversion, "_run_remote_passes")
    @patch.object(conversion, "_refresh_issue_bodies")
    @patch.object(conversion, "_fetch_project_metadata", return_value=("PID", {}))
    @patch.object(conversion, "_writeback_numbers")
    def test_writeback_when_changed_and_not_dry(self, mock_wb, mock_meta, mock_bodies, mock_passes, backlog_file):
        with patch.object(conversion, "_ensure_all_issues", return_value=True):
            assert conversion.convert(_IDENT, backlog_file, dry_run=False) == 0
        mock_wb.assert_called_once()

    @patch.object(conversion, "_run_remote_passes")
    @patch.object(conversion, "_refresh_issue_bodies")
    @patch.object(conversion, "_fetch_project_metadata", return_value=("PID", {}))
    @patch.object(conversion, "_writeback_numbers")
    def test_no_writeback_when_unchanged(self, mock_wb, mock_meta, mock_bodies, mock_passes, backlog_file):
        with patch.object(conversion, "_ensure_all_issues", return_value=False):
            conversion.convert(_IDENT, backlog_file, dry_run=False)
        mock_wb.assert_not_called()
