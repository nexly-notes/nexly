"""Project manager library: manage a unified-item solo-dev backlog.

Exposes the ``ProjectManager`` class with a ``run(command, **kwargs)``
dispatcher. The CLI wrapper lives in ``project_manager.cli``.

Schema summary (one **item** shape for stories AND sub-issues):
- Status enum: ``Backlog`` / ``In Progress`` / ``Done`` (case-sensitive).
- Priority enum: ``P0`` / ``P1`` / ``P2``.
- Items carry: title, description, status, priority, goal, notes,
  start_date, end_date, acceptance_criteria, labels, blocked_by (issue
  numbers), size, points, issue_number, and (parents only) tasks.
- Identity/dedup is ``title`` (pre-sync) → ``issue_number`` (post-sync).
  ``id`` and ``type`` are gone.
"""
from __future__ import annotations

import copy
import json as _json
import sys
from pathlib import Path
from typing import Any

from .config import DATA_PATHS

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

BACKLOG_PATH = Path(DATA_PATHS["backlog"])
TEMPLATES_DIR = Path(__file__).parent / "templates"
DEFAULT_TEMPLATE = TEMPLATES_DIR / "issue_view.txt"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
STATUS_ORDER = {
    "Done": 0,
    "In Progress": 1,
    "Ready": 2,
    "Backlog": 3,
}
# Derived "workable" status. `resolve` promotes unblocked Backlog items here;
# `ready` lists items already sitting in it.
READY_STATUS = "Ready"
# Backlog items in these statuses are candidates for `resolve` to mark Ready.
ACTIVE_STATUSES = {"Backlog"}

# Solo-dev state machine. `Backlog → Ready → In Progress → Done` is the happy
# path; the reverse arrows let a user demote a status without --force.
VALID_TRANSITIONS: dict[str, set[str]] = {
    "Backlog": {"In Progress", "Ready"},
    "Ready": {"In Progress", "Backlog"},
    "In Progress": {"Done", "Backlog"},
    "Done": {"In Progress"},
}

DEFAULT_COLUMNS: list[tuple[str, str, int]] = [
    ("#", "issue_number", 5),
    ("STATUS", "status", 12),
    ("PRI", "priority", 4),
    ("TITLE", "title", 50),
]

WIDE_COLUMNS: list[tuple[str, str, int]] = [
    ("#", "issue_number", 5),
    ("STATUS", "status", 12),
    ("PRI", "priority", 4),
    ("SIZE", "size", 6),
    ("PTS", "points", 4),
    ("TITLE", "title", 40),
]

BACKLOG_DEFAULT: dict[str, Any] = {
    "project": "",
    "description": "",
    "dates": {},
    "stories": [],
}

# Groom fields shared by every fresh (lean) item. ``title``/``description``
# are filled by the builder; ``tasks`` is added only to parent items.
_LEAN_ITEM_BASE: dict[str, Any] = {
    "description": "",
    "status": "Backlog",
    "priority": "",
    "goal": "",
    "notes": "",
    "start_date": "",
    "end_date": "",
    "acceptance_criteria": [],
    "labels": [],
    "blocked_by": [],
    "size": "",
    "points": None,
    "issue_number": None,
}

# Fields surfaced on a normalized (flattened) item row.
_ITEM_VIEW_FIELDS: tuple[str, ...] = (
    "title", "description", "issue_number", "status", "priority",
    "blocked_by", "acceptance_criteria", "labels", "goal", "notes",
    "size", "points", "start_date", "end_date",
)

_NUMERIC_SORT_FIELDS = {"issue_number", "points"}

# ---------------------------------------------------------------------------
# JSON primitives
# ---------------------------------------------------------------------------


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return _json.loads(_json.dumps(default))
    return _json.loads(path.read_text(encoding="utf-8"))


