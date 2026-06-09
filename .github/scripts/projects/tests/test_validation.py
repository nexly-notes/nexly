"""Tests for projects.validation — the lenient backlog schema.

Required per story: ``title`` (unique, non-empty), ``description`` (non-empty),
``priority`` (enum). Grooming fields are validated only when present.
``blocked_by`` references stories by issue number.
"""
from __future__ import annotations

import copy
import json

import pytest

from projects import config, validation


# A fully groomed, post-convert backlog: every field present, issue numbers
# minted, and story B blocked by story A's issue number.
_VALID_BACKLOG: dict = {
    "project": "NEXLY RN",
    "description": "Ship the two-mode (Write + Study) MVP for nursing students",
    "dates": {"start": "2026-02-17", "end": "2026-03-16"},
    "stories": [
        {
            "title": "Supabase auth + per-user RLS baseline",
            "description": "Stand up Supabase auth and lock every table behind RLS.",
            "status": "Backlog",
            "priority": "P0",
            "goal": "Guarantee per-user isolation before any data feature.",
            "notes": "",
            "tasks": ["Enable Supabase auth", "Add RLS policies"],
            "acceptance_criteria": ["A user can only read their own notes"],
            "labels": ["feature", "backend"],
            "blocked_by": [],
            "size": "M",
            "points": 5,
            "issue_number": 101,
        },
        {
            "title": "Tiptap Write Mode editor shell",
            "description": "Build the minimal Write Mode editor on Tiptap.",
            "status": "Backlog",
            "priority": "P1",
            "goal": "Give students a fast capture surface.",
            "notes": "Autosave every 30s.",
            "tasks": ["Mount Tiptap", "Wire autosave"],
            "acceptance_criteria": ["Typing persists within 30s"],
            "labels": ["feature", "frontend"],
            "blocked_by": [101],
            "size": "L",
            "points": 8,
            "issue_number": 102,
        },
    ],
}

# A lean draft: only title / description / priority (+ status / issue_number).
_LEAN_BACKLOG: dict = {
    "project": "NEXLY RN",
    "description": "Lean draft for the MVP",
    "dates": {"start": "2026-02-17", "end": "2026-03-16"},
    "stories": [
        {
            "title": "Supabase auth + per-user RLS baseline",
            "description": "Stand up Supabase auth and lock every table behind RLS.",
            "priority": "P0",
        },
        {
            "title": "Tiptap Write Mode editor shell",
            "description": "Build the minimal Write Mode editor on Tiptap.",
            "priority": "P1",
        },
    ],
}


@pytest.fixture
def valid_data() -> dict:
    return copy.deepcopy(_VALID_BACKLOG)


@pytest.fixture
def lean_data() -> dict:
    return copy.deepcopy(_LEAN_BACKLOG)


# ── Root-level validation ──────────────────────────────────────────────────


class TestRootValidation:
    def test_valid_data_has_no_errors(self, valid_data):
        assert validation.validate(valid_data) == []

    def test_missing_project(self, valid_data):
        del valid_data["project"]
        assert any("'project'" in e for e in validation.validate(valid_data))

    def test_missing_description(self, valid_data):
        del valid_data["description"]
        assert any("'description'" in e for e in validation.validate(valid_data))

    def test_missing_dates(self, valid_data):
        del valid_data["dates"]
        assert any("'dates'" in e for e in validation.validate(valid_data))

    def test_missing_dates_start(self, valid_data):
        del valid_data["dates"]["start"]
        assert any("'start'" in e for e in validation.validate(valid_data))

    def test_invalid_date_format(self, valid_data):
        valid_data["dates"]["start"] = "March 2026"
        assert any("YYYY-MM-DD" in e for e in validation.validate(valid_data))

    def test_missing_stories(self, valid_data):
        del valid_data["stories"]
        assert any("'stories'" in e for e in validation.validate(valid_data))

    def test_stories_wrong_type(self, valid_data):
        valid_data["stories"] = "nope"
        assert any("stories" in e for e in validation.validate(valid_data))


