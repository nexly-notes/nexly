"""Validate a backlog JSON against the **lenient** ``stories`` schema.

The backlog is a top-level ``stories`` array; each story maps 1:1 to a GitHub
issue. Grooming is **optional** — a lean draft (``title`` / ``description`` /
``priority`` only) validates and converts just as a fully groomed story does.

Required per story: ``title`` (non-empty), ``description`` (non-empty), and a
valid ``priority``. Everything else — ``status`` / ``goal`` / ``notes`` /
``tasks`` / ``acceptance_criteria`` / ``labels`` / ``blocked_by`` / ``size`` /
``points`` / ``issue_number`` — is **validated only when present** (grooming
enrichment).

``title`` is the re-link key, so titles must be **unique across stories**.
Identity is the GitHub ``issue_number`` (minted by ``convert``), and
``blocked_by`` references other stories by their **issue number** — so its
closure is checked against the in-file ``issue_number`` values, and a story may
not list its own number.

``labels`` (when present) must include at least one work-type label from
``WORK_TYPE_LABELS`` — the label is the sole carrier of issue type.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

VALID_STATUSES = {"Backlog", "In Progress", "Done"}
VALID_PRIORITIES = {"P0", "P1", "P2"}
VALID_SIZES = {"XS", "S", "M", "L", "XL"}

# At least one of these must appear in every story's ``labels`` (when present) —
# the label is the sole carrier of issue type. Domain labels (backend,
# frontend, …) are allowed extras but don't satisfy the rule.
WORK_TYPE_LABELS = {"feature", "tech", "bug", "spike", "chore", "docs", "review"}

DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


def validate(data: dict) -> list[str]:
    """Validate a backlog dict and return all schema errors.

    Args:
        data (dict): Parsed JSON document to check.

    Returns:
        list[str]: Human-readable error messages; empty when valid.

    Example:
        >>> validate({})  # doctest: +SKIP
        Return: ["root: missing required field 'project'", ...]
    """
    errors: list[str] = []
    _validate_root(data, errors)
    stories = data.get("stories")
    if isinstance(stories, list):
        all_numbers = _collect_issue_numbers(stories)
        seen_titles: set[str] = set()
        for i, story in enumerate(stories):
            prefix = f"stories[{i}]"
            if not isinstance(story, dict):
                errors.append(f"{prefix}: expected object, got {type(story).__name__}")
                continue
            _validate_story(story, prefix, all_numbers, seen_titles, errors)
    return errors


# ── Root-level validation ──────────────────────────────────────────────────


def _validate_root(data: dict, errors: list[str]) -> None:
    """Validate root keys (project, description, dates, stories)."""
    _require_field(data, "project", str, "root", errors)
    _require_field(data, "description", str, "root", errors)
    _validate_dates(data, errors)
    if "stories" not in data:
        errors.append("root: missing required field 'stories'")
    elif not isinstance(data["stories"], list):
        errors.append("root.stories: expected array")


def _validate_dates(data: dict, errors: list[str]) -> None:
    """Validate the dates object and its YYYY-MM-DD strings."""
    if "dates" not in data:
        errors.append("root: missing required field 'dates'")
        return
    if not isinstance(data["dates"], dict):
        errors.append("root.dates: expected object")
        return
    for date_field in ("start", "end"):
        val = data["dates"].get(date_field)
        if val is None:
            errors.append(f"root.dates: missing required field '{date_field}'")
        elif not isinstance(val, str):
            errors.append(f"root.dates.{date_field}: expected string, got {type(val).__name__}")
        elif val and not re.match(DATE_PATTERN, val):
            errors.append(f"root.dates.{date_field}: must be YYYY-MM-DD, got '{val}'")


# ── Story-level validation ─────────────────────────────────────────────────


def _collect_issue_numbers(stories: list) -> set[int]:
    """Gather every in-file ``issue_number`` so blocked_by closure can be checked."""
    numbers: set[int] = set()
    for story in stories:
        if not isinstance(story, dict):
            continue
        num = story.get("issue_number")
        if isinstance(num, int) and not isinstance(num, bool):
            numbers.add(num)
    return numbers


def _validate_story(
    story: dict, prefix: str, all_numbers: set[int], seen_titles: set[str], errors: list[str]
) -> None:
    """Run required-field checks plus validate-if-present checks for one story."""
    _validate_story_required(story, prefix, errors)
    _validate_unique_title(story, prefix, seen_titles, errors)
    _validate_story_enums(story, prefix, errors)
    _validate_story_lists(story, prefix, all_numbers, errors)
    _validate_story_scalars(story, prefix, errors)


def _validate_story_required(story: dict, prefix: str, errors: list[str]) -> None:
    """Check the always-required fields: title, description, priority.

    ``title`` / ``description`` must be non-empty prose. ``priority`` must be
    present and is enum-checked separately.
    """
    for field in ("title", "description"):
        _require_nonempty_str(story, field, prefix, errors)
    _require_field(story, "priority", str, prefix, errors)


def _validate_unique_title(
    story: dict, prefix: str, seen_titles: set[str], errors: list[str]
) -> None:
    """Title is the re-link key, so it must be unique across stories."""
    title = story.get("title")
    if not isinstance(title, str):
        return
    if title in seen_titles:
        errors.append(f"{prefix}.title: duplicate title '{title}'")
    else:
        seen_titles.add(title)


def _validate_story_enums(story: dict, prefix: str, errors: list[str]) -> None:
    """Validate the Status / Priority / Size enum values when present as strings."""
    _validate_enum(story, "status", VALID_STATUSES, prefix, errors)
    _validate_enum(story, "priority", VALID_PRIORITIES, prefix, errors)
    _validate_enum(story, "size", VALID_SIZES, prefix, errors)


def _validate_story_lists(
    story: dict, prefix: str, all_numbers: set[int], errors: list[str]
) -> None:
    """Validate the list fields (when present): tasks, acceptance_criteria, labels, blocked_by."""
    if "tasks" in story:
        _require_nonempty_str_list(story, "tasks", prefix, errors)
    if "acceptance_criteria" in story:
        _require_nonempty_str_list(story, "acceptance_criteria", prefix, errors)
    if "labels" in story:
        _validate_labels(story, prefix, errors)
    if "blocked_by" in story:
        _validate_story_blocked_by(story, prefix, all_numbers, errors)


def _validate_labels(story: dict, prefix: str, errors: list[str]) -> None:
    """labels must be a list of strings containing ≥1 work-type label."""
    labels = story["labels"]
    if not isinstance(labels, list):
        errors.append(f"{prefix}.labels: expected array")
        return
    if not all(isinstance(v, str) for v in labels):
        errors.append(f"{prefix}.labels: all entries must be str")
        return
    if not any(lab in WORK_TYPE_LABELS for lab in labels):
        errors.append(
            f"{prefix}.labels: must include at least one work-type label "
            f"from {WORK_TYPE_LABELS}"
        )


def _validate_story_blocked_by(
    story: dict, prefix: str, all_numbers: set[int], errors: list[str]
) -> None:
    """blocked_by must be a list of issue numbers; each resolves in-file, no self-block."""
    blocked_by = story["blocked_by"]
    if not isinstance(blocked_by, list):
        errors.append(f"{prefix}.blocked_by: expected array")
        return
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in blocked_by):
        errors.append(f"{prefix}.blocked_by: all entries must be int (issue numbers)")
        return
    own = story.get("issue_number")
    for dep in blocked_by:
        if dep == own:
            errors.append(f"{prefix}.blocked_by: a story may not block itself (#{dep})")
        elif dep not in all_numbers:
            errors.append(
                f"{prefix}.blocked_by: #{dep} does not resolve to an issue number in this file"
            )


def _validate_story_scalars(story: dict, prefix: str, errors: list[str]) -> None:
    """Validate the numeric fields (when present): goal/notes prose, points, issue_number."""
    if "goal" in story:
        _require_nonempty_str(story, "goal", prefix, errors)
    if "notes" in story:
        _require_field(story, "notes", str, prefix, errors)
    if "points" in story:
        _validate_points(story, prefix, errors)
    if "issue_number" in story:
        _validate_issue_number(story, prefix, errors)


def _validate_points(story: dict, prefix: str, errors: list[str]) -> None:
    """points must be a real number (not bool)."""
    points = story["points"]
    if isinstance(points, bool) or not isinstance(points, (int, float)):
        errors.append(f"{prefix}.points: expected number, got {type(points).__name__}")


def _validate_issue_number(story: dict, prefix: str, errors: list[str]) -> None:
    """issue_number must be an int (``0`` = not yet converted)."""
    num = story["issue_number"]
    if isinstance(num, bool) or not isinstance(num, int):
        errors.append(f"{prefix}.issue_number: expected int, got {type(num).__name__}")


# ── Generic helpers ────────────────────────────────────────────────────────


def _require_field(
    obj: dict, field: str, expected_type: type, prefix: str, errors: list[str]
) -> None:
    """Append errors when obj[field] is missing or has the wrong type."""
    if field not in obj:
        errors.append(f"{prefix}: missing required field '{field}'")
    elif not isinstance(obj[field], expected_type):
        errors.append(
            f"{prefix}.{field}: expected {expected_type.__name__}, "
            f"got {type(obj[field]).__name__}"
        )


def _require_nonempty_str(
    obj: dict, field: str, prefix: str, errors: list[str]
) -> None:
    """Append errors when obj[field] is missing, not a str, or blank after strip."""
    if field not in obj:
        errors.append(f"{prefix}: missing required field '{field}'")
    elif not isinstance(obj[field], str):
        errors.append(f"{prefix}.{field}: expected str, got {type(obj[field]).__name__}")
    elif not obj[field].strip():
        errors.append(f"{prefix}.{field}: must not be empty")


def _require_nonempty_str_list(
    obj: dict, field: str, prefix: str, errors: list[str]
) -> None:
    """Validate a required list-of-string field with at least one entry."""
    if field not in obj:
        errors.append(f"{prefix}: missing required field '{field}'")
        return
    val = obj[field]
    if not isinstance(val, list):
        errors.append(f"{prefix}.{field}: expected array")
    elif not val:
        errors.append(f"{prefix}.{field}: must have at least one entry")
    elif not all(isinstance(v, str) for v in val):
        errors.append(f"{prefix}.{field}: all entries must be str")


def _validate_enum(
    obj: dict, field: str, allowed: set[str], prefix: str, errors: list[str]
) -> None:
    """Validate that a string field's value is in the allowed set (presence elsewhere)."""
    val = obj.get(field)
    if isinstance(val, str) and val not in allowed:
        errors.append(f"{prefix}.{field}: '{val}' not in {allowed}")


# ── CLI entrypoint (projects validate <path>) ──────────────────────────────


def _load_backlog(path: Path) -> tuple[dict | None, str | None]:
    """Read and parse a backlog JSON file, returning data or an error message."""
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"error: file not found: {path}"
    except json.JSONDecodeError as exc:
        return None, f"error: invalid JSON in {path}: {exc}"


def run(path: str | Path) -> int:
    """Validate the backlog at ``path``; print results and return an exit code.

    Args:
        path (str | Path): Path to the backlog JSON file.

    Returns:
        int: 0 if the file passes; 1 if errors found or the file can't be read.
    """
    data, err = _load_backlog(Path(path))
    if err is not None:
        print(err)
        return 1
    errors = validate(data)
    if errors:
        for line in errors:
            print(line)
        return 1
    print("Backlog validation passed")
    return 0