def _save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps(data, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Item identity / lookup
# ---------------------------------------------------------------------------


def _item_matches_key(item: dict[str, Any], key: str) -> bool:
    """Return True if *item* is identified by *key* (issue number or title).

    Identity is the GitHub ``issue_number`` (matched as a string) once
    minted, falling back to a case-insensitive ``title`` match pre-sync.

    Args:
        item (dict): Item (story or sub-issue) record or normalized row.
        key (str): Issue number (as text) or title to match against.

    Returns:
        bool: True when the item's number or title equals ``key``.

    Example:
        >>> _item_matches_key({"title": "X", "issue_number": 7}, "7")
        True
    """
    target = str(key).strip()
    num = item.get("issue_number")
    if num is not None and str(num) == target:
        return True
    return str(item.get("title", "")).lower() == target.lower()


def _find_item_by_key(
    backlog: dict, key: str
) -> tuple[dict | None, dict | None]:
    """Find any item (story or nested sub-issue) by issue number or title.

    Searches stories first, then each story's ``tasks``, so a number/title
    resolves uniformly across both nesting levels.

    Args:
        backlog (dict): Parsed backlog data.
        key (str): Issue number (as text) or title.

    Returns:
        tuple[dict | None, dict | None]: ``(item, parent)`` — ``parent`` is
        ``None`` for a top-level story, else the owning story. ``(None,
        None)`` when nothing matches.

    Example:
        >>> _find_item_by_key({"stories": [{"title": "S"}]}, "S")  # doctest: +SKIP
        Return: ({"title": "S"}, None)
    """
    for story in backlog.get("stories", []):
        if _item_matches_key(story, key):
            return story, None
        for task in story.get("tasks", []):
            if _item_matches_key(task, key):
                return task, story
    return None, None


def _title_exists(backlog: dict, title: str) -> bool:
    item, _ = _find_item_by_key(backlog, title)
    return item is not None


# ---------------------------------------------------------------------------
# Item normalization (flattened view used by list/view/summary)
# ---------------------------------------------------------------------------


def _normalize_item(item: dict, parent_key: str = "") -> dict[str, Any]:
    """Project an item onto the flat row shape used by list/view/summary.

    Args:
        item (dict): Story or sub-issue record.
        parent_key (str): Owning story's title for a sub-issue; ``""`` for
            a top-level story.

    Returns:
        dict[str, Any]: Row with every ``_ITEM_VIEW_FIELDS`` key plus
        ``parent_id``.

    Example:
        >>> _normalize_item({"title": "X"}, "P")["parent_id"]
        'P'
    """
    row = {field: item.get(field) for field in _ITEM_VIEW_FIELDS}
    row["parent_id"] = parent_key
    return row


def _flatten_items(backlog: dict) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for story in backlog.get("stories", []):
        items.append(_normalize_item(story))
    for story in backlog.get("stories", []):
        parent_title = story.get("title", "")
        for task in story.get("tasks", []):
            items.append(_normalize_item(task, parent_title))
    return items


# ---------------------------------------------------------------------------
# Sorting / filtering
# ---------------------------------------------------------------------------


def _sort_key(field: str, item: dict[str, Any]) -> Any:
    val = item.get(field, "")
    if val is None:
        val = ""
    if field == "priority":
        return PRIORITY_ORDER.get(val, 99)
    if field == "status":
        return STATUS_ORDER.get(val, 99)
    if field in _NUMERIC_SORT_FIELDS:
        return val if isinstance(val, (int, float)) else 0
    return str(val).lower()


def _matches(item: dict[str, Any], filters: dict[str, str]) -> bool:
    for field, value in filters.items():
        item_val = item.get(field)
        if item_val is None:
            return False
        if isinstance(item_val, list):
            if value.lower() not in [str(v).lower() for v in item_val]:
                return False
        elif str(item_val).lower() != value.lower():
            return False
    return True


# ---------------------------------------------------------------------------
# Status transitions / dependency helpers
# ---------------------------------------------------------------------------


def _validate_transition(current: str, new: str) -> str | None:
    allowed = VALID_TRANSITIONS.get(current)
    if allowed is None:
        return f"Unknown current status '{current}'"
    if new not in allowed:
        return (
            f"Cannot move from '{current}' to '{new}' (allowed: "
            f"{', '.join(sorted(allowed))}). Use --force to override."
        )
    return None


def is_unblocked(item_blocked_by: list[int], status_by_number: dict[int, str]) -> bool:
    return all(status_by_number.get(dep, "") == "Done" for dep in item_blocked_by)


def _record_status(status: dict[int, str], item: dict) -> None:
    num = item.get("issue_number")
    if num is not None:
        status[num] = item.get("status", "")


def build_status_map_from_backlog(backlog: dict) -> dict[int, str]:
    """Map every item's ``issue_number`` to its ``status`` (parents + children).

    ``blocked_by`` lists hold issue numbers, so the map is keyed by number
    across both nesting levels — a story can be blocked by a sub-issue and
    vice versa. Items without an ``issue_number`` contribute nothing (they
    can't be a numeric blocker target yet).

    Args:
        backlog (dict): Parsed backlog data.

    Returns:
        dict[int, str]: ``{issue_number: status}``.

    Example:
        >>> build_status_map_from_backlog(
        ...     {"stories": [{"issue_number": 5, "status": "Done"}]})
        {5: 'Done'}
    """
    status: dict[int, str] = {}
    for story in backlog.get("stories", []):
        _record_status(status, story)
        for task in story.get("tasks", []):
            _record_status(status, task)
    return status


# Aliases retained because `ready` calls them internally.
_is_unblocked = is_unblocked
_build_status_map_from_backlog = build_status_map_from_backlog


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def _format_list(val: Any) -> str:
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else "(none)"
    if val is None or val == "":
        return "(none)"
    return str(val)


def _format_cell(val: Any, width: int) -> str:
    if val is None:
        val = ""
    if isinstance(val, list):
        val = ", ".join(str(v) for v in val)
    return _truncate(str(val), width).ljust(width)


def _print_table(
    items: list[dict[str, Any]], columns: list[tuple[str, str, int]]
) -> None:
    header = "  ".join(h.ljust(w) for h, _, w in columns)
    print(header)
    print("-" * len(header))
    for t in items:
        parts = [_format_cell(t.get(k, ""), w) for _, k, w in columns]
        print("  ".join(parts))
    print(f"\n{len(items)} task(s)")


def _template_value(key: str, val: Any) -> str:
    if key == "acceptance_criteria" and isinstance(val, list):
        return "\n".join(f"  - {i}" for i in val) if val else "-"
    if isinstance(val, list):
        return ", ".join(str(i) for i in val) if val else "-"
    if val is None or val == "":
        return "-"
    return str(val)


def _render_template(item: dict[str, Any], template_path: Path) -> str:
    tpl = template_path.read_text(encoding="utf-8")
    values = {k: _template_value(k, v) for k, v in item.items()}
    return tpl.format_map(values)


def _view_raw(item: dict[str, Any]) -> None:
    max_label = max(len(k) for k in item) + 1
    for k, v in item.items():
        label = f"{k}:".ljust(max_label)
        print(f"  {label}  {_format_list(v)}")


def _print_child_row(c: dict[str, Any]) -> None:
    print(f"  {c.get('status', ''):<12} {c.get('title', '')}")


def _print_children_block(children: list[dict], header: str, empty_msg: str) -> None:
    if not children:
        print(empty_msg)
        return
    print(header)
    for c in children:
        _print_child_row(c)


# ---------------------------------------------------------------------------
# list helpers
# ---------------------------------------------------------------------------


_LIST_FILTER_ATTR_TO_FIELD = {
    "status": "status",
    "priority": "priority",
}


def _build_list_filters(**kwargs: Any) -> dict[str, str]:
    filters: dict[str, str] = {}
    for attr, field in _LIST_FILTER_ATTR_TO_FIELD.items():
        val = kwargs.get(attr)
        if val:
            filters[field] = val
    return filters


def _resolve_story_title(items: list[dict], story: str) -> str | None:
    for t in items:
        if t.get("parent_id"):
            continue
        if _item_matches_key(t, story):
            return t.get("title", "")
    return None


def _apply_story_filter(items: list[dict], story: str | None) -> list[dict]:
    if not story:
        return items
    target = _resolve_story_title(items, story)
    if target is None:
        return []
    return [t for t in items if t.get("parent_id") == target]


def _item_key(item: dict[str, Any]) -> str:
    num = item.get("issue_number")
    return str(num) if num is not None else item.get("title", "")


def _print_keys(keys: list[str], fmt: str) -> None:
    if fmt == "newline":
        print("\n".join(keys))
    elif fmt == "json":
        print(_json.dumps(keys))
    else:
        print(",".join(keys))


def _list_output(
    items: list[dict], wide: bool, keys_only: bool, keys_format: str, as_json: bool
) -> int:
    if as_json:
        print(_json.dumps(items, indent=2))
        return 0
    if keys_only:
        keys = [k for k in (_item_key(t) for t in items) if k]
        _print_keys(keys, keys_format)
        return 0
    _print_table(items, WIDE_COLUMNS if wide else DEFAULT_COLUMNS)
    return 0


# ---------------------------------------------------------------------------
# view helpers
# ---------------------------------------------------------------------------


def _view_ready_tasks(items: list[dict], title: str, as_json: bool) -> int:
    children = [
        t for t in items
        if t.get("parent_id") == title and t.get("status") == "Backlog"
    ]
    if as_json:
        print(_json.dumps(children, indent=2))
        return 0
    _print_children_block(
        children, f"Ready tasks ({title}) — {len(children)}:", "No ready tasks found."
    )
    return 0


def _view_ac(item: dict, title: str, as_json: bool) -> int:
    ac = item.get("acceptance_criteria", [])
    if as_json:
        print(_json.dumps(ac, indent=2))
        return 0
    if not ac:
        print("No acceptance criteria found.")
        return 0
    print(f"Acceptance Criteria ({title}):")
    for i, criterion in enumerate(ac, 1):
        print(f"  {i}. {criterion}")
    return 0


def _view_children(items: list[dict], title: str, as_json: bool) -> int:
    children = [t for t in items if t.get("parent_id") == title]
    if as_json:
        print(_json.dumps(children, indent=2))
        return 0
    _print_children_block(
        children, f"Child tasks ({len(children)}):", "No child tasks found."
    )
    return 0


def _view_full_output(item: dict, raw: bool, template: str | None) -> int:
    if raw:
        _view_raw(item)
        return 0
    tpl_path = Path(template) if template else DEFAULT_TEMPLATE
    if not tpl_path.exists():
        print(f"Template not found: {tpl_path}", file=sys.stderr)
        return 1
    print(_render_template(item, tpl_path))
    return 0


def _view_full_with_children(
    item: dict, items: list[dict], title: str, raw: bool, template: str | None
) -> int:
    rc = _view_full_output(item, raw, template)
    if rc != 0:
        return rc
    children = [t for t in items if t.get("parent_id") == title]
    if children:
        print(f"\nChild tasks ({len(children)}):")
        for c in children:
            _print_child_row(c)
    return rc


def _dispatch_view(
    item: dict,
    items: list[dict],
    raw: bool,
    template: str | None,
    tasks: bool,
    ready_tasks: bool,
    ac: bool,
    as_json: bool,
) -> int:
    title = item.get("title", "")
    if ready_tasks:
        return _view_ready_tasks(items, title, as_json)
    if ac:
        return _view_ac(item, title, as_json)
    if tasks:
        return _view_children(items, title, as_json)
    if as_json:
        print(_json.dumps(item, indent=2))
        return 0
    return _view_full_with_children(item, items, title, raw, template)


# ---------------------------------------------------------------------------
# summary helpers
# ---------------------------------------------------------------------------


def _group_items(items: list[dict], field: str) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for t in items:
        val = t.get(field, "(none)")
        if val is None or val == "":
            val = "(none)"
        if isinstance(val, list):
            val = _format_list(val)
        groups.setdefault(str(val), []).append(t)
    return groups


def _print_summary_rows(groups: dict[str, list[dict]], field: str) -> None:
    order_map = {
        "status": STATUS_ORDER,
        "priority": PRIORITY_ORDER,
    }
    order = order_map.get(field, {})
    sorted_keys = sorted(groups.keys(), key=lambda k: order.get(k, 99))
    header = f"  {'GROUP'.ljust(20)}  {'COUNT':>5}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for key in sorted_keys:
        print(f"  {key.ljust(20)}  {len(groups[key]):>5}")


# ---------------------------------------------------------------------------
# update helpers
# ---------------------------------------------------------------------------


_STORY_UPDATE_FIELDS = (
    "status", "priority", "title", "description", "goal", "notes",
    "size", "points", "start_date", "end_date", "labels",
    "acceptance_criteria",
)


def _collect_updates(values: dict[str, Any]) -> dict[str, Any]:
    return {
        f: v for f, v in values.items()
        if f in _STORY_UPDATE_FIELDS and v is not None
    }


def _apply_updates(item: dict, updates: dict) -> None:
    for field, value in updates.items():
        item[field] = value


def _check_status_transition(item: dict, updates: dict, force: bool) -> str | None:
    if "status" not in updates or force:
        return None
    return _validate_transition(item.get("status", ""), updates["status"])


# ---------------------------------------------------------------------------
# progress helpers
# ---------------------------------------------------------------------------


def _all_tasks(backlog: dict) -> list[dict]:
    tasks: list[dict] = []
    for s in backlog.get("stories", []):
        tasks.extend(s.get("tasks", []))
    return tasks


def _print_progress_overall(tasks: list[dict], backlog: dict) -> None:
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("status") == "Done")
    project = backlog.get("project", "")
    description = backlog.get("description", "")
    print(f"{project} - {description}")
    print("=" * 40)
    if total > 0:
        print(f"Overall: {done}/{total} tasks done ({done / total * 100:.0f}%)")
    else:
        print("Overall: No tasks")