# ── Lean backlog (grooming optional) ───────────────────────────────────────


class TestLeanBacklog:
    def test_lean_backlog_passes(self, lean_data):
        # title / description / priority only — grooming is optional now.
        assert validation.validate(lean_data) == []

    def test_lean_missing_priority_fails(self, lean_data):
        del lean_data["stories"][0]["priority"]
        assert any("'priority'" in e for e in validation.validate(lean_data))

    def test_lean_missing_title_fails(self, lean_data):
        del lean_data["stories"][0]["title"]
        assert any("'title'" in e for e in validation.validate(lean_data))

    def test_lean_missing_description_fails(self, lean_data):
        del lean_data["stories"][0]["description"]
        assert any("'description'" in e for e in validation.validate(lean_data))


# ── Required fields (title / description / priority) ────────────────────────


class TestStoryRequired:
    def test_invalid_status(self, valid_data):
        valid_data["stories"][0]["status"] = "Frozen"
        assert any("Frozen" in e for e in validation.validate(valid_data))

    def test_status_inprogress_valid(self, valid_data):
        valid_data["stories"][0]["status"] = "In Progress"
        assert validation.validate(valid_data) == []

    def test_invalid_priority(self, valid_data):
        valid_data["stories"][0]["priority"] = "P9"
        assert any("P9" in e for e in validation.validate(valid_data))

    def test_missing_priority_is_required(self, valid_data):
        del valid_data["stories"][0]["priority"]
        assert any("'priority'" in e for e in validation.validate(valid_data))

    def test_missing_title(self, valid_data):
        del valid_data["stories"][0]["title"]
        assert any("'title'" in e for e in validation.validate(valid_data))

    def test_empty_title_fails(self, valid_data):
        valid_data["stories"][0]["title"] = "   "
        assert any("title" in e and "empty" in e for e in validation.validate(valid_data))

    def test_missing_description_is_required(self, valid_data):
        del valid_data["stories"][0]["description"]
        assert any("'description'" in e for e in validation.validate(valid_data))

    def test_empty_description_fails(self, valid_data):
        valid_data["stories"][0]["description"] = "   "
        assert any("description" in e and "empty" in e for e in validation.validate(valid_data))


# ── Title uniqueness (title is the re-link key) ─────────────────────────────


class TestTitleUniqueness:
    def test_duplicate_title_fails(self, valid_data):
        valid_data["stories"][1]["title"] = valid_data["stories"][0]["title"]
        assert any("duplicate title" in e for e in validation.validate(valid_data))

    def test_unique_titles_pass(self, valid_data):
        assert validation.validate(valid_data) == []


# ── Grooming fields validated only when present ─────────────────────────────


