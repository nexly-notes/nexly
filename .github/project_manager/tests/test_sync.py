"""Tests for project_manager.sync — pure logic, no live API calls.

Unified-item schema: every item (story OR sub-issue) is a GitHub issue
with its own board item + fields. Identity is the bare ``title``;
``blocked_by`` holds issue numbers; ``labels`` are item-supplied; dates
push to native board date fields.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from project_manager import sync as sp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_created_titles():
    sp._created_titles.clear()


def _child(title, *, issue_number=None, status="Backlog", priority="",
           blocked_by=None, labels=None, start_date="", end_date="",
           acceptance_criteria=None):
    return {
        "title": title, "description": f"{title} desc",
        "status": status, "priority": priority,
        "goal": "", "notes": "", "start_date": start_date, "end_date": end_date,
        "acceptance_criteria": list(acceptance_criteria or []),
        "labels": list(labels or []), "blocked_by": list(blocked_by or []),
        "size": "", "points": None, "issue_number": issue_number,
    }


SAMPLE_BACKLOG = {
    "project": "TestProject",
    "description": "Build foundation",
    "dates": {"start": "2026-02-17", "end": "2026-03-02"},
    "stories": [
        {
            "title": "Research features", "description": "Investigate.",
            "status": "In Progress", "priority": "P0",
            "goal": "", "notes": "",
            "start_date": "2026-02-17", "end_date": "2026-02-20",
            "acceptance_criteria": ["AC1 done", "AC2 done"],
            "labels": ["spike"], "blocked_by": [], "size": "M", "points": 3,
            "issue_number": 101,
            "tasks": [
                _child("Analyze features", issue_number=201),
                _child("Document findings", issue_number=202),
            ],
        },
        {
            "title": "Setup project", "description": "Bootstrap.",
            "status": "Backlog", "priority": "P1",
            "goal": "", "notes": "", "start_date": "", "end_date": "",
            "acceptance_criteria": ["Project setup"],
            "labels": ["infra"], "blocked_by": [101], "size": "", "points": None,
            "issue_number": 102,
            "tasks": [
                _child("Create repo", issue_number=203, status="Done"),
            ],
        },
    ],
}


@pytest.fixture
def backlog_file(tmp_path):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(SAMPLE_BACKLOG), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestNoItemFullTitle:
    def test_helper_removed(self):
        # Title is the bare issue identity now — no "id: title" prefixing.
        assert not hasattr(sp, "_item_full_title")


class TestBuildIssueBody:
    def test_with_criteria(self):
        item = {"acceptance_criteria": ["AC1", "AC2"]}
        result = sp.build_issue_body(item)
        assert "## Acceptance Criteria" in result
        assert "- [ ] AC1" in result and "- [ ] AC2" in result

    def test_empty(self):
        assert sp.build_issue_body({"acceptance_criteria": []}) == ""
        assert sp.build_issue_body({}) == ""

    def test_description_only(self):
        result = sp.build_issue_body({"description": "Why this matters."})
        assert "Why this matters." in result
        assert "## Acceptance Criteria" not in result

    def test_no_tasks_section(self):
        # Tasks are sub-issues now — never rendered in the body.
        result = sp.build_issue_body({
            "description": "Ctx.",
            "tasks": [{"title": "Sub", "issue_number": 9}],
            "acceptance_criteria": ["AC1"],
        })
        assert "## Tasks" not in result
        assert "Sub" not in result
        assert "Ctx." in result and "- [ ] AC1" in result

    def test_description_above_criteria(self):
        result = sp.build_issue_body({
            "description": "Why.", "acceptance_criteria": ["AC1"],
        })
        assert result.index("Why.") < result.index("## Acceptance Criteria")

    def test_no_task_helpers(self):
        assert not hasattr(sp, "_task_line")
        assert not hasattr(sp, "_tasks_checklist")


class TestIssueLabels:
    def test_returns_item_labels_lowercased(self):
        assert sp._issue_labels({"labels": ["Infra", "P0"]}) == ["infra", "p0"]

    def test_no_labels(self):
        assert sp._issue_labels({}) == []
        assert sp._issue_labels({"labels": []}) == []

    def test_ignores_type(self):
        # Type is gone; a stray `type` key must not become a label.
        assert sp._issue_labels({"type": "Spike"}) == []


# ---------------------------------------------------------------------------
# load_flat_data — tasks are now full issue-bearing items
# ---------------------------------------------------------------------------


class TestLoadFlatData:
    def test_returns_stories_and_tasks(self, backlog_file):
        stories, tasks, metadata, _ = sp.load_flat_data(backlog_file)
        assert len(stories) == 2
        assert len(tasks) == 3

    def test_tasks_are_full_items(self, backlog_file):
        _, tasks, _, _ = sp.load_flat_data(backlog_file)
        nums = {t["title"]: t.get("issue_number") for t in tasks}
        assert nums["Analyze features"] == 201
        assert nums["Create repo"] == 203

    def test_metadata_has_description(self, backlog_file):
        _, _, metadata, _ = sp.load_flat_data(backlog_file)
        assert metadata["project"] == "TestProject"
        assert metadata["description"] == "Build foundation"
        assert "goal" not in metadata

    def test_returns_raw_backlog(self, backlog_file):
        _, _, _, backlog_data = sp.load_flat_data(backlog_file)
        assert len(backlog_data["stories"]) == 2

    def test_empty_backlog(self, tmp_path):
        p = tmp_path / "b.json"
        p.write_text(json.dumps({"stories": []}), encoding="utf-8")
        stories, tasks, _, _ = sp.load_flat_data(p)
        assert stories == [] and tasks == []


class TestNoIdMap:
    def test_build_id_map_removed(self):
        assert not hasattr(sp, "build_id_to_issue_number_map")


# ---------------------------------------------------------------------------
# save_flat_data — writes issue_number back to parents AND children
# ---------------------------------------------------------------------------


class TestSaveFlatData:
    def test_writes_parent_and_child_numbers(self, tmp_path):
        p = tmp_path / "b.json"
        backlog = {
            "stories": [
                {"title": "S1", "tasks": [{"title": "C1"}]},
            ],
        }
        p.write_text(json.dumps(backlog), encoding="utf-8")
        stories, tasks, _, backlog_data = sp.load_flat_data(p)
        stories[0]["issue_number"] = 500
        tasks[0]["issue_number"] = 600
        sp.save_flat_data(stories, tasks, p, backlog_data)
        reloaded = json.loads(p.read_text(encoding="utf-8"))
        assert reloaded["stories"][0]["issue_number"] == 500
        assert reloaded["stories"][0]["tasks"][0]["issue_number"] == 600

    def test_preserves_other_fields(self, backlog_file):
        stories, tasks, _, backlog_data = sp.load_flat_data(backlog_file)
        sp.save_flat_data(stories, tasks, backlog_file, backlog_data)
        reloaded = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert reloaded["project"] == "TestProject"
        assert reloaded["stories"][0]["title"] == "Research features"


# ---------------------------------------------------------------------------
# blocked_by — issue numbers, no id_map
# ---------------------------------------------------------------------------


class TestCollectBlockingPairs:
    def test_pairs_from_issue_numbers(self):
        items = [
            {"title": "A", "issue_number": 100, "blocked_by": [200]},
            {"title": "B", "issue_number": 200, "blocked_by": []},
        ]
        pairs, involved = sp._collect_blocking_pairs(items)
        assert pairs == [(100, 200)]
        assert involved == {100, 200}

    def test_skips_items_without_number(self):
        items = [{"title": "A", "blocked_by": [200]}]
        pairs, involved = sp._collect_blocking_pairs(items)
        assert pairs == [] and involved == set()


class TestSetBlockingRelationship:
    @patch.object(sp, "_fetch_node_ids_and_edges",
                  return_value=({100: "NODE-100", 200: "NODE-200"}, set(), {}))
    @patch.object(sp, "execute_batched_mutations")
    def test_calls_addBlockedBy(self, mock_exec, mock_fetch):
        items = [{"title": "B", "issue_number": 100, "blocked_by": [200]}]
        sp.set_blocking_relationships("org/repo", items)
        mutations = mock_exec.call_args[0][0]
        assert any("addBlockedBy" in m for m in mutations)
        assert len(mutations) == 1

    @patch.object(sp, "_fetch_node_ids_and_edges", return_value=({}, set(), {}))
    @patch.object(sp, "execute_batched_mutations")
    def test_skips_empty(self, mock_exec, mock_fetch, capsys):
        sp.set_blocking_relationships("org/repo", [])
        assert "No blocking" in capsys.readouterr().out
        mock_exec.assert_not_called()

    @patch.object(sp, "_fetch_node_ids_and_edges",
                  return_value=({100: "NODE-100", 200: "NODE-200"}, {(100, 200)}, {}))
    @patch.object(sp, "execute_batched_mutations")
    def test_skips_pairs_already_set(self, mock_exec, mock_fetch):
        items = [{"title": "B", "issue_number": 100, "blocked_by": [200]}]
        sp.set_blocking_relationships("org/repo", items)
        assert mock_exec.call_args[0][0] == []

    @patch.object(sp, "_fetch_node_ids_and_edges",
                  return_value=({100: "NODE-100"}, set(), {}))
    @patch.object(sp, "execute_batched_mutations")
    def test_skips_dangling_blocker(self, mock_exec, mock_fetch):
        # Blocker #999 has no node id (dangling) → pair skipped, not crashed.
        items = [{"title": "B", "issue_number": 100, "blocked_by": [999]}]
        sp.set_blocking_relationships("org/repo", items)
        assert mock_exec.call_args[0][0] == []


class TestBlockedByInts:
    def test_blocking_mutations_use_numbers(self):
        node_ids = {100: "N100", 200: "N200"}
        mutations = sp._blocking_mutations(node_ids, [(100, 200)], set())
        assert len(mutations) == 1
        assert "addBlockedBy" in mutations[0]
        assert "N100" in mutations[0] and "N200" in mutations[0]


class TestFetchNodeIdsAndEdges:
    @patch.object(sp, "gh_json")
    def test_parses_ids_and_edges(self, mock_gh):
        mock_gh.return_value = {
            "data": {"repository": {
                "i100": {"id": "NODE-100", "number": 100,
                         "blockedBy": {"nodes": [{"number": 200}]},
                         "parent": None},
                "i200": {"id": "NODE-200", "number": 200,
                         "blockedBy": {"nodes": []}, "parent": None},
            }}
        }
        ids, edges, parents = sp._fetch_node_ids_and_edges("org/repo", {100, 200})
        assert ids == {100: "NODE-100", 200: "NODE-200"}
        assert edges == {(100, 200)}

    @patch.object(sp, "gh_json")
    def test_empty_input_skips_query(self, mock_gh):
        ids, edges, parents = sp._fetch_node_ids_and_edges("org/repo", set())
        assert ids == {} and edges == set() and parents == {}
        mock_gh.assert_not_called()


# ---------------------------------------------------------------------------
# resolve_existing_issues — bare-title identity
# ---------------------------------------------------------------------------


class TestResolveExistingIssues:
    def test_live_issue_number_kept(self):
        items = [{"title": "X", "issue_number": 42}]
        assert sp.resolve_existing_issues(items, {"X": 42}) == []
        assert items[0]["issue_number"] == 42

    def test_stale_issue_number_dropped(self):
        items = [{"title": "X", "issue_number": 999}]
        needs = sp.resolve_existing_issues(items, {})
        assert needs == items
        assert "issue_number" not in items[0]

    def test_matches_existing_by_bare_title(self):
        items = [{"title": "X"}]
        assert sp.resolve_existing_issues(items, {"X": 99}) == []
        assert items[0]["issue_number"] == 99

    def test_needs_creation(self):
        items = [{"title": "New"}]
        assert sp.resolve_existing_issues(items, {}) == items


# ---------------------------------------------------------------------------
# build_field_map / find_item_id / issue_url
# ---------------------------------------------------------------------------


class TestBuildFieldMap:
    def test_basic(self):
        fmap = sp.build_field_map([{"id": "F1", "name": "Status", "type": "TEXT"}])
        assert fmap["Status"]["id"] == "F1"

    def test_with_options(self):
        fields = [{
            "id": "F1", "name": "Status", "type": "SINGLE_SELECT",
            "options": [{"id": "O1", "name": "Done"}],
        }]
        assert sp.build_field_map(fields)["Status"]["options"] == {"Done": "O1"}


class TestFindItemId:
    def test_found(self):
        items = [{"id": "I2", "content": {"number": 2}}]
        assert sp.find_item_id(items, 2) == "I2"

    def test_not_found(self):
        assert sp.find_item_id([], 99) is None


class TestIssueUrl:
    def test_basic(self):
        assert sp.issue_url("o/r", 42) == "https://github.com/o/r/issues/42"


# ---------------------------------------------------------------------------
# _build_field_value — single-select, text, AND dates
# ---------------------------------------------------------------------------


class TestBuildFieldValue:
    def test_single_select(self):
        field_map = {"Status": {"id": "F1", "options": {"Done": "O1"}}}
        assert sp._build_field_value(field_map, "Status", "Done") == {
            "singleSelectOptionId": '"O1"'
        }

    def test_text(self):
        assert sp._build_field_value({"Notes": {"id": "F4"}}, "Notes", "hi") == {
            "text": '"hi"'
        }

    def test_date_field(self):
        field_map = {"Start date": {"id": "FD"}}
        assert sp._build_field_value(field_map, "Start date", "2026-02-17") == {
            "date": '"2026-02-17"'
        }

    def test_target_date_field(self):
        field_map = {"Target date": {"id": "FTD"}}
        assert sp._build_field_value(field_map, "Target date", "2026-02-20") == {
            "date": '"2026-02-20"'
        }

    def test_none_value(self):
        assert sp._build_field_value({"X": {"id": "F"}}, "X", None) is None

    def test_empty_value(self):
        assert sp._build_field_value({"X": {"id": "F"}}, "X", "") is None

    def test_field_not_found(self):
        assert sp._build_field_value({}, "Missing", "val") is None


# ---------------------------------------------------------------------------
# Field specs — Status + Priority + Start/Target date
# ---------------------------------------------------------------------------


class TestFieldSpecs:
    def test_base_specs(self):
        # Local `end_date` maps to the board's native "Target date" field.
        assert sp._BASE_FIELD_SPECS == [
            ("Status", "status"), ("Priority", "priority"),
            ("Start date", "start_date"), ("Target date", "end_date"),
        ]

    def test_required_fields_include_dates(self):
        names = [name for name, _, _ in sp._REQUIRED_FIELDS]
        assert names == ["Status", "Priority", "Start date", "Target date"]

    def test_required_date_fields_are_date_type(self):
        by_name = {n: t for n, t, _ in sp._REQUIRED_FIELDS}
        assert by_name["Start date"] == "DATE"
        assert by_name["Target date"] == "DATE"

    def test_status_options_include_ready(self):
        opts = {n: o for n, _, o in sp._REQUIRED_FIELDS}["Status"]
        assert "Ready" in opts


class TestEnsureReadyOption:
    def test_missing_option_mutation_appends_and_preserves(self):
        m = sp._missing_option_mutation("FS", ["Backlog", "Done"], "Ready")
        assert "updateProjectV2Field" in m and "FS" in m
        # New option added, existing options re-sent so GitHub preserves them.
        assert "Ready" in m and "Backlog" in m and "Done" in m

    def test_missing_option_mutation_idempotent(self):
        assert sp._missing_option_mutation("FS", ["Backlog", "Ready"], "Ready") is None

    def test_ensure_option_adds_when_missing(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(sp, "run", lambda cmd, **k: calls.append(cmd))
        fmap = {"Status": {"id": "FS", "options": {"Backlog": "O1", "Done": "O2"}}}
        assert sp.ensure_single_select_option("Status", "Ready", fmap) is True
        assert any("updateProjectV2Field" in " ".join(c) for c in calls)

    def test_ensure_option_noop_when_present(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(sp, "run", lambda cmd, **k: calls.append(cmd))
        fmap = {"Status": {"id": "FS", "options": {"Ready": "O1"}}}
        assert sp.ensure_single_select_option("Status", "Ready", fmap) is False
        assert calls == []

    def test_ensure_option_noop_when_field_absent(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(sp, "run", lambda cmd, **k: calls.append(cmd))
        assert sp.ensure_single_select_option("Status", "Ready", {}) is False
        assert calls == []

    def test_ensure_required_fields_adds_ready_and_signals_rebuild(self, monkeypatch):
        calls: list = []
        monkeypatch.setattr(sp, "run", lambda cmd, **k: calls.append(cmd))
        fmap = {
            "Status": {"id": "FS", "options": {
                "Backlog": "O1", "In Progress": "O2", "Done": "O3"}},
            "Priority": {"id": "FP", "options": {"P0": "P", "P1": "Q", "P2": "R"}},
            "Start date": {"id": "FSD"}, "Target date": {"id": "FED"},
        }
        assert sp.Syncer()._ensure_required_fields("PID", fmap) is True
        assert any("updateProjectV2Field" in " ".join(c) for c in calls)


# ---------------------------------------------------------------------------
# _collect_mutations — status/priority + date fields
# ---------------------------------------------------------------------------


_FIELD_MAP = {
    "Status": {"id": "FS", "options": {
        "Backlog": "OS_B", "In Progress": "OS_IP", "Done": "OS_D",
    }},
    "Priority": {"id": "FP", "options": {"P0": "OP0", "P1": "OP1", "P2": "OP2"}},
    "Start date": {"id": "FSD"},
    "Target date": {"id": "FED"},
}


class TestCollectMutations:
    def test_emits_status_and_priority(self):
        item = {
            "title": "X", "issue_number": 1,
            "status": "In Progress", "priority": "P0",
        }
        items = [{"id": "ITEM-1", "content": {"number": 1}}]
        mutations = sp._collect_mutations([item], items, "PID", _FIELD_MAP, {})
        flat = " ".join(mutations)
        assert "FS" in flat and "FP" in flat

    def test_empty(self):
        assert sp._collect_mutations([], [], "PID", {}, {}) == []


class TestDateFields:
    def _items(self):
        return [{"id": "ITEM-1", "content": {"number": 1}}]

    def test_pushes_start_and_end_dates(self):
        item = {
            "title": "X", "issue_number": 1, "status": "Backlog",
            "start_date": "2026-02-17", "end_date": "2026-02-20",
        }
        mutations = sp._collect_mutations([item], self._items(), "PID", _FIELD_MAP, {})
        flat = " ".join(mutations)
        assert "FSD" in flat and "FED" in flat
        assert "2026-02-17" in flat and "2026-02-20" in flat

    def test_skips_empty_dates(self):
        item = {
            "title": "X", "issue_number": 1, "status": "Backlog",
            "start_date": "", "end_date": "",
        }
        mutations = sp._collect_mutations([item], self._items(), "PID", _FIELD_MAP, {})
        flat = " ".join(mutations)
        assert "FSD" not in flat and "FED" not in flat


# ---------------------------------------------------------------------------
# Sub-issue reconcile — link desired, detach undesired by (parent#, child#)
# ---------------------------------------------------------------------------


class TestSubIssuePairs:
    def test_desired_pairs_from_stories(self):
        stories = [
            {"title": "P", "issue_number": 10,
             "tasks": [{"title": "C1", "issue_number": 11},
                       {"title": "C2", "issue_number": 12}]},
        ]
        assert sp._desired_sub_issue_pairs(stories) == {(10, 11), (10, 12)}

    def test_desired_skips_unnumbered(self):
        stories = [{"title": "P", "tasks": [{"title": "C"}]}]
        assert sp._desired_sub_issue_pairs(stories) == set()

    def test_existing_pairs_from_subs(self):
        subs = {10: [(11, "N11", "C1"), (12, "N12", "C2")]}
        assert sp._existing_sub_issue_pairs(subs) == {(10, 11), (10, 12)}


class TestReconcileSubIssueMutations:
    def test_links_missing(self):
        node_ids = {10: "N10", 13: "N13"}
        mutations = sp._reconcile_sub_issue_mutations({(10, 13)}, set(), node_ids)
        assert len(mutations) == 1
        assert "addSubIssue" in mutations[0]
        assert "N10" in mutations[0] and "N13" in mutations[0]

    def test_detaches_undesired(self):
        node_ids = {10: "N10", 11: "N11"}
        mutations = sp._reconcile_sub_issue_mutations(set(), {(10, 11)}, node_ids)
        assert len(mutations) == 1
        assert "removeSubIssue" in mutations[0]

    def test_no_change_zero_mutations(self):
        node_ids = {10: "N10", 11: "N11"}
        assert sp._reconcile_sub_issue_mutations({(10, 11)}, {(10, 11)}, node_ids) == []

    def test_skips_when_node_missing(self):
        mutations = sp._reconcile_sub_issue_mutations({(10, 13)}, set(), {10: "N10"})
        assert mutations == []


class TestSubIssueIdempotency:
    @patch.object(sp, "_fetch_sub_issues")
    @patch.object(sp, "_fetch_node_ids_and_edges")
    @patch.object(sp, "execute_batched_mutations")
    def test_unchanged_tree_zero_mutations(self, mock_exec, mock_nodes, mock_subs):
        stories = [{"title": "P", "issue_number": 10,
                    "tasks": [{"title": "C", "issue_number": 11}]}]
        mock_subs.return_value = ({10: "N10"}, {10: [(11, "N11", "C")]})
        mock_nodes.return_value = ({10: "N10", 11: "N11"}, set(), {})
        sp.reconcile_sub_issues("org/repo", stories)
        # Already linked → no add/remove mutations.
        assert not mock_exec.called or mock_exec.call_args[0][0] == []

    @patch.object(sp, "_fetch_sub_issues")
    @patch.object(sp, "_fetch_node_ids_and_edges")
    @patch.object(sp, "execute_batched_mutations")
    def test_new_child_links(self, mock_exec, mock_nodes, mock_subs):
        stories = [{"title": "P", "issue_number": 10,
                    "tasks": [{"title": "C", "issue_number": 11}]}]
        mock_subs.return_value = ({10: "N10"}, {10: []})
        mock_nodes.return_value = ({10: "N10", 11: "N11"}, set(), {})
        sp.reconcile_sub_issues("org/repo", stories)
        mutations = mock_exec.call_args[0][0]
        assert len(mutations) == 1
        assert "addSubIssue" in mutations[0]


class TestFetchSubIssues:
    @patch.object(sp, "gh_json")
    def test_parses_node_ids_titles_and_subs(self, mock_gh):
        mock_gh.return_value = {
            "data": {"repository": {
                "i100": {
                    "id": "N100", "number": 100, "title": "P",
                    "subIssues": {"nodes": [
                        {"id": "N101", "number": 101, "title": "C1"},
                    ]},
                },
            }}
        }
        node_ids, subs = sp._fetch_sub_issues("org/repo", {100})
        assert node_ids == {100: "N100"}
        assert subs[100] == [(101, "N101", "C1")]

    @patch.object(sp, "gh_json")
    def test_query_selects_title(self, mock_gh):
        mock_gh.return_value = {"data": {"repository": {}}}
        sp._fetch_sub_issues("org/repo", {100})
        query = mock_gh.call_args[0][0][-1]
        assert "subIssues(" in query
        assert "title" in query


# ---------------------------------------------------------------------------
# Labels reconcile on existing issues
# ---------------------------------------------------------------------------


class TestReconcileLabels:
    @patch.object(sp, "run")
    @patch.object(sp, "ensure_label")
    def test_adds_labels_to_existing_issue(self, mock_label, mock_run):
        sp._ensure_issue_labels("org/repo", {"issue_number": 5, "labels": ["Infra"]})
        cmd = mock_run.call_args[0][0]
        assert "issue" in cmd and "edit" in cmd
        assert "--add-label" in cmd and "infra" in cmd

    @patch.object(sp, "run")
    def test_skips_issue_without_number(self, mock_run):
        sp._ensure_issue_labels("org/repo", {"labels": ["x"]})
        mock_run.assert_not_called()

    @patch.object(sp, "run")
    def test_skips_issue_without_labels(self, mock_run):
        sp._ensure_issue_labels("org/repo", {"issue_number": 5, "labels": []})
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# _extract_item_field_values + _build_remote_values_map
# ---------------------------------------------------------------------------


class TestExtractItemFieldValues:
    def test_status_and_priority(self):
        result = sp._extract_item_field_values(
            {"id": "X", "status": "In Progress", "priority": "P0"}
        )
        assert result["Status"] == "In Progress"
        assert result["Priority"] == "P0"

    def test_missing_excluded(self):
        result = sp._extract_item_field_values({"id": "X", "status": "Backlog"})
        assert "Status" in result and "Priority" not in result


class TestBuildRemoteValuesMap:
    def test_builds_map(self):
        items = [{"id": "I1", "status": "In Progress", "priority": "P0"}]
        assert sp._build_remote_values_map(items) == {
            "I1": {"Status": "In Progress", "Priority": "P0"}
        }

    def test_skips_items_without_id(self):
        assert sp._build_remote_values_map([{"status": "Backlog"}]) == {}


# ---------------------------------------------------------------------------
# Pass 2 diff
# ---------------------------------------------------------------------------


class TestPass2Diffing:
    def _items(self):
        return [{"id": "ITEM-1", "content": {"number": 1}}]

    def test_skips_field_when_unchanged(self):
        item = {"title": "X", "issue_number": 1, "status": "In Progress"}
        remote = {"ITEM-1": {"Status": "In Progress"}}
        assert sp._collect_mutations([item], self._items(), "PID", _FIELD_MAP, remote) == []

    def test_emits_when_status_changes(self):
        item = {"title": "X", "issue_number": 1, "status": "In Progress"}
        remote = {"ITEM-1": {"Status": "Backlog"}}
        mutations = sp._collect_mutations([item], self._items(), "PID", _FIELD_MAP, remote)
        assert len(mutations) == 1 and "FS" in mutations[0]


# ---------------------------------------------------------------------------
# run_pass2_batched — children get fields too
# ---------------------------------------------------------------------------


class TestRunPass2Batched:
    @patch.object(sp, "execute_batched_mutations")
    def test_child_items_get_field_mutations(self, mock_exec):
        # A sub-issue with its own board item gets Status pushed.
        items = [{"id": "ITEM-9", "content": {"number": 9},
                  "status": "Backlog", "priority": ""}]
        child = {"title": "Sub", "issue_number": 9, "status": "Done",
                 "priority": "", "title_only": True}
        remote = sp._build_remote_values_map(items)
        sp.run_pass2_batched([child], items, "PID", _FIELD_MAP, "org/repo",
                             remote_by_item=remote)
        mutations = mock_exec.call_args[0][0]
        assert len(mutations) == 1 and "FS" in mutations[0]


# ---------------------------------------------------------------------------
# Pass 1c: refresh existing issue bodies
# ---------------------------------------------------------------------------


class TestFetchIssueBodies:
    @patch.object(sp, "gh_json")
    def test_parses_bodies(self, mock_gh):
        mock_gh.return_value = {
            "data": {"repository": {
                "i100": {"number": 100, "id": "N100", "body": "Body A"},
            }}
        }
        assert sp._fetch_issue_bodies("org/repo", {100}) == {100: ("N100", "Body A")}

    @patch.object(sp, "gh_json")
    def test_empty_input_skips_query(self, mock_gh):
        assert sp._fetch_issue_bodies("org/repo", set()) == {}
        mock_gh.assert_not_called()


class TestCollectBodyUpdateMutations:
    def test_emits_when_body_differs(self):
        item = {"title": "X", "issue_number": 100, "description": "New context"}
        bodies = {100: ("N100", "")}
        mutations = sp._collect_body_update_mutations([item], bodies)
        assert len(mutations) == 1
        assert "updateIssue" in mutations[0] and "New context" in mutations[0]

    def test_skips_when_body_matches(self):
        item = {"title": "X", "issue_number": 100, "description": "Same"}
        bodies = {100: ("N100", sp.build_issue_body(item))}
        assert sp._collect_body_update_mutations([item], bodies) == []

    def test_skips_without_issue_number(self):
        assert sp._collect_body_update_mutations([{"title": "X", "description": "X"}], {}) == []


class TestUpdateIssueBodies:
    @patch.object(sp, "_fetch_issue_bodies")
    @patch.object(sp, "execute_batched_mutations")
    def test_runs_when_body_differs(self, mock_exec, mock_fetch):
        mock_fetch.return_value = {100: ("N100", "stale")}
        items = [{"title": "X", "issue_number": 100, "description": "Fresh"}]
        sp.update_issue_bodies("org/repo", items)
        assert len(mock_exec.call_args[0][0]) == 1

    @patch.object(sp, "_fetch_issue_bodies")
    @patch.object(sp, "execute_batched_mutations")
    def test_skips_without_numbers(self, mock_exec, mock_fetch):
        sp.update_issue_bodies("org/repo", [{"title": "X", "description": "X"}])
        mock_fetch.assert_not_called()
        mock_exec.assert_not_called()


# ---------------------------------------------------------------------------
# _create_issue — bare title
# ---------------------------------------------------------------------------


class TestCreateIssue:
    @patch.object(sp, "run", return_value="https://github.com/org/repo/issues/5")
    @patch.object(sp, "ensure_label")
    def test_returns_number_and_uses_bare_title(self, mock_label, mock_run):
        item = {"title": "New", "labels": []}
        assert sp._create_issue(item, "org/repo") == 5
        assert item["issue_number"] == 5
        cmd = mock_run.call_args[0][0]
        # Title passed bare — no "id: " prefix.
        assert "New" in cmd

    @patch.object(sp, "run", return_value="https://github.com/org/repo/issues/1")
    @patch.object(sp, "ensure_label")
    def test_dedup_guard(self, mock_label, mock_run):
        sp._create_issue({"title": "X"}, "org/repo")
        with pytest.raises(RuntimeError, match="Duplicate"):
            sp._create_issue({"title": "X"}, "org/repo")

    @patch.object(sp, "run", return_value="https://github.com/org/repo/issues/1")
    @patch.object(sp, "ensure_label")
    def test_uses_item_labels(self, mock_label, mock_run):
        sp._create_issue({"title": "X", "labels": ["Infra"]}, "org/repo")
        cmd = mock_run.call_args[0][0]
        assert "infra" in cmd


class TestEnsureIssue:
    def test_returns_existing_number(self):
        assert sp.ensure_issue({"title": "X", "issue_number": 5}, "org/repo") == 5

    def test_uses_cache_by_bare_title(self):
        assert sp.ensure_issue({"title": "X"}, "org/repo", {"X": 10}) == 10

    @patch.object(sp, "find_existing_issue", return_value=20)
    def test_fallback_search(self, mock_find):
        assert sp.ensure_issue({"title": "X"}, "org/repo", {}) == 20


# ---------------------------------------------------------------------------
# execute_batched_mutations
# ---------------------------------------------------------------------------


class TestExecuteBatchedMutations:
    def test_empty(self, capsys):
        sp.execute_batched_mutations([])
        assert "No field updates" in capsys.readouterr().out

    @patch("subprocess.run")
    def test_single_batch(self, mock_run, capsys):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "{}", "stderr": ""})()
        sp.execute_batched_mutations([f"m{i}: stub" for i in range(5)])
        assert "Batch 1/1" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Syncer class
# ---------------------------------------------------------------------------


class TestSyncerClass:
    def test_init_defaults(self):
        s = sp.Syncer()
        assert s.backlog_path is not None and s.repo is not None

    def test_init_with_overrides(self, tmp_path):
        s = sp.Syncer(backlog_path=tmp_path / "b.json", repo="o/r", project=7, owner="me")
        assert s.repo == "o/r" and s.project == 7 and s.owner == "me"


# ---------------------------------------------------------------------------
# sync --dry-run is fully read-only (zero remote mutations)
# ---------------------------------------------------------------------------


# Every module-level entry point that writes to GitHub. In a dry-run none of
# these may be reached.
_DRY_RUN_MUTATORS = [
    "_resolve_or_create", "update_issue_bodies", "reconcile_labels",
    "_add_all_to_project_batched", "run_pass2_batched",
    "set_blocking_relationships", "reconcile_sub_issues",
    "ensure_project_field", "ensure_single_select_option",
    "_writeback_numbers", "get_project_id",
]


def _dry_run_backlog(tmp_path):
    item = {
        "title": "Story 1", "description": "", "status": "Backlog",
        "priority": "", "goal": "", "notes": "", "start_date": "",
        "end_date": "", "acceptance_criteria": [], "labels": [],
        "blocked_by": [], "size": "", "points": None, "issue_number": None,
    }
    sub = dict(item, title="Sub 1")
    p = tmp_path / "b.json"
    p.write_text(json.dumps({
        "project": "T", "description": "d", "dates": {},
        "stories": [dict(item, tasks=[sub])],
    }), encoding="utf-8")
    return p


def _stub_reads(monkeypatch, existing=None, fields=None):
    monkeypatch.setattr(sp, "fetch_all_open_issues", lambda repo: existing or {})
    monkeypatch.setattr(sp, "get_project_fields", lambda n, o: fields or [])


class TestSyncDryRunReadOnly:
    def test_no_mutations_in_dry_run(self, tmp_path, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("dry-run must not mutate GitHub")

        for name in _DRY_RUN_MUTATORS:
            monkeypatch.setattr(sp, name, boom)
        _stub_reads(monkeypatch)
        s = sp.Syncer(backlog_path=_dry_run_backlog(tmp_path),
                      repo="o/r", project=4, owner="me")
        assert s.sync(dry_run=True) == 0

    def test_reports_creates_for_new_titles(self, tmp_path, monkeypatch, capsys):
        _stub_reads(monkeypatch)
        s = sp.Syncer(backlog_path=_dry_run_backlog(tmp_path),
                      repo="o/r", project=4, owner="me")
        s.sync(dry_run=True)
        out = capsys.readouterr().out
        assert "Would create 2 new issue(s)" in out
        assert "Story 1" in out and "Sub 1" in out

    def test_reports_updates_for_existing_titles(self, tmp_path, monkeypatch, capsys):
        _stub_reads(monkeypatch, existing={"Story 1": 1, "Sub 1": 2})
        s = sp.Syncer(backlog_path=_dry_run_backlog(tmp_path),
                      repo="o/r", project=4, owner="me")
        s.sync(dry_run=True)
        out = capsys.readouterr().out
        assert "Would create 0 new issue(s)" in out
        assert "Would update 2 existing issue(s)" in out

    def test_flags_missing_board_field_and_ready_option(
        self, tmp_path, monkeypatch, capsys
    ):
        fields = [{"id": "FS", "name": "Status", "type": "SINGLE_SELECT",
                   "options": [{"id": "O1", "name": "Backlog"}]}]
        _stub_reads(monkeypatch, fields=fields)
        s = sp.Syncer(backlog_path=_dry_run_backlog(tmp_path),
                      repo="o/r", project=4, owner="me")
        s.sync(dry_run=True)
        out = capsys.readouterr().out
        assert "Priority" in out          # missing field reported
        assert "Ready" in out and "Status" in out  # missing option reported

    def test_run_unknown_mode(self, tmp_path):
        s = sp.Syncer(backlog_path=tmp_path / "b.json")
        with pytest.raises(ValueError, match="Unknown sync mode"):
            s.run("not-a-mode")

    def test_modes_registered(self):
        for mode in ("sync", "delete-all", "delete_all", "pull"):
            assert mode in sp.Syncer._MODE_MAP

    def test_run_clears_created_titles(self, tmp_path):
        sp._created_titles.add("leftover")
        s = sp.Syncer(backlog_path=tmp_path / "b.json")
        captured: dict = {}
        with patch.object(s, "sync") as mock_sync:
            mock_sync.side_effect = lambda **k: captured.setdefault(
                "at_dispatch", set(sp._created_titles)) or 0
            s.run("sync")
        assert captured["at_dispatch"] == set()


# ---------------------------------------------------------------------------
# pull — full mirror of GitHub state back into the backlog
# ---------------------------------------------------------------------------


def _groomed(title, num, **over):
    base = {
        "title": title, "description": "old desc",
        "status": "In Progress", "priority": "P0",
        "goal": "local goal", "notes": "local notes",
        "start_date": "2026-01-01", "end_date": "2026-01-05",
        "acceptance_criteria": ["local AC"], "labels": ["old"],
        "blocked_by": [], "size": "M", "points": 3,
        "issue_number": num, "tasks": [],
    }
    base.update(over)
    return base


class TestInvertEdges:
    def test_inverts_to_int_lists(self):
        result = sp._invert_edges({(1, 2), (1, 3), (4, 2)})
        assert sorted(result[1]) == [2, 3]
        assert result[4] == [2]

    def test_empty(self):
        assert sp._invert_edges(set()) == {}


class TestBodyToDescription:
    def test_strips_ac_section(self):
        body = "Why this matters.\n\n## Acceptance Criteria\n\n- [ ] AC1"
        assert sp._body_to_description(body) == "Why this matters."

    def test_no_ac(self):
        assert sp._body_to_description("Just text.") == "Just text."

    def test_empty(self):
        assert sp._body_to_description("") == ""


class TestAssemblePulledIssues:
    def test_assembles_fields_and_inverts_edges(self):
        issues = sp._assemble_pulled_issues(
            {100},
            {100: {"title": "A", "body": "Ctx.\n\n## Acceptance Criteria\n\n- [ ] x"}},
            {100: "P0"},
            {100: [200]},
        )
        assert issues[100]["title"] == "A"
        assert issues[100]["description"] == "Ctx."
        assert issues[100]["priority"] == "P0"
        assert issues[100]["blocked_by"] == [200]


class TestPullBoardPriority:
    def test_extracts_priority_by_number(self):
        board = [
            {"content": {"number": 5}, "priority": "P1"},
            {"content": {"number": 6}},
        ]
        assert sp._pull_board_priority(board) == {5: "P1"}


class TestMergePulled:
    def test_github_wins_local_preserved(self):
        backlog = {
            "project": "P", "description": "d", "dates": {"start": "2026-02-01"},
            "stories": [_groomed("Old title", 100)],
        }
        pulled = {
            "issues": {100: {
                "title": "New title", "description": "New desc",
                "labels": ["a", "b"], "priority": "P2", "blocked_by": [],
            }},
            "parents": {},
        }
        s = sp.merge_pulled(backlog, pulled)["stories"][0]
        # GitHub wins
        assert s["title"] == "New title"
        assert s["description"] == "New desc"
        assert s["labels"] == ["a", "b"]
        assert s["priority"] == "P2"
        # local preserved
        assert s["status"] == "In Progress"
        assert s["goal"] == "local goal"
        assert s["acceptance_criteria"] == ["local AC"]
        assert s["start_date"] == "2026-01-01"
        assert s["points"] == 3

    def test_root_dates_preserved(self):
        backlog = {"dates": {"start": "x"}, "stories": []}
        merged = sp.merge_pulled(backlog, {"issues": {}, "parents": {}})
        assert merged["dates"] == {"start": "x"}

    def test_new_issue_becomes_lean_story(self):
        backlog = {"stories": []}
        pulled = {"issues": {55: {
            "title": "Fresh", "description": "D", "labels": [],
            "priority": "P1", "blocked_by": [],
        }}, "parents": {}}
        s = sp.merge_pulled(backlog, pulled)["stories"][0]
        assert s["title"] == "Fresh"
        assert s["issue_number"] == 55
        assert s["status"] == "Backlog"
        assert s["points"] is None

    def test_subissue_attached_under_parent(self):
        backlog = {"stories": [_groomed("Parent", 10)]}
        pulled = {
            "issues": {
                10: {"title": "Parent", "description": "", "labels": [],
                     "priority": "P0", "blocked_by": []},
                11: {"title": "Child", "description": "", "labels": [],
                     "priority": "P1", "blocked_by": []},
            },
            "parents": {11: 10},
        }
        parent = sp.merge_pulled(backlog, pulled)["stories"][0]
        assert parent["issue_number"] == 10
        assert [t["issue_number"] for t in parent["tasks"]] == [11]
        assert "tasks" not in parent["tasks"][0]  # leaf

    def test_dedup_by_title_adopts_number(self):
        local = _groomed("Same title", None)
        local["issue_number"] = None
        backlog = {"stories": [local]}
        pulled = {"issues": {77: {
            "title": "Same title", "description": "gh", "labels": [],
            "priority": "P2", "blocked_by": [],
        }}, "parents": {}}
        merged = sp.merge_pulled(backlog, pulled)
        assert len(merged["stories"]) == 1
        assert merged["stories"][0]["issue_number"] == 77

    def test_blocked_by_ints_from_edges(self):
        backlog = {"stories": [_groomed("S", 100)]}
        pulled = {"issues": {100: {
            "title": "S", "description": "", "labels": [],
            "priority": "P0", "blocked_by": [200],
        }}, "parents": {}}
        s = sp.merge_pulled(backlog, pulled)["stories"][0]
        assert s["blocked_by"] == [200]

    def test_preserves_board_absent_local_story(self):
        backlog = {"stories": [_groomed("Local only", None)]}
        merged = sp.merge_pulled(backlog, {"issues": {}, "parents": {}})
        assert any(s["title"] == "Local only" for s in merged["stories"])


class TestSyncerPull:
    def _backlog(self, tmp_path):
        p = tmp_path / "b.json"
        p.write_text(json.dumps(
            {"project": "P", "description": "d", "dates": {}, "stories": []}
        ), encoding="utf-8")
        return p

    def test_dry_run_writes_nothing(self, tmp_path):
        p = self._backlog(tmp_path)
        before = p.read_text(encoding="utf-8")
        s = sp.Syncer(backlog_path=p)
        pulled = {"issues": {55: {
            "title": "Fresh", "description": "D", "labels": [],
            "priority": "P1", "blocked_by": [],
        }}, "parents": {}}
        with patch.object(s, "_fetch_pull_state", return_value=pulled):
            assert s.run("pull", dry_run=True) == 0
        assert p.read_text(encoding="utf-8") == before

    def test_pull_writes_merged(self, tmp_path):
        p = self._backlog(tmp_path)
        s = sp.Syncer(backlog_path=p)
        pulled = {"issues": {55: {
            "title": "Fresh", "description": "D", "labels": [],
            "priority": "P1", "blocked_by": [],
        }}, "parents": {}}
        with patch.object(s, "_fetch_pull_state", return_value=pulled):
            assert s.run("pull") == 0
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["stories"][0]["title"] == "Fresh"
        assert data["stories"][0]["issue_number"] == 55
