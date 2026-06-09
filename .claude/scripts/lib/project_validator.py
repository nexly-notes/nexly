"""project_validator.py — Schema validator for project_manager/project/backlog.json.

Pure validation: callers pass parsed JSON, get back a list of human-readable
error strings. An empty list means the file conforms. The validator covers
the rules documented in ``project_manager/README.md`` (top-level shape,
canonical enums for status / priority / complexity, ID-prefix-per-type, the
story-vs-task field split) plus the cross-record check that every
``blocked_by`` references a story that exists in the same file.

No side effects, no I/O — feed it ``json.loads(...)`` output. The validator
short-circuits nothing: it surfaces every error it can find in one pass so
authors can fix the whole file in one revision.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Canonical enums + structural constants
# ---------------------------------------------------------------------------

STATUSES = {"Backlog", "Ready", "In progress", "In review", "Done"}
PRIORITIES = {"P0", "P1", "P2", "P3"}
COMPLEXITIES = {"XS", "S", "M", "L", "XL"}

# Type → required ID prefix. "Tech" and "Technical Story" both map to TS-
# because the docs use the long form while the live backlog uses "Tech".
STORY_TYPE_PREFIX = {
    "Spike": "SK-",
    "Bug": "BG-",
    "User Story": "US-",
    "Tech": "TS-",
    "Technical Story": "TS-",
}

TOP_LEVEL_REQUIRED = ("project", "goal", "dates", "totalPoints", "stories")

# Story-only fields: must NOT appear on tasks.
STORY_ONLY_FIELDS = ("points", "tdd", "is_blocking", "blocked_by")
# Task-only fields: must NOT appear on stories.
TASK_ONLY_FIELDS = ("complexity",)

STORY_REQUIRED = (
    "id", "type", "title", "status", "priority",
    "points", "tdd", "is_blocking", "blocked_by",
)
TASK_REQUIRED = (
    "id", "title", "status", "priority",
    "complexity", "parent_story_id", "item_type",
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_project(data: Any) -> list[str]:
    """
    Validate parsed backlog.json against the documented schema.

    Walks the document once, collecting every rule violation it finds. The
    returned list is ordered top-down (top-level → stories → tasks) so the
    first error a caller sees is also the highest-level one.

    Args:
        data (Any): Parsed JSON. Expected to be a dict matching the
            backlog.json shape; non-dict roots produce a single error.

    Returns:
        list[str]: Human-readable error messages. Empty list means valid.

    Raises:
        None: The validator never raises on malformed input — every
            structural problem is reported as an error string instead.

    Example:
        >>> validate_project({})
        Return: ['root must be an object', "missing top-level 'project'", ...]
    """
    if not isinstance(data, dict):
        return ["root must be an object (dict)"]
    errors: list[str] = []
    _check_top_level(data, errors)         # required top-level keys
    _check_dates(data.get("dates"), errors)  # nested date object
    stories = data.get("stories")
    if isinstance(stories, list):
        _check_all_stories(stories, errors)  # per-story + cross-refs
    elif "stories" in data:
        errors.append("'stories' must be a list")
    return errors


# ---------------------------------------------------------------------------
# Top-level helpers
# ---------------------------------------------------------------------------


def _check_top_level(data: dict, errors: list[str]) -> None:
    # Each missing top-level key surfaces independently so authors see them all.
    for field in TOP_LEVEL_REQUIRED:
        if field not in data:
            errors.append(f"missing top-level '{field}'")


def _check_dates(dates: Any, errors: list[str]) -> None:
    # 'dates' is optional only when missing entirely (already reported above).
    if dates is None:
        return
    if not isinstance(dates, dict):
        errors.append("'dates' must be an object with start/end")
        return
    for key in ("start", "end"):  # dates.start, dates.end both required
        if key not in dates:
            errors.append(f"missing 'dates.{key}'")


# ---------------------------------------------------------------------------
# Story-level helpers
# ---------------------------------------------------------------------------


def _check_all_stories(stories: list, errors: list[str]) -> None:
    # Pre-collect IDs so blocked_by / is_blocking can be cross-checked.
    known_ids = {s.get("id") for s in stories if isinstance(s, dict)}
    for story in stories:
        _check_story(story, known_ids, errors)


def _check_story(story: Any, known_ids: set, errors: list[str]) -> None:
    if not isinstance(story, dict):
        errors.append(f"story entry is not an object: {story!r}")
        return
    sid = story.get("id", "<no-id>")
    _check_required_fields(story, STORY_REQUIRED, sid, errors)
    _check_story_enums(story, sid, errors)        # status / priority
    _check_story_type_and_prefix(story, sid, errors)
    _check_forbidden_fields(story, TASK_ONLY_FIELDS, sid, "story", errors)
    _check_blocked_refs(story, known_ids, errors)
    _check_tasks(story.get("tasks"), sid, errors)


def _check_story_enums(story: dict, sid: str, errors: list[str]) -> None:
    status = story.get("status")
    if status is not None and status not in STATUSES:
        errors.append(f"{sid}: invalid status '{status}'")
    priority = story.get("priority")
    if priority is not None and priority not in PRIORITIES:
        errors.append(f"{sid}: invalid priority '{priority}'")


def _check_story_type_and_prefix(
    story: dict, sid: str, errors: list[str]
) -> None:
    stype = story.get("type")
    if stype is None:
        return  # missing type already reported by required-field check
    if stype not in STORY_TYPE_PREFIX:
        errors.append(f"{sid}: unknown story type '{stype}'")
        return
    expected_prefix = STORY_TYPE_PREFIX[stype]
    if isinstance(sid, str) and not sid.startswith(expected_prefix):
        errors.append(
            f"id '{sid}' does not match type '{stype}' "
            f"(expected prefix '{expected_prefix}')"
        )


def _check_blocked_refs(
    story: dict, known_ids: set, errors: list[str]
) -> None:
    sid = story.get("id", "<no-id>")
    # Both blocked_by and is_blocking reference other story IDs by value.
    for field in ("blocked_by", "is_blocking"):
        refs = story.get(field) or []
        if not isinstance(refs, list):
            errors.append(f"{sid}: '{field}' must be a list")
            continue
        for ref in refs:
            if ref not in known_ids:
                errors.append(
                    f"{sid}: '{field}' references unknown story '{ref}'"
                )


# ---------------------------------------------------------------------------
# Task-level helpers
# ---------------------------------------------------------------------------


def _check_tasks(tasks: Any, parent_id: str, errors: list[str]) -> None:
    if tasks is None:
        return  # tasks list is optional — empty stories are fine
    if not isinstance(tasks, list):
        errors.append(f"{parent_id}: 'tasks' must be a list")
        return
    for task in tasks:
        _check_task(task, parent_id, errors)


def _check_task(task: Any, parent_id: str, errors: list[str]) -> None:
    if not isinstance(task, dict):
        errors.append(f"{parent_id}: task entry is not an object")
        return
    tid = task.get("id", "<no-id>")
    _check_required_fields(task, TASK_REQUIRED, tid, errors)
    _check_task_enums(task, tid, errors)
    _check_task_id_prefix(tid, errors)
    _check_task_parent_match(task, tid, parent_id, errors)
    _check_forbidden_fields(task, STORY_ONLY_FIELDS, tid, "task", errors)


def _check_task_enums(task: dict, tid: str, errors: list[str]) -> None:
    # Status / priority share the story enums; complexity is task-only.
    status = task.get("status")
    if status is not None and status not in STATUSES:
        errors.append(f"{tid}: invalid status '{status}'")
    priority = task.get("priority")
    if priority is not None and priority not in PRIORITIES:
        errors.append(f"{tid}: invalid priority '{priority}'")
    complexity = task.get("complexity")
    if complexity is not None and complexity not in COMPLEXITIES:
        errors.append(f"{tid}: invalid complexity '{complexity}'")


def _check_task_id_prefix(tid: Any, errors: list[str]) -> None:
    if isinstance(tid, str) and not tid.startswith("T-"):
        errors.append(f"task id '{tid}' must use 'T-' prefix")


def _check_task_parent_match(
    task: dict, tid: str, parent_id: str, errors: list[str]
) -> None:
    claimed = task.get("parent_story_id")
    if claimed is not None and claimed != parent_id:
        errors.append(
            f"{tid}: parent_story_id '{claimed}' does not match "
            f"owning story '{parent_id}'"
        )


# ---------------------------------------------------------------------------
# Generic helpers reused across stories + tasks
# ---------------------------------------------------------------------------


def _check_required_fields(
    obj: dict, required: tuple, owner_id: str, errors: list[str]
) -> None:
    for field in required:
        if field not in obj:
            errors.append(f"{owner_id}: missing required field '{field}'")


def _check_forbidden_fields(
    obj: dict,
    forbidden: tuple,
    owner_id: str,
    kind: str,
    errors: list[str],
) -> None:
    # 'kind' is "story" or "task" — surfaces *which* item type the field
    # is illegal on so the error message reads cleanly.
    for field in forbidden:
        if field in obj:
            errors.append(
                f"{owner_id} ({kind}): field '{field}' is not allowed"
            )
