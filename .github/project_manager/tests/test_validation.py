"""Tests for project_manager.validation — pure blocked_by graph checks.

``blocked_by`` entries may be ints (issue numbers, durable) or strings
(item titles, the pre-mint authoring form). Validation must be loud about
everything that would corrupt the title→number conversion: dangling titles,
self-blocks, duplicate refs, duplicate item titles, and cycles.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from project_manager.validation import validate_backlog


def _item(title, *, blocked_by=None, issue_number=None, status="Backlog"):
    return {
        "title": title, "status": status,
        "blocked_by": list(blocked_by or []), "issue_number": issue_number,
    }


def _backlog(*stories):
    return {"project": "T", "stories": list(stories)}


class TestValidBacklogs:
    def test_empty_backlog(self):
        assert validate_backlog({"stories": []}) == []

    def test_no_blocked_by(self):
        backlog = _backlog(_item("A"), _item("B"))
        assert validate_backlog(backlog) == []

    def test_valid_mixed_backlog(self):
        # Titles pre-mint, ints post-mint, and an external int ref together.
        backlog = _backlog(
            _item("A", issue_number=1),
            _item("B", blocked_by=[1]),
            _item("C", blocked_by=["A", "B"]),
            _item("D", blocked_by=[999]),  # external ref — legal
        )
        assert validate_backlog(backlog) == []

    def test_existing_all_int_backlog_still_valid(self):
        backlog = _backlog(
            _item("A", issue_number=447),
            _item("B", issue_number=445, blocked_by=[447]),
            _item("C", issue_number=405, blocked_by=[447, 445]),
        )
        assert validate_backlog(backlog) == []


class TestDanglingTitles:
    def test_dangling_title_is_error(self):
        backlog = _backlog(_item("A", blocked_by=["Nope"]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1
        assert "A" in errors[0] and "Nope" in errors[0]

    def test_title_match_is_case_sensitive(self):
        backlog = _backlog(_item("A"), _item("B", blocked_by=["a"]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "'a'" in errors[0]

    def test_dangling_int_is_not_error(self):
        # Numeric refs may point at external issues — skip-warn at sync time.
        backlog = _backlog(_item("A", blocked_by=[999]))
        assert validate_backlog(backlog) == []


class TestSelfBlocks:
    def test_self_block_by_title(self):
        backlog = _backlog(_item("A", blocked_by=["A"]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "itself" in errors[0]

    def test_self_block_by_issue_number(self):
        backlog = _backlog(_item("A", issue_number=5, blocked_by=[5]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "itself" in errors[0]


class TestDuplicateEntries:
    def test_literal_duplicate_titles(self):
        backlog = _backlog(_item("A"), _item("B", blocked_by=["A", "A"]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "duplicate blocked_by" in errors[0]

    def test_literal_duplicate_ints(self):
        backlog = _backlog(_item("A", blocked_by=[7, 7]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "duplicate blocked_by" in errors[0]

    def test_mixed_duplicate_after_normalizing(self):
        # int 5 and the title of issue 5 reference the same item.
        backlog = _backlog(
            _item("A", issue_number=5),
            _item("B", blocked_by=[5, "A"]),
        )
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "duplicate blocked_by" in errors[0]


class TestEntryTypes:
    def test_non_int_str_entry_is_error(self):
        backlog = _backlog(_item("A", blocked_by=[None]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "must be an" in errors[0]

    def test_bool_entry_is_error(self):
        # JSON `true` loads as bool — never a valid issue number.
        backlog = _backlog(_item("A", blocked_by=[True]))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "must be an" in errors[0]


class TestCycles:
    def test_title_cycle_detected(self):
        backlog = _backlog(
            _item("A", blocked_by=["B"]),
            _item("B", blocked_by=["A"]),
        )
        errors = validate_backlog(backlog)
        assert len(errors) == 1
        assert "cycle" in errors[0].lower()
        assert "A" in errors[0] and "B" in errors[0]

    def test_mixed_title_int_cycle_detected(self):
        # A blocks B by title; B blocks A by issue number.
        backlog = _backlog(
            _item("A", issue_number=1, blocked_by=["B"]),
            _item("B", blocked_by=[1]),
        )
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "cycle" in errors[0].lower()

    def test_longer_cycle_reports_path(self):
        backlog = _backlog(
            _item("A", blocked_by=["C"]),
            _item("B", blocked_by=["A"]),
            _item("C", blocked_by=["B"]),
        )
        errors = validate_backlog(backlog)
        assert len(errors) == 1
        assert errors[0].count("->") == 3

    def test_diamond_is_not_a_cycle(self):
        backlog = _backlog(
            _item("A"),
            _item("B", blocked_by=["A"]),
            _item("C", blocked_by=["A"]),
            _item("D", blocked_by=["B", "C"]),
        )
        assert validate_backlog(backlog) == []


class TestDuplicateItemTitles:
    def test_duplicate_story_titles(self):
        backlog = _backlog(_item("Same"), _item("Same"))
        errors = validate_backlog(backlog)
        assert len(errors) == 1 and "Duplicate item title" in errors[0]

    def test_duplicate_across_levels(self):
        story = _item("Parent")
        story["tasks"] = [_item("Parent")]
        errors = validate_backlog(_backlog(story))
        assert len(errors) == 1 and "Duplicate item title" in errors[0]


class TestAllDigitsTitle:
    def test_int_entry_does_not_match_digit_title(self):
        # JSON types disambiguate: int 123 is an external numeric ref,
        # not a reference to the item titled "123".
        backlog = _backlog(_item("123"), _item("A", blocked_by=[123, "123"]))
        assert validate_backlog(backlog) == []

    def test_digit_title_entry_resolves_by_title(self):
        backlog = _backlog(_item("123"), _item("A", blocked_by=["123"]))
        assert validate_backlog(backlog) == []


class TestSubIssues:
    def test_subissue_blocked_by_validated(self):
        story = _item("Parent")
        story["tasks"] = [_item("Child", blocked_by=["Nope"])]
        errors = validate_backlog(_backlog(story))
        assert len(errors) == 1 and "Child" in errors[0]

    def test_subissue_title_is_valid_target(self):
        story = _item("Parent")
        story["tasks"] = [_item("Child", issue_number=9)]
        backlog = _backlog(story, _item("A", blocked_by=["Child"]))
        assert validate_backlog(backlog) == []

    def test_string_tasks_tolerated(self):
        story = _item("Parent")
        story["tasks"] = ["plain checklist line"]
        assert validate_backlog(_backlog(story)) == []


class TestMultipleErrors:
    def test_all_errors_reported_together(self):
        backlog = _backlog(
            _item("Same"),
            _item("Same"),
            _item("A", blocked_by=["Nope", "A"]),
        )
        errors = validate_backlog(backlog)
        assert len(errors) == 3
