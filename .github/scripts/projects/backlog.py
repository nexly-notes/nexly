"""Backlog file IO + GitHub issue-body building.

The backlog is a top-level ``stories`` array; each story maps 1:1 to a GitHub
issue, keyed by its ``title`` (the re-link key) and identified by its
``issue_number`` once converted. This module is pure (file IO + string
building); it issues no network calls, so it stays trivially testable.

The issue body is assembled in a fixed section order — ``description`` prose
first, then ``## Goal``, ``## Tasks``, ``## Acceptance Criteria``, ``## Notes``
— with every empty / missing section silently skipped, so a story renders the
same whether or not a given section is present.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Pure helpers ───────────────────────────────────────────────────────────


def _item_title(item: dict[str, Any]) -> str:
    """Return the story's bare ``title`` — the issue title and re-link key."""
    return item["title"]


def _checklist_line(entry: str) -> str:
    """Render one entry as an unchecked GitHub checkbox line.

    Example:
        >>> _checklist_line("Build API client")
        '- [ ] Build API client'
    """
    return f"- [ ] {entry}"


def _checklist(entries: list[str]) -> str:
    """Render a list of plain strings as a checkbox checklist.

    Example:
        >>> _checklist(["A", "B"])
        '- [ ] A\\n- [ ] B'
    """
    return "\n".join(_checklist_line(e) for e in entries)


def build_issue_body(item: dict[str, Any]) -> str:
    """Build an issue body from a story's content fields.

    Sections render in the order ``description`` → ``## Goal`` → ``## Tasks``
    → ``## Acceptance Criteria`` → ``## Notes``. Any empty / missing section
    is skipped so the joined body never carries a dangling separator.

    Args:
        item (dict): Story record. Reads ``description`` (str), ``goal``
            (str), ``tasks`` (list[str]), ``acceptance_criteria`` (list[str]),
            and ``notes`` (str).

    Returns:
        str: Markdown body, or empty string when every section is empty.

    Example:
        >>> build_issue_body({"acceptance_criteria": ["AC1"]})
        '## Acceptance Criteria\\n\\n- [ ] AC1'
    """
    description = (item.get("description") or "").strip()
    goal = (item.get("goal") or "").strip()
    tasks = item.get("tasks", []) or []
    criteria = item.get("acceptance_criteria", []) or []
    notes = (item.get("notes") or "").strip()
    sections: list[str] = []
    if description:
        sections.append(description)
    if goal:
        sections.append(f"## Goal\n\n{goal}")
    if tasks:
        sections.append(f"## Tasks\n\n{_checklist(tasks)}")
    if criteria:
        sections.append(f"## Acceptance Criteria\n\n{_checklist(criteria)}")
    if notes:
        sections.append(f"## Notes\n\n{notes}")
    return "\n\n".join(sections)


# ── Flat data load / save ──────────────────────────────────────────────────


def _build_metadata(backlog: dict) -> dict:
    return {
        "description": backlog.get("description", ""),
        "dates": backlog.get("dates", {}),
        "project": backlog.get("project", ""),
    }


def load_flat_data(backlog_path: Path) -> tuple[list[dict], dict, dict[str, Any]]:
    """Load the backlog file.

    Returns ``(stories, metadata, backlog_data)``. ``stories`` is the
    top-level story list verbatim.
    """
    backlog_data = json.loads(Path(backlog_path).read_text(encoding="utf-8"))
    metadata = _build_metadata(backlog_data)
    stories: list[dict] = list(backlog_data.get("stories", []))
    return stories, metadata, backlog_data


def _title_to_issue_number_map(stories: list[dict]) -> dict[str, int]:
    """Build ``{title: issue_number}`` for every story that has an issue_number."""
    title_map: dict[str, int] = {}
    for story in stories:
        if story.get("issue_number") and story.get("title"):
            title_map[story["title"]] = story["issue_number"]
    return title_map


def save_flat_data(
    stories: list[dict],
    backlog_path: Path,
    backlog_data: dict[str, Any],
) -> None:
    """Write updated story ``issue_number`` values back into the backlog file.

    Stories are matched back to the file by ``title`` (the re-link key), so the
    newly-minted ``issue_number`` lands on the right entry even when the working
    ``stories`` list is a copy.
    """
    title_to_num = _title_to_issue_number_map(stories)
    for story in backlog_data.get("stories", []):
        if story.get("title") in title_to_num:
            story["issue_number"] = title_to_num[story["title"]]
    Path(backlog_path).write_text(json.dumps(backlog_data, indent=2), encoding="utf-8")


def clear_issue_numbers(backlog_data: dict[str, Any], backlog_path: Path) -> None:
    """Strip every story's ``issue_number`` so the next convert re-creates."""
    for story in backlog_data.get("stories", []):
        story.pop("issue_number", None)
    Path(backlog_path).write_text(json.dumps(backlog_data, indent=2), encoding="utf-8")
    print(f"\nCleared issue numbers from {backlog_path}")
