"""Tests for projects.backlog — pure file IO + issue-body building, no network."""
from __future__ import annotations

import json

import pytest

from projects import backlog


# ── Pure helpers ───────────────────────────────────────────────────────────


class TestItemTitle:
    def test_returns_bare_title(self):
        assert backlog._item_title({"title": "X"}) == "X"

    def test_ignores_any_stray_id(self):
        # The title is the issue title now — no id prefix is added.
        assert backlog._item_title({"id": "NEXLY-001", "title": "X"}) == "X"


class TestChecklist:
    def test_renders_plain_strings(self):
        assert backlog._checklist(["A", "B"]) == "- [ ] A\n- [ ] B"

    def test_empty(self):
        assert backlog._checklist([]) == ""

    def test_single_line(self):
        assert backlog._checklist_line("Build API client") == "- [ ] Build API client"


# ── build_issue_body ───────────────────────────────────────────────────────


class TestBuildIssueBody:
    def test_empty(self):
        assert backlog.build_issue_body({}) == ""

    def test_description_only(self):
        assert backlog.build_issue_body({"description": "Capture notes fast."}) == "Capture notes fast."

    def test_goal_section(self):
        result = backlog.build_issue_body({"goal": "Why this matters."})
        assert result == "## Goal\n\nWhy this matters."

    def test_tasks_section(self):
        result = backlog.build_issue_body({"tasks": ["Do thing", "Do other"]})
        assert "## Tasks" in result
        assert "- [ ] Do thing" in result
        assert "- [ ] Do other" in result
        assert "## Acceptance Criteria" not in result

    def test_acceptance_criteria_section(self):
        result = backlog.build_issue_body({"acceptance_criteria": ["AC1", "AC2"]})
        assert result == "## Acceptance Criteria\n\n- [ ] AC1\n- [ ] AC2"

    def test_notes_section(self):
        result = backlog.build_issue_body({"notes": "Mind the edge case."})
        assert result == "## Notes\n\nMind the edge case."

    def test_full_order_description_goal_tasks_ac_notes(self):
        result = backlog.build_issue_body({
            "description": "Desc.",
            "goal": "Goal.",
            "tasks": ["Step"],
            "acceptance_criteria": ["AC1"],
            "notes": "Notes.",
        })
        assert (
            result.index("Desc.")
            < result.index("## Goal")
            < result.index("## Tasks")
            < result.index("## Acceptance Criteria")
            < result.index("## Notes")
        )

    def test_blank_description_ignored(self):
        result = backlog.build_issue_body({"description": "", "acceptance_criteria": ["AC1"]})
        assert result == "## Acceptance Criteria\n\n- [ ] AC1"

    def test_empty_tasks_ignored(self):
        result = backlog.build_issue_body({"description": "X.", "tasks": []})
        assert "## Tasks" not in result
        assert result == "X."

    def test_lean_story_renders_description_only(self):
        # A lean (un-groomed) story carries only title / description / priority.
        story = {"title": "T", "description": "Just the description.", "priority": "P0"}
        assert backlog.build_issue_body(story) == "Just the description."


# ── load / save / title-map / clear ────────────────────────────────────────


_SAMPLE = {
    "project": "TestProject",
    "description": "Build foundation",
    "dates": {"start": "2026-02-17", "end": "2026-03-02"},
    "stories": [
        {"title": "Research", "description": "Investigate.",
         "status": "In Progress", "priority": "P0", "issue_number": 101},
        {"title": "Setup", "description": "Stand up repo.",
         "status": "Backlog", "priority": "P1", "issue_number": 102},
    ],
}


@pytest.fixture
def backlog_file(tmp_path):
    p = tmp_path / "backlog.json"
    p.write_text(json.dumps(_SAMPLE), encoding="utf-8")
    return p


class TestLoadFlatData:
    def test_returns_stories(self, backlog_file):
        stories, _, backlog_data = backlog.load_flat_data(backlog_file)
        assert len(stories) == 2
        assert isinstance(backlog_data, dict)

    def test_metadata(self, backlog_file):
        _, metadata, _ = backlog.load_flat_data(backlog_file)
        assert metadata["project"] == "TestProject"
        assert metadata["description"] == "Build foundation"
        assert metadata["dates"]["start"] == "2026-02-17"

    def test_empty(self, tmp_path):
        p = tmp_path / "b.json"
        p.write_text(json.dumps({"stories": []}), encoding="utf-8")
        stories, _, _ = backlog.load_flat_data(p)
        assert stories == []


class TestTitleToIssueNumberMap:
    def test_maps_all_titles(self):
        stories = [{"title": "Research", "issue_number": 1}, {"title": "Setup", "issue_number": 2}]
        assert backlog._title_to_issue_number_map(stories) == {"Research": 1, "Setup": 2}

    def test_skips_missing_numbers(self):
        stories = [{"title": "Research"}, {"title": "Setup", "issue_number": 2}]
        assert backlog._title_to_issue_number_map(stories) == {"Setup": 2}


class TestSaveFlatData:
    def test_writes_issue_numbers(self, tmp_path):
        p = tmp_path / "b.json"
        data = {"stories": [{"title": "X", "description": "d"}]}
        p.write_text(json.dumps(data), encoding="utf-8")
        stories, _, backlog_data = backlog.load_flat_data(p)
        backlog_data["stories"][0]["issue_number"] = 999
        backlog.save_flat_data(backlog_data["stories"], p, backlog_data)
        reloaded = json.loads(p.read_text(encoding="utf-8"))
        assert reloaded["stories"][0]["issue_number"] == 999

    def test_writeback_matches_by_title(self, tmp_path):
        # The working stories list is a separate copy carrying the minted
        # numbers; writeback must land them on the file entries by title.
        p = tmp_path / "b.json"
        data = {"stories": [{"title": "Research", "description": "d"},
                            {"title": "Setup", "description": "d"}]}
        p.write_text(json.dumps(data), encoding="utf-8")
        _, _, backlog_data = backlog.load_flat_data(p)
        mutated = [{"title": "Setup", "issue_number": 22},
                   {"title": "Research", "issue_number": 11}]
        backlog.save_flat_data(mutated, p, backlog_data)
        reloaded = json.loads(p.read_text(encoding="utf-8"))
        by_title = {s["title"]: s["issue_number"] for s in reloaded["stories"]}
        assert by_title == {"Research": 11, "Setup": 22}

    def test_preserves_other_fields(self, backlog_file):
        stories, _, backlog_data = backlog.load_flat_data(backlog_file)
        backlog.save_flat_data(stories, backlog_file, backlog_data)
        reloaded = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert reloaded["project"] == "TestProject"
        assert reloaded["stories"][0]["title"] == "Research"


class TestClearIssueNumbers:
    def test_strips_issue_numbers(self, backlog_file, capsys):
        _, _, backlog_data = backlog.load_flat_data(backlog_file)
        backlog.clear_issue_numbers(backlog_data, backlog_file)
        reloaded = json.loads(backlog_file.read_text(encoding="utf-8"))
        assert all("issue_number" not in s for s in reloaded["stories"])
        assert "Cleared" in capsys.readouterr().out
