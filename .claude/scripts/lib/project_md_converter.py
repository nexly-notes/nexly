"""project_md_converter.py — Render backlog.json as a human-readable markdown backlog.

Pure renderer: feed it parsed JSON (``json.loads`` of backlog.json), get a
markdown string. No I/O, no validation — pair with ``lib.project_validator``
when you need both. The shape mirrors the schema documented in
``project_manager/README.md``: an H1 project header, then one H2 section per
story with metadata, description, acceptance criteria, and a checkbox-style
task sublist.

Done tasks render as ``- [x]`` so a glance at the file conveys progress.
Empty optional sections (no tasks, no blocked_by) are suppressed or shown as
``—`` so the output stays compact regardless of which fields are populated.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def project_json_to_md(data: dict) -> str:
    """
    Render a parsed backlog.json as a markdown backlog string.

    Sections are emitted top-down: project header, then each story in the
    order they appear in *data['stories']*. Tasks nest under their parent
    story under an ``### Tasks`` subsection, omitted when the list is empty.

    Args:
        data (dict): Parsed backlog.json. Expected to carry the documented
            top-level keys (project, goal, dates, totalPoints, stories).

    Returns:
        str: Markdown text. Sections are separated by blank lines; the
            output ends with a single trailing newline.

    Raises:
        KeyError: If a required top-level key (``project``, ``goal``,
            ``dates``, ``stories``) is missing — validate first.

    Example:
        >>> project_json_to_md({"project": "X", "goal": "Y",
        ...     "dates": {"start": "a", "end": "b"}, "totalPoints": 0,
        ...     "stories": []})  # doctest: +ELLIPSIS
        Return: '# Project: X\\n...'
    """
    parts: list[str] = []
    parts.append(_render_header(data))   # project name, goal, dates, points
    for story in data.get("stories", []):
        parts.append(_render_story(story))  # one H2 block per story
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def _render_header(data: dict) -> str:
    # Top-of-file overview: name, goal, dates, point total. Kept compact.
    dates = data.get("dates") or {}
    start = dates.get("start", "?")
    end = dates.get("end", "?")
    lines = [
        f"# Project: {data['project']}",
        "",
        f"**Goal:** {data['goal']}",
        f"**Dates:** {start} → {end}",
        f"**Total points:** {data.get('totalPoints', 0)}",
        "",
        "---",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Story rendering
# ---------------------------------------------------------------------------


def _render_story(story: dict) -> str:
    # Compose a story section from independent sub-renderers; drop empties so
    # we don't leave a trail of blank lines between sections.
    blocks = [
        _render_story_heading(story),
        _render_story_meta(story),
        _render_story_secondary_meta(story),
        _render_description(story),
        _render_blocking_lines(story),
        _render_acceptance_criteria(story.get("acceptance_criteria")),
        _render_tasks(story.get("tasks")),
    ]
    return "\n\n".join(b for b in blocks if b)


def _render_story_heading(story: dict) -> str:
    sid = story.get("id", "?")
    title = story.get("title", "")
    return f"## {sid} — {title}"


def _render_story_meta(story: dict) -> str:
    # Single-line "core" metadata — the fields a triage pass cares about.
    parts = [
        f"**Type:** {story.get('type', '?')}",
        f"**Priority:** {story.get('priority', '?')}",
        f"**Status:** {story.get('status', '?')}",
        f"**Points:** {story.get('points', 0)}",
        f"**Milestone:** {story.get('milestone', '—')}",
    ]
    return " · ".join(parts)


def _render_story_secondary_meta(story: dict) -> str:
    # Less-frequently-scanned metadata — TDD flag, labels, dates.
    labels = ", ".join(story.get("labels") or []) or "—"
    start = story.get("start_date", "—")
    end = story.get("target_date", "—")
    tdd = "yes" if story.get("tdd") else "no"
    return (
        f"**TDD:** {tdd}  \n"
        f"**Labels:** {labels}  \n"
        f"**Dates:** {start} → {end}"
    )


def _render_description(story: dict) -> str:
    desc = (story.get("description") or "").strip()
    return desc  # may be empty; outer join filters it out


def _render_blocking_lines(story: dict) -> str:
    # Both directions of the dependency graph; '—' for empty, comma list otherwise.
    blocked_by = _format_id_list(story.get("blocked_by"))
    is_blocking = _format_id_list(story.get("is_blocking"))
    return (
        f"**Blocked by:** {blocked_by}  \n"
        f"**Is blocking:** {is_blocking}"
    )


def _format_id_list(ids) -> str:
    if not ids:
        return "—"
    return ", ".join(ids)


def _render_acceptance_criteria(items) -> str:
    if not items:
        return ""
    bullets = "\n".join(f"- {item}" for item in items)
    return f"### Acceptance criteria\n{bullets}"


# ---------------------------------------------------------------------------
# Tasks subsection
# ---------------------------------------------------------------------------


def _render_tasks(tasks) -> str:
    if not tasks:
        return ""  # omit the heading entirely when there are no tasks
    bullets = "\n".join(_render_task_line(t) for t in tasks)
    return f"### Tasks\n{bullets}"


def _render_task_line(task: dict) -> str:
    # Done → [x]; everything else (Backlog / Ready / In progress / In review) → [ ].
    box = "x" if task.get("status") == "Done" else " "
    tid = task.get("id", "?")
    title = task.get("title", "")
    suffix = _render_task_suffix(task)
    return f"- [{box}] {tid} — {title} {suffix}".rstrip()


def _render_task_suffix(task: dict) -> str:
    # Inline parenthetical: priority, complexity, status. Skipped fields drop out.
    parts = [
        task.get("priority"),
        task.get("complexity"),
        task.get("status"),
    ]
    visible = [p for p in parts if p]
    return f"({', '.join(visible)})" if visible else ""