def _print_story_status_distribution(stories: list[dict]) -> None:
    counts: dict[str, int] = {}
    for s in stories:
        st = s.get("status", "(none)")
        counts[st] = counts.get(st, 0) + 1
    if not counts:
        return
    print("\nStory status distribution:")
    for status in sorted(counts, key=lambda s: STATUS_ORDER.get(s, 99)):
        print(f"  {status:<12} {counts[status]}")


def _print_story_completion(stories: list[dict]) -> None:
    total = len(stories)
    done = sum(1 for s in stories if s.get("status") == "Done")
    print(f"\nStory completion: {done}/{total} stories done")
    for story in sorted(stories, key=lambda s: STATUS_ORDER.get(s.get("status", ""), 99)):
        status = story.get("status", "")
        print(f"  {status:<12} {story.get('title', '')[:50]}")


def _print_per_story_row(story: dict) -> None:
    title = story.get("title", "")[:40]
    story_tasks = story.get("tasks", [])
    total = len(story_tasks)
    if total == 0:
        print(f"  {title:<40} (no tasks)")
        return
    done = sum(1 for t in story_tasks if t.get("status") == "Done")
    print(f"  {title:<40} {done}/{total} ({done / total * 100:.0f}%)")


def _print_per_story(stories: list[dict]) -> None:
    print("\nPer-story task completion:")
    for story in stories:
        _print_per_story_row(story)


