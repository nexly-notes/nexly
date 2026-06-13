#!/usr/bin/env python3
"""Convert the backlog JSON into a readable ``backlog.md``.

Reads ``project/backlog.json`` and writes ``backlog.md`` alongside it -- a
human-friendly view of the same data: a one-glance overview table plus a
detailed section per story. The JSON stays the source of truth; the markdown
is regenerated, never hand-edited.

Story detail mirrors the GitHub issue-body section order used by the projects
package (description -> Goal -> Tasks -> Acceptance Criteria -> Notes), so any
grooming fields that happen to be present render the same way they would on the
issue. Lean stories (title / description / priority only) render cleanly with
those sections simply omitted.

The GitHub issue number is the story's identity; it links to GitHub when
``.github/config.json`` is readable and degrades to a plain ``#N`` reference
when it is not. ``blocked_by`` entries may be issue numbers (rendered ``#N``)
or item titles (the pre-mint authoring form — rendered ``#N`` when the target
is already minted, otherwise as the quoted title).

Usage:
    python3 .claude/skills/backlog/scripts/backlog-to-md.py
    python3 .claude/skills/backlog/scripts/backlog-to-md.py path/to/backlog.json
    python3 .claude/skills/backlog/scripts/backlog-to-md.py -o path/to/out.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo root is four levels up from this script
# (.claude/skills/backlog/scripts/backlog-to-md.py).
REPO_ROOT: Path = Path(__file__).resolve().parents[4]
DEFAULT_BACKLOG: Path = REPO_ROOT / "project" / "backlog.json"
CONFIG_PATH: Path = REPO_ROOT / ".github" / "config.json"
PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2")
DEFAULT_STATUS: str = "Backlog"


# ── Loading ────────────────────────────────────────────────────────────────


def load_backlog(path: Path) -> dict:
    """Read and parse the backlog JSON, exiting with a message on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"error: backlog file not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: invalid JSON in {path}: {exc}")


def load_repo_slug() -> str | None:
    """Read the ``owner/repo`` slug from config.json for issue links (optional)."""
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    repo = config.get("repo")
    return repo if isinstance(repo, str) and "/" in repo else None


# ── Small render helpers ───────────────────────────────────────────────────


def _relative_to_root(path: Path) -> str:
    """Display a path relative to the repo root when it lives inside it."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _escape_cell(text: str) -> str:
    """Escape pipe characters so a title never breaks the table layout."""
    return text.replace("|", "\\|")


def _checklist(entries: list[str]) -> str:
    """Render plain strings as a checkbox checklist, matching the issue body."""
    return "\n".join(f"- [ ] {entry}" for entry in entries)


def _render_tasks(tasks: list[str | dict]) -> str:
    """Render tasks as a checkbox checklist.

    Tasks may be plain strings (lean shape) or sub-issue objects (groomed
    shape). Objects render their done-state from ``status`` and append their
    ``#N`` issue reference when one has been minted.
    """
    lines: list[str] = []
    for task in tasks:
        if isinstance(task, dict):
            box = "x" if task.get("status") == "Done" else " "
            title = task.get("title", "")
            number = task.get("issue_number")
            ref = f" (#{number})" if number else ""
            lines.append(f"- [{box}] {title}{ref}")
        else:
            lines.append(f"- [ ] {task}")
    return "\n".join(lines)


def _code_list(entries: list[str]) -> str:
    """Render a list of short tokens as comma-separated inline code."""
    return ", ".join(f"`{entry}`" for entry in entries)


def _blocked_by_refs(blocked_by: list[int | str], num_by_title: dict[str, int]) -> str:
    """Render blocked_by entries: ``#N`` for numbers and minted titles, else the quoted title."""
    refs: list[str] = []
    for entry in blocked_by:
        if isinstance(entry, str):
            num = num_by_title.get(entry)
            refs.append(f"#{num}" if num else f'"{entry}"')
        else:
            refs.append(f"#{entry}")
    return " ".join(refs)


def _build_title_to_number(stories: list[dict]) -> dict[str, int]:
    """Index minted items (stories + sub-issues) by title for blocked_by rendering."""
    num_by_title: dict[str, int] = {}
    for story in stories:
        tasks = [t for t in story.get("tasks", []) if isinstance(t, dict)]
        for item in [story, *tasks]:
            title, number = item.get("title"), item.get("issue_number")
            if title and number:
                num_by_title[title] = number
    return num_by_title


def _issue_link(issue_number: int, repo_slug: str | None) -> str:
    """Link an issue number to GitHub, or fall back to a plain ``#N`` reference."""
    if repo_slug:
        return f"[#{issue_number}](https://github.com/{repo_slug}/issues/{issue_number})"
    return f"#{issue_number}"


def _issue_cell(issue_number: int, repo_slug: str | None) -> str:
    """Issue reference for the overview table; em dash when not yet created."""
    if not issue_number:
        return "—"
    return _issue_link(issue_number, repo_slug)


def _issue_detail(issue_number: int, repo_slug: str | None) -> str:
    """Issue reference for the story detail; spelled out when not yet created."""
    if not issue_number:
        return "not yet created"
    return _issue_link(issue_number, repo_slug)


# ── Section renderers ──────────────────────────────────────────────────────