class TestGroomingWhenPresent:
    def test_missing_goal_passes(self, valid_data):
        del valid_data["stories"][0]["goal"]
        assert validation.validate(valid_data) == []

    def test_empty_goal_fails(self, valid_data):
        valid_data["stories"][0]["goal"] = "   "
        assert any("goal" in e and "empty" in e for e in validation.validate(valid_data))

    def test_goal_must_be_str(self, valid_data):
        valid_data["stories"][0]["goal"] = ["x"]
        assert any("goal" in e for e in validation.validate(valid_data))

    def test_missing_notes_passes(self, valid_data):
        del valid_data["stories"][0]["notes"]
        assert validation.validate(valid_data) == []

    def test_empty_notes_passes(self, valid_data):
        valid_data["stories"][0]["notes"] = ""
        assert validation.validate(valid_data) == []

    def test_notes_must_be_str(self, valid_data):
        valid_data["stories"][0]["notes"] = 5
        assert any("notes" in e for e in validation.validate(valid_data))

    def test_missing_tasks_passes(self, valid_data):
        del valid_data["stories"][0]["tasks"]
        assert validation.validate(valid_data) == []

    def test_empty_tasks_fails(self, valid_data):
        valid_data["stories"][0]["tasks"] = []
        assert any("tasks" in e and "at least one" in e for e in validation.validate(valid_data))

    def test_tasks_must_be_str_list(self, valid_data):
        valid_data["stories"][0]["tasks"] = [1, 2]
        assert any("tasks" in e for e in validation.validate(valid_data))

    def test_missing_acceptance_criteria_passes(self, valid_data):
        del valid_data["stories"][0]["acceptance_criteria"]
        assert validation.validate(valid_data) == []

    def test_empty_acceptance_criteria_fails(self, valid_data):
        valid_data["stories"][0]["acceptance_criteria"] = []
        assert any(
            "acceptance_criteria" in e and "at least one" in e
            for e in validation.validate(valid_data)
        )

    def test_acceptance_criteria_must_be_str_list(self, valid_data):
        valid_data["stories"][0]["acceptance_criteria"] = "not a list"
        assert any("acceptance_criteria" in e for e in validation.validate(valid_data))

    def test_missing_size_passes(self, valid_data):
        del valid_data["stories"][0]["size"]
        assert validation.validate(valid_data) == []

    def test_size_enum_enforced(self, valid_data):
        valid_data["stories"][0]["size"] = "HUGE"
        assert any("size" in e for e in validation.validate(valid_data))

    def test_missing_points_passes(self, valid_data):
        del valid_data["stories"][0]["points"]
        assert validation.validate(valid_data) == []

    def test_points_must_be_number(self, valid_data):
        valid_data["stories"][0]["points"] = "five"
        assert any("points" in e for e in validation.validate(valid_data))

    def test_points_bool_rejected(self, valid_data):
        valid_data["stories"][0]["points"] = True
        assert any("points" in e for e in validation.validate(valid_data))

    def test_points_float_ok(self, valid_data):
        valid_data["stories"][0]["points"] = 2.5
        assert validation.validate(valid_data) == []

    def test_missing_issue_number_passes(self, valid_data):
        del valid_data["stories"][0]["issue_number"]
        # story B references 101, which is now absent — drop that ref too.
        valid_data["stories"][1]["blocked_by"] = []
        assert validation.validate(valid_data) == []

    def test_issue_number_zero_passes(self, lean_data):
        # 0 is the not-yet-converted sentinel and must validate.
        lean_data["stories"][0]["issue_number"] = 0
        assert validation.validate(lean_data) == []

    def test_issue_number_must_be_int(self, valid_data):
        valid_data["stories"][0]["issue_number"] = "5"
        assert any("issue_number" in e for e in validation.validate(valid_data))


# ── labels (when present, must carry a work-type label) ─────────────────────


class TestLabels:
    def test_missing_labels_passes(self, valid_data):
        del valid_data["stories"][0]["labels"]
        assert validation.validate(valid_data) == []

    def test_empty_labels_fails(self, valid_data):
        valid_data["stories"][0]["labels"] = []
        assert any("labels" in e and "work-type" in e for e in validation.validate(valid_data))

    def test_labels_must_be_strings(self, valid_data):
        valid_data["stories"][0]["labels"] = [1, 2]
        assert any("labels" in e for e in validation.validate(valid_data))

    def test_only_domain_label_fails(self, valid_data):
        # A domain label alone does not type the issue.
        valid_data["stories"][0]["labels"] = ["backend"]
        assert any("labels" in e and "work-type" in e for e in validation.validate(valid_data))

    def test_work_type_plus_domain_passes(self, valid_data):
        valid_data["stories"][0]["labels"] = ["feature", "backend"]
        assert validation.validate(valid_data) == []

    def test_review_label_satisfies_rule(self, valid_data):
        # `review` is part of the work-type vocabulary.
        valid_data["stories"][0]["labels"] = ["review"]
        assert validation.validate(valid_data) == []


# ── blocked_by (issue numbers, closure-checked, no self-block) ──────────────