# ---------------------------------------------------------------------------
# ready helpers
# ---------------------------------------------------------------------------


_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


def _filter_ready_stories(
    stories: list[dict], status_by_number: dict[int, str], story_filter: str | None
) -> list[dict]:
    return [
        s for s in stories
        if s.get("status") in ACTIVE_STATUSES
        and _is_unblocked(s.get("blocked_by", []), status_by_number)
        and (story_filter is None or _item_matches_key(s, story_filter))
    ]


def _filter_ready_status(
    stories: list[dict], story_filter: str | None
) -> list[dict]:
    return [
        s for s in stories
        if s.get("status") == READY_STATUS
        and (story_filter is None or _item_matches_key(s, story_filter))
    ]


def _ready_sort_key(story: dict) -> tuple:
    """Composite sort key for `ready`: priority then title.

    Args:
        story (dict): Story record with priority/title.

    Returns:
        tuple: ``(priority_rank, title_lower)`` — lower sorts first.

    Example:
        >>> _ready_sort_key({"title": "B", "priority": "P0"})
        (0, 'b')
    """
    return (
        _PRIORITY_RANK.get(story.get("priority") or "", 99),
        str(story.get("title", "")).lower(),
    )


def _story_ready_json(item: dict) -> dict:
    return {
        "title": item.get("title", ""),
        "issue_number": item.get("issue_number"),
        "status": item.get("status", ""),
        "blocked_by": item.get("blocked_by", []),
    }


