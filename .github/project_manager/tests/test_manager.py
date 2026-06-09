"""Tests for project_manager.manager — unified-item backlog schema.

Schema reminder (one shape for stories AND sub-issues):
- title, description, status, priority, goal, notes, start_date,
  end_date, acceptance_criteria, labels, blocked_by (issue numbers),
  size, points, issue_number, tasks (parents only).
- Identity is `title` (pre-sync) → `issue_number` (post-sync).
- `id` and `type` are gone.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from project_manager import ProjectManager
from project_manager import manager as pm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _child(title, description, status, *, priority="", issue_number=None):
    return {
        "title": title, "description": description,
        "status": status, "priority": priority,
        "goal": "", "notes": "", "start_date": "", "end_date": "",
        "acceptance_criteria": [], "labels": [], "blocked_by": [],
        "size": "", "points": None, "issue_number": issue_number,
    }


SAMPLE_BACKLOG: dict = {
    "project": "Test",
    "description": "Test description",
    "dates": {"start": "2026-01-01", "end": "2026-03-01"},
    "stories": [
        {
            "title": "Research feature X",
            "description": "Investigate feature X impact.",
            "status": "In Progress", "priority": "P0",
            "goal": "Understand X", "notes": "see spike",
            "start_date": "2026-01-02", "end_date": "2026-01-10",
            "acceptance_criteria": ["AC1", "AC2"], "labels": ["spike"],
            "blocked_by": [], "size": "M", "points": 3,
            "issue_number": 101,
            "tasks": [
                _child("Setup CI pipeline", "Wire up GitHub Actions.",
                       "Done", priority="P1", issue_number=201),
                _child("Add auth module", "Stand up the login flow.",
                       "Backlog", priority="P2", issue_number=202),
            ],
        },
        {
            "title": "Project setup",
            "description": "Bootstrap the repo.",
            "status": "Backlog", "priority": "P1",
            "goal": "", "notes": "",
            "start_date": "", "end_date": "",
            "acceptance_criteria": [], "labels": [],
            "blocked_by": [], "size": "", "points": None,
            "issue_number": 102,
            "tasks": [
                _child("Fix login bug", "Address the redirect loop.",
                       "Backlog", priority="P0", issue_number=203),
            ],
        },
    ],
}


@pytest.fixture
def backlog_file(tmp_path):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(SAMPLE_BACKLOG), encoding="utf-8")
    return p


@pytest.fixture
def pm_instance(backlog_file):
    return ProjectManager(backlog_file)


@pytest.fixture
def all_items(pm_instance):
    return pm_instance.load_all_items()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_status_enum(self):
        assert set(pm.STATUS_ORDER) == {"Backlog", "Ready", "In Progress", "Done"}

    def test_priority_enum(self):
        assert set(pm.PRIORITY_ORDER) == {"P0", "P1", "P2"}

    def test_valid_transitions(self):
        assert pm.VALID_TRANSITIONS == {
            "Backlog": {"In Progress", "Ready"},
            "Ready": {"In Progress", "Backlog"},
            "In Progress": {"Done", "Backlog"},
            "Done": {"In Progress"},
        }

    def test_no_type_prefixes(self):
        assert not hasattr(pm, "STORY_TYPE_PREFIXES")

    def test_no_next_id(self):
        assert not hasattr(pm, "_next_id")

    def test_no_type_rank(self):
        assert not hasattr(pm, "_TYPE_RANK")

    def test_default_columns_no_id_or_type(self):
        keys = [k for _, k, _ in pm.DEFAULT_COLUMNS]
        assert "id" not in keys and "type" not in keys
        assert keys == ["issue_number", "status", "priority", "title"]

    def test_wide_columns_add_size_and_points(self):
        keys = [k for _, k, _ in pm.WIDE_COLUMNS]
        assert "size" in keys and "points" in keys
        assert "id" not in keys and "type" not in keys

    def test_backlog_default_shape(self):
        assert set(pm.BACKLOG_DEFAULT) == {"project", "description", "dates", "stories"}
        assert "goal" not in pm.BACKLOG_DEFAULT
        assert pm.BACKLOG_DEFAULT["stories"] == []


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------


class TestSortKey:
    def test_priority_order(self):
        assert pm._sort_key("priority", {"priority": "P0"}) == 0
        assert pm._sort_key("priority", {"priority": "Unknown"}) == 99

    def test_status_order(self):
        assert pm._sort_key("status", {"status": "Done"}) == 0
        assert pm._sort_key("status", {"status": "Ready"}) == 2
        assert pm._sort_key("status", {"status": "Backlog"}) == 3

    def test_issue_number(self):
        assert pm._sort_key("issue_number", {"issue_number": 5}) == 5
        assert pm._sort_key("issue_number", {"issue_number": None}) == 0

    def test_points_numeric(self):
        assert pm._sort_key("points", {"points": 8}) == 8
        assert pm._sort_key("points", {"points": None}) == 0

    def test_string_field(self):
        assert pm._sort_key("title", {"title": "Hello"}) == "hello"


class TestMatches:
    def test_exact_match(self):
        item = {"status": "Done", "priority": "P0"}
        assert pm._matches(item, {"status": "Done"}) is True
        assert pm._matches(item, {"status": "Backlog"}) is False

    def test_case_insensitive(self):
        assert pm._matches({"status": "In Progress"}, {"status": "in progress"}) is True

    def test_missing_field(self):
        assert pm._matches({}, {"status": "Done"}) is False

    def test_empty_filters(self):
        assert pm._matches({"status": "Done"}, {}) is True


class TestFindItemByKey:
    def test_story_by_title(self):
        item, parent = pm._find_item_by_key(SAMPLE_BACKLOG, "Research feature X")
        assert item["issue_number"] == 101
        assert parent is None

    def test_story_by_title_case_insensitive(self):
        item, parent = pm._find_item_by_key(SAMPLE_BACKLOG, "research FEATURE x")
        assert item["issue_number"] == 101

    def test_story_by_issue_number(self):
        item, parent = pm._find_item_by_key(SAMPLE_BACKLOG, "102")
        assert item["title"] == "Project setup"
        assert parent is None

    def test_subissue_by_title(self):
        item, parent = pm._find_item_by_key(SAMPLE_BACKLOG, "Add auth module")
        assert item["issue_number"] == 202
        assert parent["title"] == "Research feature X"

    def test_subissue_by_issue_number(self):
        item, parent = pm._find_item_by_key(SAMPLE_BACKLOG, "203")
        assert item["title"] == "Fix login bug"
        assert parent["title"] == "Project setup"

    def test_not_found(self):
        assert pm._find_item_by_key(SAMPLE_BACKLOG, "nope") == (None, None)


class TestValidateTransition:
    def test_valid(self):
        assert pm._validate_transition("Backlog", "In Progress") is None

    def test_invalid_returns_message(self):
        err = pm._validate_transition("Backlog", "Done")
        assert err is not None and "Cannot move" in err

    def test_done_to_in_progress_allowed(self):
        assert pm._validate_transition("Done", "In Progress") is None


class TestIsUnblocked:
    def test_empty(self):
        assert pm._is_unblocked([], {}) is True

    def test_all_done(self):
        assert pm._is_unblocked([11], {11: "Done"}) is True

    def test_not_done(self):
        assert pm._is_unblocked([11], {11: "Backlog"}) is False

    def test_missing_number(self):
        assert pm._is_unblocked([99], {}) is False


class TestBuildStatusMap:
    def test_maps_issue_numbers_across_levels(self):
        m = pm.build_status_map_from_backlog(SAMPLE_BACKLOG)
        # Parents AND sub-issues contribute, keyed by issue_number (int).
        assert m[101] == "In Progress"
        assert m[201] == "Done"
        assert m[202] == "Backlog"
        assert m[203] == "Backlog"

    def test_items_without_number_skipped(self):
        backlog = {"stories": [{"title": "X", "status": "Backlog", "tasks": []}]}
        assert pm.build_status_map_from_backlog(backlog) == {}


# ---------------------------------------------------------------------------
# I/O methods
# ---------------------------------------------------------------------------


class TestLoadBacklog:
    def test_existing(self, backlog_file):
        data = ProjectManager(backlog_file).load_backlog()
        assert data["project"] == "Test"
        assert len(data["stories"]) == 2

    def test_missing(self, tmp_path):
        data = ProjectManager(tmp_path / "missing.json").load_backlog()
        assert data["stories"] == []
        assert data["description"] == ""
        assert "goal" not in data


class TestSaveBacklog:
    def test_save_and_reload(self, tmp_path):
        p = tmp_path / "backlog.json"
        ProjectManager(p).save_backlog({"project": "X", "stories": []})
        loaded = json.loads(p.read_text(encoding="utf-8"))
        assert loaded["project"] == "X"

    def test_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "sub" / "dir" / "backlog.json"
        ProjectManager(p).save_backlog({"stories": []})
        assert p.exists()


class TestLoadAllItems:
    def test_counts(self, pm_instance):
        # 2 stories + 3 sub-issues
        assert len(pm_instance.load_all_items()) == 5

    def test_stories_first(self, pm_instance):
        items = pm_instance.load_all_items()
        assert items[0]["title"] == "Research feature X"
        assert items[1]["title"] == "Project setup"

    def test_subissues_get_parent_title(self, pm_instance):
        items = pm_instance.load_all_items()
        ci = next(i for i in items if i["title"] == "Setup CI pipeline")
        bug = next(i for i in items if i["title"] == "Fix login bug")
        assert ci["parent_id"] == "Research feature X"
        assert bug["parent_id"] == "Project setup"

    def test_subissue_status_is_real(self, pm_instance):
        items = pm_instance.load_all_items()
        ci = next(i for i in items if i["title"] == "Setup CI pipeline")
        auth = next(i for i in items if i["title"] == "Add auth module")
        assert ci["status"] == "Done"
        assert auth["status"] == "Backlog"


# ---------------------------------------------------------------------------
# list_items
# ---------------------------------------------------------------------------


class TestCmdList:
    def test_list_all(self, pm_instance, capsys):
        assert pm_instance.list_items() == 0
        out = capsys.readouterr().out
        assert "Research feature X" in out
        assert "Setup CI pipeline" in out
        assert "5 task(s)" in out

    def test_filter_by_status_done(self, pm_instance, capsys):
        pm_instance.list_items(status="Done")
        out = capsys.readouterr().out
        # Only "Setup CI pipeline" is Done.
        assert "Setup CI pipeline" in out
        assert "1 task(s)" in out

    def test_filter_by_priority(self, pm_instance, capsys):
        pm_instance.list_items(priority="P0")
        out = capsys.readouterr().out
        assert "Research feature X" in out
        assert "Fix login bug" in out

    def test_wide_shows_size_and_points(self, pm_instance, capsys):
        pm_instance.list_items(wide=True)
        out = capsys.readouterr().out
        assert "SIZE" in out and "PTS" in out

    def test_no_type_column(self, pm_instance, capsys):
        pm_instance.list_items(wide=True)
        out = capsys.readouterr().out
        assert "TYPE" not in out

    def test_filter_by_story_title(self, pm_instance, capsys):
        pm_instance.list_items(subissues="Research feature X")
        out = capsys.readouterr().out
        assert "Setup CI pipeline" in out
        assert "Add auth module" in out
        assert "Fix login bug" not in out

    def test_filter_by_story_number(self, pm_instance, capsys):
        pm_instance.list_items(subissues="102")
        out = capsys.readouterr().out
        assert "Fix login bug" in out
        assert "Setup CI pipeline" not in out


# ---------------------------------------------------------------------------
# view
# ---------------------------------------------------------------------------


class TestCmdView:
    def test_view_raw(self, pm_instance, capsys):
        assert pm_instance.view(key="Research feature X", raw=True) == 0
        out = capsys.readouterr().out
        assert "Research feature X" in out
        assert "In Progress" in out

    def test_view_by_issue_number(self, pm_instance, capsys):
        assert pm_instance.view(key="101", raw=True) == 0
        assert "Research feature X" in capsys.readouterr().out

    def test_view_not_found(self, pm_instance):
        assert pm_instance.view(key="nope") == 1

    def test_view_story_shows_children(self, pm_instance, capsys):
        pm_instance.view(key="Research feature X", raw=True)
        out = capsys.readouterr().out
        assert "Child tasks" in out
        assert "Setup CI pipeline" in out
        assert "Add auth module" in out

    def test_view_ac_only(self, pm_instance, capsys):
        assert pm_instance.view(key="Research feature X", ac=True) == 0
        out = capsys.readouterr().out
        assert "AC1" in out and "AC2" in out

    def test_view_ready_tasks_excludes_done(self, pm_instance, capsys):
        # "Setup CI pipeline" is Done; only "Add auth module" is ready.
        assert pm_instance.view(key="Research feature X", ready_tasks=True) == 0
        out = capsys.readouterr().out
        assert "Add auth module" in out
        assert "Setup CI pipeline" not in out


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


class TestCmdSummary:
    def test_by_status(self, pm_instance, capsys):
        assert pm_instance.summary(group_by="status") == 0
        assert "Summary by status" in capsys.readouterr().out

    def test_by_priority(self, pm_instance, capsys):
        assert pm_instance.summary(group_by="priority") == 0
        out = capsys.readouterr().out
        assert "Summary by priority" in out
        assert "P0" in out


# ---------------------------------------------------------------------------
# add_issue — lean top-level item
# ---------------------------------------------------------------------------


class TestAddStory:
    def test_adds_lean_item(self, backlog_file, capsys):
        pm_inst = ProjectManager(backlog_file)
        assert pm_inst.add_issue(title="New story") == 0
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert len(data["stories"]) == 3
        new = data["stories"][-1]
        assert new["title"] == "New story"
        assert new["status"] == "Backlog"
        assert new["priority"] == ""
        assert new["tasks"] == []
        assert new["issue_number"] is None
        assert new["acceptance_criteria"] == []
        assert new["labels"] == []
        assert new["blocked_by"] == []
        assert new["points"] is None
        assert "Added issue" in capsys.readouterr().out

    def test_no_id_or_type(self, backlog_file):
        ProjectManager(backlog_file).add_issue(title="X")
        new = json.loads(backlog_file.read_text(encoding="utf-8"))["stories"][-1]
        assert "id" not in new and "type" not in new

    def test_carries_description(self, backlog_file):
        ProjectManager(backlog_file).add_issue(title="X", description="Why X.")
        new = json.loads(backlog_file.read_text(encoding="utf-8"))["stories"][-1]
        assert new["description"] == "Why X."

    def test_description_defaults_empty(self, backlog_file):
        ProjectManager(backlog_file).add_issue(title="X")
        new = json.loads(backlog_file.read_text(encoding="utf-8"))["stories"][-1]
        assert new["description"] == ""

    def test_rejects_duplicate_title(self, backlog_file, capsys):
        rc = ProjectManager(backlog_file).add_issue(title="Research feature X")
        assert rc == 1
        assert "uplicate" in capsys.readouterr().err

    def test_rejects_duplicate_subissue_title(self, backlog_file, capsys):
        # Title uniqueness is global across parents + children.
        rc = ProjectManager(backlog_file).add_issue(title="Fix login bug")
        assert rc == 1


# ---------------------------------------------------------------------------
# add_subissue — lean child item (leaf)
# ---------------------------------------------------------------------------


class TestAddTask:
    def test_adds_child_item(self, backlog_file, capsys):
        pm_inst = ProjectManager(backlog_file)
        assert pm_inst.add_subissue(story="Research feature X", title="New task") == 0
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        sk = data["stories"][0]
        assert len(sk["tasks"]) == 3
        new = sk["tasks"][-1]
        assert new["title"] == "New task"
        assert new["status"] == "Backlog"
        assert new["issue_number"] is None
        assert "Added sub-issue" in capsys.readouterr().out

    def test_resolves_parent_by_number(self, backlog_file):
        ProjectManager(backlog_file).add_subissue(story="102", title="Child via num")
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        ps = next(s for s in data["stories"] if s["issue_number"] == 102)
        assert ps["tasks"][-1]["title"] == "Child via num"

    def test_child_is_leaf_no_tasks_key(self, backlog_file):
        ProjectManager(backlog_file).add_subissue(story="Project setup", title="Leaf")
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        new = data["stories"][1]["tasks"][-1]
        assert "tasks" not in new

    def test_carries_description(self, backlog_file):
        ProjectManager(backlog_file).add_subissue(
            story="Research feature X", title="Y", description="Why Y.",
        )
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][0]["tasks"][-1]["description"] == "Why Y."

    def test_parent_not_found(self, backlog_file, capsys):
        rc = ProjectManager(backlog_file).add_subissue(story="nope", title="X")
        assert rc == 1
        assert "not found" in capsys.readouterr().err

    def test_rejects_nesting_under_subissue(self, backlog_file, capsys):
        # Sub-issues are leaves — can't attach a task under one.
        rc = ProjectManager(backlog_file).add_subissue(story="Add auth module", title="X")
        assert rc == 1

    def test_rejects_duplicate_title(self, backlog_file):
        rc = ProjectManager(backlog_file).add_subissue(
            story="Research feature X", title="Project setup",
        )
        assert rc == 1


# ---------------------------------------------------------------------------
# update — any item (parent or sub-issue), full groom field set
# ---------------------------------------------------------------------------


class TestUpdateStory:
    def test_status(self, backlog_file):
        # "Research feature X" is In Progress; In Progress → Done is valid.
        assert ProjectManager(backlog_file).update(
            key="Research feature X", status="Done") == 0
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][0]["status"] == "Done"

    def test_priority(self, backlog_file):
        ProjectManager(backlog_file).update(key="Project setup", priority="P0")
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][1]["priority"] == "P0"

    def test_groom_fields(self, backlog_file):
        ProjectManager(backlog_file).update(
            key="Project setup", goal="ship it", notes="careful",
            size="L", points=5, start_date="2026-02-01", end_date="2026-02-05",
        )
        s = json.loads(backlog_file.read_text(encoding="utf-8"))["stories"][1]
        assert s["goal"] == "ship it"
        assert s["notes"] == "careful"
        assert s["size"] == "L"
        assert s["points"] == 5
        assert s["start_date"] == "2026-02-01"
        assert s["end_date"] == "2026-02-05"

    def test_list_fields(self, backlog_file):
        ProjectManager(backlog_file).update(
            key="Project setup", labels=["infra", "p0"],
            acceptance_criteria=["done when green"],
        )
        s = json.loads(backlog_file.read_text(encoding="utf-8"))["stories"][1]
        assert s["labels"] == ["infra", "p0"]
        assert s["acceptance_criteria"] == ["done when green"]

    def test_not_found(self, backlog_file, capsys):
        assert ProjectManager(backlog_file).update(key="nope", status="Done") == 1
        assert "not found" in capsys.readouterr().err

    def test_nothing_to_update(self, backlog_file, capsys):
        assert ProjectManager(backlog_file).update(key="Project setup") == 1
        assert "Nothing to update" in capsys.readouterr().err


class TestUpdateSubIssue:
    def test_groom_fields_on_subissue(self, backlog_file):
        # Sub-issues are first-class items now — groom them directly.
        ProjectManager(backlog_file).update(
            key="Add auth module", priority="P0", goal="auth done",
            size="S", points=2, labels=["auth"],
            acceptance_criteria=["login works"],
        )
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        child = data["stories"][0]["tasks"][1]
        assert child["priority"] == "P0"
        assert child["goal"] == "auth done"
        assert child["size"] == "S"
        assert child["points"] == 2
        assert child["labels"] == ["auth"]
        assert child["acceptance_criteria"] == ["login works"]

    def test_status_on_subissue(self, backlog_file):
        # "Add auth module" is Backlog → In Progress valid.
        assert ProjectManager(backlog_file).update(
            key="Add auth module", status="In Progress") == 0
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][0]["tasks"][1]["status"] == "In Progress"

    def test_update_subissue_by_number(self, backlog_file):
        ProjectManager(backlog_file).update(key="202", title="Auth (renamed)")
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][0]["tasks"][1]["title"] == "Auth (renamed)"


class TestUpdateGuardrail:
    def test_invalid_blocked(self, backlog_file, capsys):
        # "Project setup" is Backlog; Backlog → Done is not allowed.
        assert ProjectManager(backlog_file).update(
            key="Project setup", status="Done") == 1
        assert "Cannot move" in capsys.readouterr().err

    def test_force_bypass(self, backlog_file):
        assert ProjectManager(backlog_file).update(
            key="Project setup", status="Done", force=True) == 0
        data = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][1]["status"] == "Done"

    def test_subissue_transition_guard(self, backlog_file, capsys):
        # "Fix login bug" is Backlog; Backlog → Done blocked.
        assert ProjectManager(backlog_file).update(
            key="Fix login bug", status="Done") == 1
        assert "Cannot move" in capsys.readouterr().err

    def test_non_status_no_guardrail(self, backlog_file):
        assert ProjectManager(backlog_file).update(
            key="Project setup", priority="P0") == 0


# ---------------------------------------------------------------------------
# progress — real per-story done ratios from child status
# ---------------------------------------------------------------------------


class TestProgress:
    def test_header(self, pm_instance, capsys):
        pm_instance.progress()
        out = capsys.readouterr().out
        assert "Test - Test description" in out

    def test_overall_done_ratio(self, pm_instance, capsys):
        assert pm_instance.progress() == 0
        out = capsys.readouterr().out
        # Child items: "Setup CI pipeline" Done; the other 2 Backlog → 1/3.
        assert "1/3" in out
        assert "33%" in out

    def test_story_status_distribution(self, pm_instance, capsys):
        pm_instance.progress()
        assert "Story status distribution:" in capsys.readouterr().out

    def test_per_story_done_ratio(self, pm_instance, capsys):
        pm_instance.progress()
        out = capsys.readouterr().out
        assert "Per-story task completion:" in out
        # "Research feature X" has 1 of 2 children Done.
        assert "Research feature X" in out
        assert "1/2" in out
        # "Project setup" has 0 of 1 children Done.
        assert "0/1" in out

    def test_empty(self, tmp_path, capsys):
        ProjectManager(tmp_path / "backlog.json").progress()
        assert "No tasks" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# resolve / ready — derivation (Backlog+unblocked → Ready) and listing
# ---------------------------------------------------------------------------


def _ready_story(title, *, priority=None, status="Backlog",
                 blocked_by=None, issue_number=None):
    return {
        "title": title, "status": status, "priority": priority,
        "blocked_by": list(blocked_by or []), "issue_number": issue_number,
        "tasks": [],
    }


def _ready_backlog_with(stories):
    return {"project": "T", "stories": stories}


SAMPLE_BACKLOG_RESOLVE: dict = {
    "project": "T",
    "stories": [
        {
            "title": "Story A", "status": "Done", "priority": "P0",
            "blocked_by": [], "issue_number": 1,
            "tasks": [
                _child("Task A", "", "Backlog", issue_number=11),
                _child("Task C", "", "Done", issue_number=12),
            ],
        },
        {
            "title": "Story B", "status": "Backlog", "priority": "P1",
            "blocked_by": [1], "issue_number": 2, "tasks": [],
        },
        {
            "title": "Story C", "status": "Backlog", "priority": "P2",
            "blocked_by": [2], "issue_number": 3, "tasks": [],
        },
    ],
}


@pytest.fixture
def resolve_backlog_file(tmp_path):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(SAMPLE_BACKLOG_RESOLVE), encoding="utf-8")
    return p


class TestResolve:
    def test_promotes_unblocked_backlog_to_ready(self, resolve_backlog_file, capsys):
        # Story B (Backlog, blocked only by Done #1) resolves to Ready.
        assert ProjectManager(resolve_backlog_file).resolve() == 0
        data = json.loads(resolve_backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][1]["status"] == "Ready"     # Story B
        assert data["stories"][2]["status"] == "Backlog"   # Story C still blocked
        assert data["stories"][0]["status"] == "Done"      # Story A untouched
        assert "Resolved 1 item(s) to Ready." in capsys.readouterr().out

    def test_blocked_story_stays_backlog(self, resolve_backlog_file):
        ProjectManager(resolve_backlog_file).resolve()
        data = json.loads(resolve_backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][2]["status"] == "Backlog"

    def test_subissues_never_resolved(self, resolve_backlog_file):
        ProjectManager(resolve_backlog_file).resolve()
        data = json.loads(resolve_backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][0]["tasks"][0]["status"] == "Backlog"  # Task A

    def test_filter_by_story_number(self, resolve_backlog_file):
        # Narrow to Story C (#3) — still blocked, so Story B is left alone.
        ProjectManager(resolve_backlog_file).resolve(story="3")
        data = json.loads(resolve_backlog_file.read_text(encoding="utf-8"))
        assert data["stories"][1]["status"] == "Backlog"

    def test_top_resolves_single(self, tmp_path):
        backlog = _ready_backlog_with([
            _ready_story("Zeta", priority="P2"),
            _ready_story("Alpha", priority="P0"),
        ])
        p = tmp_path / "b.json"; p.write_text(json.dumps(backlog), encoding="utf-8")
        ProjectManager(p).resolve(top=True)
        statuses = {s["title"]: s["status"]
                    for s in json.loads(p.read_text(encoding="utf-8"))["stories"]}
        assert statuses == {"Alpha": "Ready", "Zeta": "Backlog"}

    def test_nothing_to_resolve(self, tmp_path, capsys):
        data = {"stories": [
            {"title": "S", "status": "Done", "blocked_by": [],
             "issue_number": 1, "tasks": []},
        ]}
        p = tmp_path / "b.json"; p.write_text(json.dumps(data), encoding="utf-8")
        assert ProjectManager(p).resolve() == 0
        assert "No backlog items to resolve." in capsys.readouterr().out


SAMPLE_BACKLOG_READY: dict = {
    "project": "T",
    "stories": [
        {
            "title": "Story A", "status": "Done", "priority": "P0",
            "blocked_by": [], "issue_number": 1,
            "tasks": [_child("Task A", "", "Ready", issue_number=11)],
        },
        {
            "title": "Story B", "status": "Ready", "priority": "P1",
            "blocked_by": [], "issue_number": 2, "tasks": [],
        },
        {
            "title": "Story C", "status": "Backlog", "priority": "P2",
            "blocked_by": [], "issue_number": 3, "tasks": [],
        },
    ],
}


@pytest.fixture
def ready_backlog_file(tmp_path):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(SAMPLE_BACKLOG_READY), encoding="utf-8")
    return p


@pytest.fixture
def ready_pm(ready_backlog_file):
    return ProjectManager(ready_backlog_file)


class TestReady:
    def test_lists_only_ready_status(self, ready_pm, capsys):
        assert ready_pm.ready() == 0
        out = capsys.readouterr().out
        assert "Story B" in out        # status Ready
        assert "Story A" not in out    # Done
        assert "Story C" not in out    # Backlog
        assert "Task A" not in out     # sub-issues never listed

    def test_filter_by_story_number(self, ready_pm, capsys):
        ready_pm.ready(story="2")
        assert "Story B" in capsys.readouterr().out

    def test_no_items(self, tmp_path, capsys):
        data = {"stories": [
            {"title": "S", "status": "Backlog", "blocked_by": [],
             "issue_number": 1, "tasks": []},
        ]}
        p = tmp_path / "b.json"; p.write_text(json.dumps(data), encoding="utf-8")
        assert ProjectManager(p).ready() == 0
        assert "No ready stories found." in capsys.readouterr().out

    def test_json_output(self, ready_pm, capsys):
        assert ready_pm.ready(json=True) == 0
        parsed = json.loads(capsys.readouterr().out)
        assert [item["title"] for item in parsed] == ["Story B"]
        for item in parsed:
            for req in ("title", "issue_number", "status", "blocked_by"):
                assert req in item

    def test_ready_has_no_promote_param(self):
        # Promotion moved to `resolve`; `ready` is read-only now.
        import inspect
        assert "promote" not in inspect.signature(ProjectManager.ready).parameters


class TestReadySort:
    def test_priority_sorts_first(self, tmp_path, capsys):
        backlog = _ready_backlog_with([
            _ready_story("Zeta", priority="P2", status="Ready"),
            _ready_story("Alpha", priority="P0", status="Ready"),
        ])
        p = tmp_path / "b.json"; p.write_text(json.dumps(backlog), encoding="utf-8")
        ProjectManager(p).ready(json=True)
        titles = [s["title"] for s in json.loads(capsys.readouterr().out)]
        assert titles == ["Alpha", "Zeta"]

    def test_title_breaks_priority_tie(self, tmp_path, capsys):
        backlog = _ready_backlog_with([
            _ready_story("Beta", priority="P1", status="Ready"),
            _ready_story("Alpha", priority="P1", status="Ready"),
        ])
        p = tmp_path / "b.json"; p.write_text(json.dumps(backlog), encoding="utf-8")
        ProjectManager(p).ready(json=True)
        titles = [s["title"] for s in json.loads(capsys.readouterr().out)]
        assert titles == ["Alpha", "Beta"]


class TestReadyTop:
    def test_top_returns_single_top_ranked(self, tmp_path, capsys):
        backlog = _ready_backlog_with([
            _ready_story("Zeta", priority="P2", status="Ready"),
            _ready_story("Alpha", priority="P0", status="Ready"),
            _ready_story("Mid", priority="P1", status="Ready"),
        ])
        p = tmp_path / "b.json"; p.write_text(json.dumps(backlog), encoding="utf-8")
        ProjectManager(p).ready(top=True, json=True)
        parsed = json.loads(capsys.readouterr().out)
        assert [s["title"] for s in parsed] == ["Alpha"]


# ---------------------------------------------------------------------------
# run() dispatcher
# ---------------------------------------------------------------------------


class TestRun:
    def test_list(self, pm_instance, capsys):
        assert pm_instance.run("list") == 0
        assert "5 task(s)" in capsys.readouterr().out

    def test_ls_alias(self, pm_instance, capsys):
        assert pm_instance.run("ls") == 0
        assert "5 task(s)" in capsys.readouterr().out

    def test_progress(self, pm_instance, capsys):
        assert pm_instance.run("progress") == 0
        assert "Test description" in capsys.readouterr().out

    def test_view_kwargs(self, pm_instance, capsys):
        assert pm_instance.run("view", key="Research feature X", raw=True) == 0
        assert "Research feature X" in capsys.readouterr().out

    def test_pull_is_registered(self, pm_instance):
        assert pm_instance._COMMAND_MAP["pull"] == "pull"

    def test_resolve_is_registered(self, pm_instance):
        assert pm_instance._COMMAND_MAP["resolve"] == "resolve"

    def test_resolve_dispatch(self, pm_instance, capsys):
        # SAMPLE_BACKLOG's "Project setup" is an unblocked Backlog story.
        assert pm_instance.run("resolve") == 0
        assert "Resolved" in capsys.readouterr().out

    def test_unknown_command(self, pm_instance):
        with pytest.raises(ValueError, match="Unknown command"):
            pm_instance.run("does-not-exist")