class TestBlockedByClosure:
    def test_missing_blocked_by_passes(self, valid_data):
        del valid_data["stories"][1]["blocked_by"]
        assert validation.validate(valid_data) == []

    def test_empty_blocked_by_passes(self, valid_data):
        valid_data["stories"][1]["blocked_by"] = []
        assert validation.validate(valid_data) == []

    def test_dangling_blocked_by_fails(self, valid_data):
        valid_data["stories"][1]["blocked_by"] = [999]
        errors = validation.validate(valid_data)
        assert any("#999" in e and "does not resolve" in e for e in errors)

    def test_resolvable_blocked_by_passes(self, valid_data):
        valid_data["stories"][1]["blocked_by"] = [101]
        assert validation.validate(valid_data) == []

    def test_blocked_by_must_be_ints(self, valid_data):
        valid_data["stories"][1]["blocked_by"] = ["NEXLY-001"]
        assert any("blocked_by" in e and "int" in e for e in validation.validate(valid_data))

    def test_blocked_by_bool_rejected(self, valid_data):
        valid_data["stories"][1]["blocked_by"] = [True]
        assert any("blocked_by" in e and "int" in e for e in validation.validate(valid_data))

    def test_self_block_fails(self, valid_data):
        valid_data["stories"][0]["blocked_by"] = [101]
        assert any(
            "may not block itself" in e for e in validation.validate(valid_data)
        )


# ── Stray unknown fields are ignored ───────────────────────────────────────


class TestStrayFields:
    def test_stray_unknown_fields_ignored(self, valid_data):
        valid_data["stories"][0]["subtasks"] = ["legacy"]
        valid_data["stories"][0]["type"] = "Spike"
        assert validation.validate(valid_data) == []


# ── CLI entrypoint (projects validate <path>) ──────────────────────────────


class TestRun:
    def test_valid_file_returns_zero(self, tmp_path, valid_data, capsys):
        path = tmp_path / "backlog.json"
        path.write_text(json.dumps(valid_data), encoding="utf-8")
        rc = validation.run(str(path))
        assert rc == 0
        assert "Backlog validation passed" in capsys.readouterr().out

    def test_lean_file_returns_zero(self, tmp_path, lean_data, capsys):
        path = tmp_path / "backlog.json"
        path.write_text(json.dumps(lean_data), encoding="utf-8")
        assert validation.run(str(path)) == 0
        assert "Backlog validation passed" in capsys.readouterr().out

    def test_invalid_file_returns_one_and_prints_errors(self, tmp_path, valid_data, capsys):
        valid_data["stories"][0]["priority"] = "P9"
        path = tmp_path / "backlog.json"
        path.write_text(json.dumps(valid_data), encoding="utf-8")
        rc = validation.run(str(path))
        assert rc == 1
        assert "P9" in capsys.readouterr().out

    def test_dangling_blocked_by_file_returns_one(self, tmp_path, valid_data, capsys):
        valid_data["stories"][1]["blocked_by"] = [404]
        path = tmp_path / "backlog.json"
        path.write_text(json.dumps(valid_data), encoding="utf-8")
        rc = validation.run(str(path))
        assert rc == 1
        assert "404" in capsys.readouterr().out

    def test_malformed_json_returns_one(self, tmp_path, capsys):
        path = tmp_path / "backlog.json"
        path.write_text("{not json", encoding="utf-8")
        rc = validation.run(str(path))
        assert rc == 1
        assert "Backlog validation passed" not in capsys.readouterr().out

    def test_missing_file_returns_one(self, tmp_path, capsys):
        rc = validation.run(str(tmp_path / "nope.json"))
        assert rc == 1
        assert "Backlog validation passed" not in capsys.readouterr().out


# ── Real shipped artifacts ─────────────────────────────────────────────────


class TestRealArtifacts:
    def test_sample_structure_is_valid(self):
        # The sample is the canonical groomed example — it must validate.
        path = config.REPO_ROOT / ".claude" / "skills" / "backlog" / "sample_structure.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert validation.validate(data) == []

    def test_real_backlog_validates(self):
        # The real backlog is a lean draft, which now validates under the
        # lenient schema (grooming optional).
        path = config.REPO_ROOT / "project" / "backlog.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert validation.validate(data) == []