def _ready_to_json(stories: list[dict]) -> list[dict]:
    return [_story_ready_json(s) for s in stories]


def _print_ready_row(item: dict) -> None:
    print(f"  {item.get('status', ''):<12} {item.get('title', '')[:50]}")


def _print_ready_list(stories: list[dict]) -> None:
    print(f"Ready stories ({len(stories)}):")
    print("-" * 50)
    for item in stories:
        _print_ready_row(item)


def _resolve_to_ready(story: dict) -> int:
    if story.get("status") == "Backlog":
        story["status"] = READY_STATUS
        return 1
    return 0


def _resolve_unblocked_in_place(stories: list[dict]) -> int:
    return sum(_resolve_to_ready(s) for s in stories)


# ---------------------------------------------------------------------------
# Add-issue / add-subissue builders
# ---------------------------------------------------------------------------


def _build_lean_item(
    title: str, description: str | None = None, *, include_tasks: bool = True
) -> dict:
    """Build a fresh lean item (groom fields empty, ``status`` Backlog).

    Args:
        title (str): Item title (its pre-sync identity).
        description (str | None): Free-text context; defaults to ``""``.
        include_tasks (bool): Add an empty ``tasks`` list (parents only).
            Sub-issues are leaves and omit the key.

    Returns:
        dict: New item with every schema field present.

    Example:
        >>> _build_lean_item("X")["status"]
        'Backlog'
    """
    item = copy.deepcopy(_LEAN_ITEM_BASE)
    item["title"] = title
    item["description"] = description or ""
    if include_tasks:
        item["tasks"] = []
    return item