def _render_header(backlog: dict, stories: list[dict], source_label: str) -> str:
    """Render the title, description, and at-a-glance backlog summary."""
    project = backlog.get("project", "Backlog")
    description = (backlog.get("description") or "").strip()
    dates = backlog.get("dates", {}) or {}
    start = dates.get("start", "?")
    end = dates.get("end", "?")
    by_priority = {p: sum(1 for s in stories if s.get("priority") == p) for p in PRIORITIES}
    created = sum(1 for s in stories if s.get("issue_number"))
    priority_summary = " · ".join(f"{p}: {by_priority[p]}" for p in PRIORITIES)
    lines = [f"# {project} — Product Backlog", ""]
    if description:
        lines += [f"*{description}*", ""]
    lines += [
        f"- **Dates:** {start} → {end}",
        f"- **Stories:** {len(stories)} — {priority_summary}",
        f"- **Issues created:** {created} / {len(stories)}",
        "",
        f"*Generated from `{source_label}`. Do not edit by hand — re-run the converter.*",
    ]
    return "\n".join(lines)


def _meta_cell(value: object) -> str:
    """Render an optional scalar (size / points) for the overview, em dash when absent."""
    if value is None or value == "":
        return "—"
    return str(value)


def _render_overview(stories: list[dict], repo_slug: str | None) -> str:
    """Render the scan-friendly overview table, one row per story."""
    if not stories:
        return "## Overview\n\n*No stories yet.*"
    lines = [
        "## Overview",
        "",
        "| Title | Priority | Size | Points | Status | GitHub |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for story in stories:
        title = _escape_cell(story.get("title", ""))
        priority = story.get("priority", "—")
        size = _meta_cell(story.get("size"))
        points = _meta_cell(story.get("points"))
        status = story.get("status", DEFAULT_STATUS)
        issue = _issue_cell(story.get("issue_number", 0), repo_slug)
        lines.append(f"| {title} | {priority} | {size} | {points} | {status} | {issue} |")
    return "\n".join(lines)


def _append_groom_meta(
    story: dict, lines: list[str], num_by_title: dict[str, int]
) -> None:
    """Append the flat grooming fields (labels, dependencies, size, points)."""
    meta: list[str] = []
    labels = story.get("labels") or []
    if labels:
        meta.append(f"- **Labels:** {_code_list(labels)}")
    blocked_by = story.get("blocked_by") or []
    if blocked_by:
        meta.append(f"- **Blocked by:** {_blocked_by_refs(blocked_by, num_by_title)}")
    size = story.get("size")
    points = story.get("points")
    if size is not None or points is not None:
        parts: list[str] = []
        if size is not None:
            parts.append(f"**Size:** {size}")
        if points is not None:
            parts.append(f"**Points:** {points}")
        meta.append("- " + " · ".join(parts))
    if meta:
        lines.append("")
        lines.extend(meta)


def _append_grooming(
    story: dict, lines: list[str], num_by_title: dict[str, int]
) -> None:
    """Append optional grooming detail in the canonical issue-body order."""
    goal = (story.get("goal") or "").strip()
    if goal:
        lines += ["", "**Goal**", "", goal]
    tasks = story.get("tasks") or []
    if tasks:
        lines += ["", "**Tasks**", "", _render_tasks(tasks)]
    criteria = story.get("acceptance_criteria") or []
    if criteria:
        lines += ["", "**Acceptance criteria**", "", _checklist(criteria)]
    notes = (story.get("notes") or "").strip()
    if notes:
        lines += ["", "**Notes**", "", notes]
    _append_groom_meta(story, lines, num_by_title)


def _render_story(
    story: dict, repo_slug: str | None, num_by_title: dict[str, int]
) -> str:
    """Render a single story: heading, metadata, description, any grooming."""
    title = story.get("title", "")
    priority = story.get("priority", "—")
    status = story.get("status", DEFAULT_STATUS)
    issue = _issue_detail(story.get("issue_number", 0), repo_slug)
    description = (story.get("description") or "").strip()
    lines = [
        f"### {title}",
        "",
        f"- **Priority:** {priority}",
        f"- **Status:** {status}",
        f"- **GitHub issue:** {issue}",
    ]
    if description:
        lines += ["", description]
    _append_grooming(story, lines, num_by_title)
    return "\n".join(lines)


def render_markdown(backlog: dict, source_label: str, repo_slug: str | None) -> str:
    """Render the whole backlog document from a parsed backlog dict."""
    stories = list(backlog.get("stories", []))
    num_by_title = _build_title_to_number(stories)
    blocks = [
        _render_header(backlog, stories, source_label),
        _render_overview(stories, repo_slug),
    ]
    if stories:
        story_blocks = "\n\n".join(
            _render_story(s, repo_slug, num_by_title) for s in stories
        )
        blocks.append(f"## Stories\n\n{story_blocks}")
    return "\n\n".join(blocks) + "\n"


# ── CLI entrypoint ─────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """Convert ``backlog.json`` to ``backlog.md`` beside it; return an exit code."""
    parser = argparse.ArgumentParser(
        description="Convert backlog.json into a readable backlog.md."
    )
    parser.add_argument(
        "backlog",
        nargs="?",
        type=Path,
        default=DEFAULT_BACKLOG,
        help="path to the backlog JSON (default: project/backlog.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output markdown path (default: backlog.md beside the JSON)",
    )
    args = parser.parse_args(argv)
    backlog_path = args.backlog.resolve()
    output_path = (args.output or backlog_path.with_name("backlog.md")).resolve()
    backlog = load_backlog(backlog_path)
    repo_slug = load_repo_slug()
    markdown = render_markdown(backlog, _relative_to_root(backlog_path), repo_slug)
    output_path.write_text(markdown, encoding="utf-8")
    story_count = len(backlog.get("stories", []))
    print(f"Wrote {_relative_to_root(output_path)} ({story_count} stories)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
