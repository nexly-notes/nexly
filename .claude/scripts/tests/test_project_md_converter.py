"""Tests for lib.project_md_converter — JSON → Markdown rendering."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.project_md_converter import project_json_to_md  # type: ignore


# ---------------------------------------------------------------------------
# Fixture builders — keep each test focused on one observable difference.
# ---------------------------------------------------------------------------


def _task(**overrides) -> dict:
    base = {
        "id": "T-001",
        "type": "task",
        "labels": ["analysis"],
        "title": "Run analysis",
        "description": "Compute features",
        "status": "Backlog",
        "priority": "P1",
        "complexity": "M",
        "acceptance_criteria": ["scores logged"],
        "item_type": "task",
        "parent_story_id": "SK-001",
        "milestone": "v0.1.0",
    }
    base.update(overrides)
    return base


def _story(**overrides) -> dict:
    base = {
        "id": "SK-001",
        "type": "Spike",
        "milestone": "v0.1.0",
        "labels": ["spike", "research"],
        "title": "Research feature X",
        "description": "Detailed body of the spike.",
        "points": 2,
        "status": "Ready",
        "tdd": True,
        "priority": "P0",
        "is_blocking": ["TS-002"],
        "blocked_by": [],
        "acceptance_criteria": ["criterion 1", "criterion 2"],
        "start_date": "2026-02-17",
        "target_date": "2026-02-21",
        "tasks": [],
        "item_type": "story",
    }
    base.update(overrides)
    return base


def _project(**overrides) -> dict:
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
# Header section
# ---------------------------------------------------------------------------


class TestHeader:
    def test_header_contains_project_name_as_h1(self) -> None:
        md = project_json_to_md(_project())
        assert "# Project: Avaris" in md

    def test_header_includes_goal(self) -> None:
        md = project_json_to_md(_project())
        assert "Foundational ML pipeline" in md

    def test_header_includes_dates_and_total_points(self) -> None:
        md = project_json_to_md(_project())
        assert "2026-02-17" in md and "2026-03-02" in md
        assert "Total points" in md and "2" in md


# ---------------------------------------------------------------------------
# Story rendering
# ---------------------------------------------------------------------------


class TestStorySection:
    def test_story_uses_h2_with_id_and_title(self) -> None:
        md = project_json_to_md(_project())
        assert "## SK-001 — Research feature X" in md

    def test_story_metadata_line_has_core_fields(self) -> None:
        md = project_json_to_md(_project())
        # Type, priority, status, points, milestone all on one line.
        meta_lines = [ln for ln in md.splitlines() if "Type" in ln and "Priority" in ln]
        assert meta_lines, "expected a metadata line with Type and Priority"
        line = meta_lines[0]
        for token in ("Spike", "P0", "Ready", "2", "v0.1.0"):
            assert token in line, f"missing '{token}' in metadata line"

    def test_acceptance_criteria_render_as_bullets(self) -> None:
        md = project_json_to_md(_project())
        assert "### Acceptance criteria" in md
        assert "- criterion 1" in md
        assert "- criterion 2" in md

    def test_blocked_by_empty_renders_em_dash(self) -> None:
        md = project_json_to_md(_project())
        # Empty blocked_by should not produce a list of IDs; show '—' instead.
        line = next(ln for ln in md.splitlines() if "Blocked by" in ln)
        assert "—" in line

    def test_is_blocking_lists_referenced_ids(self) -> None:
        md = project_json_to_md(_project())
        line = next(ln for ln in md.splitlines() if "Is blocking" in ln)
        assert "TS-002" in line

    def test_description_appears_in_section(self) -> None:
        md = project_json_to_md(_project())
        assert "Detailed body of the spike." in md


# ---------------------------------------------------------------------------
# Tasks subsection
# ---------------------------------------------------------------------------


class TestTasksSubsection:
    def test_no_tasks_omits_tasks_heading(self) -> None:
        md = project_json_to_md(_project(stories=[_story(tasks=[])]))
        assert "### Tasks" not in md

    def test_tasks_render_as_checkbox_bullets(self) -> None:
        md = project_json_to_md(
            _project(stories=[_story(tasks=[_task()])])
        )
        assert "### Tasks" in md
        # Backlog/Ready/In progress/In review → unchecked checkbox.
        assert "- [ ] T-001" in md
        assert "Run analysis" in md

    def test_done_task_uses_checked_checkbox(self) -> None:
        md = project_json_to_md(
            _project(stories=[_story(tasks=[_task(status="Done")])])
        )
        assert "- [x] T-001" in md

    def test_task_line_includes_priority_complexity_and_status(self) -> None:
        md = project_json_to_md(
            _project(stories=[_story(tasks=[_task()])])
        )
        task_line = next(ln for ln in md.splitlines() if "T-001" in ln)
        for token in ("P1", "M", "Backlog"):
            assert token in task_line, f"missing '{token}' in task line"


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


class TestRealBacklog:
    def test_repo_backlog_json_renders_without_error(self) -> None:
        path = (
            Path(__file__).resolve().parents[2]
            / "project_manager"
            / "project"
            / "backlog.json"
        )
        if not path.is_file():
            pytest.skip(f"backlog not present at {path}")
        data = json.loads(path.read_text())
        md = project_json_to_md(data)
        assert md.startswith("# Project:")
        # Every story heading should appear in the output.
        for story in data["stories"]:
            assert f"## {story['id']}" in md