# ---------------------------------------------------------------------------
# ProjectManager
# ---------------------------------------------------------------------------


class ProjectManager:
    """Manage a backlog (stories with nested sub-issues) in a single JSON file."""

    _COMMAND_MAP: dict[str, str] = {
        "list": "list_items",
        "ls": "list_items",
        "view": "view",
        "summary": "summary",
        "update": "update",
        "add-issue": "add_issue",
        "add-subissue": "add_subissue",
        "progress": "progress",
        "sync": "sync",
        "pull": "pull",
        "ready": "ready",
        "resolve": "resolve",
    }

    def __init__(self, backlog_path: Path | None = None) -> None:
        self.backlog_path = Path(backlog_path) if backlog_path else BACKLOG_PATH

    # -- dispatch ----------------------------------------------------------

    def run(self, command: str, **kwargs: Any) -> int:
        method_name = self._COMMAND_MAP.get(command)
        if method_name is None:
            raise ValueError(f"Unknown command: {command}")
        return getattr(self, method_name)(**kwargs)

    # -- I/O ---------------------------------------------------------------

    def load_backlog(self) -> dict:
        return _load_json(self.backlog_path, BACKLOG_DEFAULT)

    def save_backlog(self, data: dict) -> None:
        _save_json(data, self.backlog_path)

    def load_all_items(self) -> list[dict[str, Any]]:
        return _flatten_items(self.load_backlog())

    # -- list --------------------------------------------------------------

    def list_items(
        self,
        *,
        status: str | None = None,
        priority: str | None = None,
        subissues: str | None = None,
        sort_by: str | None = None,
        reverse: bool = False,
        wide: bool = False,
        keys_only: bool = False,
        keys_format: str = "comma",
        json: bool = False,
    ) -> int:
        items = self.load_all_items()
        filters = _build_list_filters(status=status, priority=priority)
        items = [t for t in items if _matches(t, filters)]
        items = _apply_story_filter(items, subissues)
        if sort_by:
            items.sort(key=lambda t: _sort_key(sort_by, t), reverse=reverse)
        return _list_output(items, wide, keys_only, keys_format, json)

    # -- view --------------------------------------------------------------

    def view(
        self,
        *,
        key: str,
        raw: bool = False,
        template: str | None = None,
        tasks: bool = False,
        ready_tasks: bool = False,
        ac: bool = False,
        json: bool = False,
    ) -> int:
        items = self.load_all_items()
        item = next((t for t in items if _item_matches_key(t, key)), None)
        if not item:
            print(f"Item not found: {key}", file=sys.stderr)
            return 1
        return _dispatch_view(item, items, raw, template, tasks, ready_tasks, ac, json)

    # -- summary -----------------------------------------------------------

    def summary(self, *, group_by: str = "status") -> int:
        items = self.load_all_items()
        groups = _group_items(items, group_by)
        print(f"Summary by {group_by}  ({len(items)} items)\n")
        _print_summary_rows(groups, group_by)
        return 0

    # -- add-issue / add-subissue -----------------------------------------

    def add_issue(self, *, title: str, description: str | None = None) -> int:
        """Append a lean top-level story keyed by its (unique) title.

        Args:
            title (str): Story title — must be globally unique.
            description (str | None): Free-text context; defaults to ``""``.

        Returns:
            int: 0 on success, 1 if the title already exists.

        SideEffect:
            Appends to ``backlog["stories"]`` and writes the file.

        Example:
            >>> ProjectManager(p).add_issue(title="Research X")  # doctest: +SKIP
            Return: 0
        """
        data = self.load_backlog()
        if _title_exists(data, title):
            print(f"Duplicate title: {title}", file=sys.stderr)
            return 1
        data.setdefault("stories", []).append(_build_lean_item(title, description))
        self.save_backlog(data)
        print(f"Added issue: {title}")
        return 0

    def add_subissue(
        self, *, story: str, title: str, description: str | None = None
    ) -> int:
        """Append a lean child item (leaf) under a top-level story.

        Args:
            story (str): Parent identity — issue number (text) or title.
            title (str): Child title — must be globally unique.
            description (str | None): Free-text context; defaults to ``""``.

        Returns:
            int: 0 on success; 1 if the parent is missing, is itself a
            sub-issue (nesting is one level), or the title duplicates.

        SideEffect:
            Appends to the parent story's ``tasks`` and writes the file.

        Example:
            >>> ProjectManager(p).add_subissue(story="7", title="Sub")  # doctest: +SKIP
            Return: 0
        """
        data = self.load_backlog()
        parent, grandparent = _find_item_by_key(data, story)
        if parent is None or grandparent is not None:
            print(f"Parent story not found: {story}", file=sys.stderr)
            return 1
        if _title_exists(data, title):
            print(f"Duplicate title: {title}", file=sys.stderr)
            return 1
        parent.setdefault("tasks", []).append(
            _build_lean_item(title, description, include_tasks=False)
        )
        self.save_backlog(data)
        print(f"Added sub-issue: {title}")
        return 0

    # -- update ------------------------------------------------------------

    def update(
        self,
        *,
        key: str,
        status: str | None = None,
        priority: str | None = None,
        title: str | None = None,
        description: str | None = None,
        goal: str | None = None,
        notes: str | None = None,
        size: str | None = None,
        points: int | None = None,
        labels: list[str] | None = None,
        acceptance_criteria: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        force: bool = False,
    ) -> int:
        """Update any item (story or sub-issue) resolved by number or title.

        Args:
            key (str): Issue number (text) or title of the target item.
            status, priority, title, description, goal, notes, size, points,
            labels, acceptance_criteria, start_date, end_date: Fields to set
            when not ``None``. ``labels``/``acceptance_criteria`` replace the
            whole list. ``force`` bypasses the status-transition guard.

        Returns:
            int: 0 on success; 1 if not found, nothing to update, or an
            illegal status transition without ``force``.

        SideEffect:
            Mutates the matched item in-place and writes the file.

        Example:
            >>> ProjectManager(p).update(key="7", status="Done")  # doctest: +SKIP
            Return: 0
        """
        values = {
            "status": status, "priority": priority, "title": title,
            "description": description, "goal": goal, "notes": notes,
            "size": size, "points": points, "labels": labels,
            "acceptance_criteria": acceptance_criteria,
            "start_date": start_date, "end_date": end_date,
        }
        return self._apply_update(key, values, force)

    def _apply_update(self, key: str, values: dict, force: bool) -> int:
        data = self.load_backlog()
        item, _ = _find_item_by_key(data, key)
        if item is None:
            print(f"Item not found: {key}", file=sys.stderr)
            return 1
        return self._commit_update(data, item, values, force, key)

    def _commit_update(
        self, data: dict, item: dict, values: dict, force: bool, key: str
    ) -> int:
        updates = _collect_updates(values)
        if not updates:
            print("Nothing to update. Use --help to see available options.", file=sys.stderr)
            return 1
        err = _check_status_transition(item, updates, force)
        if err:
            print(err, file=sys.stderr)
            return 1
        _apply_updates(item, updates)
        self.save_backlog(data)
        print(f"Updated {key}")
        return 0

    # -- progress ----------------------------------------------------------

    def progress(self) -> int:
        backlog = self.load_backlog()
        stories = backlog.get("stories", [])
        tasks = _all_tasks(backlog)
        _print_progress_overall(tasks, backlog)
        _print_story_status_distribution(stories)
        if stories:
            _print_story_completion(stories)
            _print_per_story(stories)
        return 0

    # -- ready -------------------------------------------------------------

    def ready(
        self,
        *,
        story: str | None = None,
        top: bool = False,
        json: bool = False,
    ) -> int:
        """List top-level stories whose ``status`` is ``Ready``.

        ``Ready`` is the derived "workable" status that ``resolve`` writes;
        ``ready`` is read-only and never mutates the backlog. Sub-issues are
        never listed. Stories rank by ``(priority, title)``.

        Args:
            story (str | None): Narrow to one story (title or issue number).
            top (bool): Keep only the single top-ranked story.
            json (bool): Emit JSON instead of a table.

        Returns:
            int: ``0`` always (an empty result is not an error).

        Example:
            >>> ProjectManager(path).ready()  # doctest: +SKIP
            Ready stories (1):
            Return: 0
        """
        stories = self.load_backlog().get("stories", [])
        ready_stories = _filter_ready_status(stories, story)
        ready_stories.sort(key=_ready_sort_key)
        if top:
            ready_stories = ready_stories[:1]
        return self._render_ready(ready_stories, json)

    def _render_ready(self, stories: list[dict], as_json: bool) -> int:
        if not stories:
            print("No ready stories found.")
            return 0
        if as_json:
            print(_json.dumps(_ready_to_json(stories), indent=2))
            return 0
        _print_ready_list(stories)
        return 0

    # -- resolve -----------------------------------------------------------

    def resolve(self, *, story: str | None = None, top: bool = False) -> int:
        """Promote unblocked ``Backlog`` stories to ``Ready`` and save.

        Readiness is derived: a story qualifies when its ``status`` is
        ``Backlog`` and every ``blocked_by`` issue number resolves to a
        ``Done`` item (across both nesting levels). Sub-issues are never
        resolved. This is the only place readiness is computed and written.

        Args:
            story (str | None): Narrow to one story (title or issue number).
            top (bool): Resolve only the single top-ranked candidate.

        Returns:
            int: ``0`` always.

        SideEffect:
            Sets ``status = "Ready"`` on each qualifying story in
            ``stories[]`` and rewrites ``backlog.json``.

        Example:
            >>> ProjectManager(path).resolve()  # doctest: +SKIP
            Resolved 1 item(s) to Ready.
            Return: 0
            SideEffect:
                stories[i][status] = "Ready"  (for each unblocked Backlog story)
        """
        backlog = self.load_backlog()
        stories = backlog.get("stories", [])
        status_by_number = _build_status_map_from_backlog(backlog)
        candidates = _filter_ready_stories(stories, status_by_number, story)
        candidates.sort(key=_ready_sort_key)
        if top:
            candidates = candidates[:1]
        return self._apply_resolve(candidates, backlog)

    def _apply_resolve(self, candidates: list[dict], backlog: dict) -> int:
        if not candidates:
            print("No backlog items to resolve.")
            return 0
        resolved = _resolve_unblocked_in_place(candidates)
        self.save_backlog(backlog)
        print(f"Resolved {resolved} item(s) to Ready.")
        return 0

    # -- sync / pull -------------------------------------------------------

    def sync(
        self,
        *,
        dry_run: bool = False,
        delete_all: bool = False,
        repo: str | None = None,
        project: int | None = None,
        owner: str | None = None,
    ) -> int:
        from .sync import Syncer

        syncer = Syncer(
            backlog_path=self.backlog_path,
            repo=repo, project=project, owner=owner,
        )
        if delete_all:
            return syncer.run("delete-all", dry_run=dry_run)
        return syncer.run("sync", dry_run=dry_run)

    def pull(
        self,
        *,
        dry_run: bool = False,
        repo: str | None = None,
        project: int | None = None,
        owner: str | None = None,
    ) -> int:
        """Mirror GitHub state back into ``backlog.json`` (thin delegate).

        Args:
            dry_run (bool): Print a per-item diff and write nothing.
            repo, project, owner: Optional config overrides.

        Returns:
            int: ``Syncer.run("pull")`` exit code.

        SideEffect:
            Rewrites ``backlog.json`` unless ``dry_run`` (via the Syncer).

        Example:
            >>> ProjectManager(p).pull(dry_run=True)  # doctest: +SKIP
            Return: 0
        """
        from .sync import Syncer

        syncer = Syncer(
            backlog_path=self.backlog_path,
            repo=repo, project=project, owner=owner,
        )
        return syncer.run("pull", dry_run=dry_run)
