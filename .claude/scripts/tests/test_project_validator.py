"""Tests for lib.project_validator — schema validation for backlog.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.project_validator import validate_project  # type: ignore


# ---------------------------------------------------------------------------
# Fixture builders — tiny helpers so each test states only what it changes.
# ---------------------------------------------------------------------------


def _task(**overrides) -> dict:
    """Return a minimal valid task dict; *overrides* mutate fields."""
    base = {
        "id": "T-001",
        "type": "task",
        "labels": [],
        "title": "Run analysis",
        "description": "Compute features",
        "status": "Backlog",
        "priority": "P1",
        "complexity": "M",
        "acceptance_criteria": ["one"],
        "item_type": "task",
        "parent_story_id": "SK-001",
        "milestone": "v0.1.0",
    }
    base.update(overrides)
    return base


def _story(**overrides) -> dict:
    """Return a minimal valid Spike story dict; *overrides* mutate fields."""
    base = {
        "id": "SK-001",
        "type": "Spike",
        "milestone": "v0.1.0",
        "labels": ["spike"],
        "title": "Research feature X",
        "description": "...",
        "points": 2,
        "status": "Backlog",
        "tdd": True,
        "priority": "P0",
        "is_blocking": [],
        "blocked_by": [],
        "acceptance_criteria": ["criterion 1"],
        "start_date": "2026-02-17",
        "target_date": "2026-02-21",
        "tasks": [],
        "item_type": "story",
    }
    base.update(overrides)
    return base


def _project(**overrides) -> dict:
    """Return a minimal valid project dict; *overrides* mutate fields."""
    base = {
        "project": "Avaris",
        "goal": "Foundational ML pipeline",
        "dates": {"start": "2026-02-17", "end": "2026-03-02"},
        "totalPoints": 2,
        "stories": [_story()],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Top-level structure
# ---------------------------------------------------------------------------


class TestTopLevel:
    def test_valid_minimal_project_has_no_errors(self) -> None:
        assert validate_project(_project()) == []

    def test_non_dict_root_is_rejected(self) -> None:
        errors = validate_project([])  # type: ignore[arg-type]
        assert any("must be an object" in e for e in errors)

    def test_missing_top_level_keys_are_reported(self) -> None:
        errors = validate_project({})
        # Each missing required top-level key surfaces independently.
        for field in ("project", "goal", "dates", "totalPoints", "stories"):
            assert any(field in e for e in errors), f"missing report for {field}"

    def test_dates_object_must_have_start_and_end(self) -> None:
        errors = validate_project(_project(dates={"start": "2026-02-17"}))
        assert any("dates.end" in e for e in errors)

    def test_stories_must_be_a_list(self) -> None:
        errors = validate_project(_project(stories={}))
        assert any("stories" in e and "list" in e for e in errors)


# ---------------------------------------------------------------------------
# Story-level rules
# ---------------------------------------------------------------------------


class TestStoryRules:
    def test_invalid_status_value_is_rejected(self) -> None:
        errors = validate_project(_project(stories=[_story(status="done")]))
        assert any("status" in e and "done" in e for e in errors)

    def test_invalid_priority_value_is_rejected(self) -> None:
        errors = validate_project(_project(stories=[_story(priority="P9")]))
        assert any("priority" in e and "P9" in e for e in errors)

    def test_id_prefix_must_match_type(self) -> None:
        # Spike must use SK- prefix; US- belongs to User Story.
        errors = validate_project(
            _project(stories=[_story(id="US-001", type="Spike")])
        )
        assert any("US-001" in e and "Spike" in e for e in errors)

    def test_unknown_story_type_is_rejected(self) -> None:
        errors = validate_project(_project(stories=[_story(type="Epic")]))
        assert any("type" in e and "Epic" in e for e in errors)

    def test_story_must_not_carry_complexity(self) -> None:
        # complexity is a task-only field per the schema rules.
        story = _story()
        story["complexity"] = "M"
        errors = validate_project(_project(stories=[story]))
        assert any("complexity" in e and "SK-001" in e for e in errors)

    def test_blocked_by_must_reference_existing_story(self) -> None:
        errors = validate_project(
            _project(stories=[_story(blocked_by=["TS-999"])])
        )
        assert any("TS-999" in e and "blocked_by" in e for e in errors)


# ---------------------------------------------------------------------------
# Task-level rules
# ---------------------------------------------------------------------------


class TestTaskRules:
    def test_task_id_must_use_T_prefix(self) -> None:
        errors = validate_project(
            _project(stories=[_story(tasks=[_task(id="X-001")])])
        )
        assert any("X-001" in e and "T-" in e for e in errors)

    def test_task_must_not_carry_story_only_fields(self) -> None:
        # points / tdd / is_blocking / blocked_by belong on stories only.
        bad = _task()
        bad["points"] = 3
        bad["tdd"] = True
        errors = validate_project(_project(stories=[_story(tasks=[bad])]))
        assert any("points" in e and "T-001" in e for e in errors)
        assert any("tdd" in e and "T-001" in e for e in errors)

    def test_task_parent_story_id_must_match_owner(self) -> None:
        # Task is nested under SK-001 but claims a different parent.
        errors = validate_project(
            _project(stories=[_story(tasks=[_task(parent_story_id="SK-999")])])
        )
        assert any(
            "parent_story_id" in e and "SK-999" in e for e in errors
        )

    def test_task_invalid_complexity_is_rejected(self) -> None:
        errors = validate_project(
            _project(stories=[_story(tasks=[_task(complexity="HUGE")])])
        )
        assert any("complexity" in e and "HUGE" in e for e in errors)


# ---------------------------------------------------------------------------
# Cross-cutting: real backlog file passes
# ---------------------------------------------------------------------------


class TestRealBacklog:
    def test_repo_backlog_json_is_valid(self) -> None:
        # Regression guard: the checked-in backlog must satisfy the schema.
        path = (
            Path(__file__).resolve().parents[2]
            / "project_manager"
            / "project"
            / "backlog.json"
        )
        if not path.is_file():
            pytest.skip(f"backlog not present at {path}")
        data = json.loads(path.read_text())
        errors = validate_project(data)
        assert errors == [], f"real backlog has schema errors: {errors[:5]}"
