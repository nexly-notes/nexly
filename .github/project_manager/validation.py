"""Pure backlog validation — no GitHub calls, shared by manager/sync/CLI.

``blocked_by`` entries may be **ints** (GitHub issue numbers — the durable
form, minted by ``sync``) or **strings** (another item's exact title — the
pre-mint authoring form). :func:`validate_backlog` catches everything that
would corrupt the title→number conversion or the GitHub edge pass: duplicate
item titles, non-int/str entries, dangling title refs, self-blocks, duplicate
references, and dependency cycles. Dangling **int** refs stay legal (they may
point at external issues).
"""
from __future__ import annotations

from typing import Any


def _dict_tasks(story: dict[str, Any]) -> list[dict]:
    """Return only dict-shaped tasks (plain-string checklist lines skipped)."""
    return [t for t in story.get("tasks", []) if isinstance(t, dict)]


def _collect_items(backlog: dict) -> list[dict]:
    """Flatten stories + their dict-shaped sub-issues into one item list."""
    items: list[dict] = []
    for story in backlog.get("stories", []):
        items.append(story)
        items.extend(_dict_tasks(story))
    return items


def _duplicate_title_errors(items: list[dict]) -> list[str]:
    """Flag titles used by more than one item (breaks title→number mapping)."""
    seen: set[str] = set()
    errors: list[str] = []
    for item in items:
        title = item.get("title") or ""
        if not title:
            continue
        if title in seen:
            errors.append(f"Duplicate item title: '{title}' (titles must be unique)")
        seen.add(title)
    return errors


def _title_by_number(items: list[dict]) -> dict[int, str]:
    """Index in-file items by minted ``issue_number``."""
    return {
        item["issue_number"]: item.get("title", "")
        for item in items
        if item.get("issue_number") is not None
    }


def _normalize_entry(
    entry: int | str, title_by_num: dict[int, str]
) -> tuple[str, int | str]:
    """Reduce an entry to a comparable key (int 5 ≡ the title of issue 5)."""
    if isinstance(entry, int) and entry in title_by_num:
        return ("title", title_by_num[entry])
    if isinstance(entry, str):
        return ("title", entry)
    return ("number", entry)


def _entry_errors(
    item: dict, titles: set[str], title_by_num: dict[int, str]
) -> list[str]:
    """Validate one item's ``blocked_by`` list (types, dangling, self, dups)."""
    errors: list[str] = []
    label = item.get("title") or "?"
    seen_keys: set[tuple[str, int | str]] = set()
    for entry in item.get("blocked_by", []):
        if isinstance(entry, bool) or not isinstance(entry, (int, str)):
            errors.append(
                f"Item '{label}': blocked_by entry {entry!r} must be an "
                "issue number (int) or item title (str)"
            )
            continue
        if isinstance(entry, str) and entry not in titles:
            errors.append(
                f"Item '{label}': blocked_by title {entry!r} does not match "
                "any item title in the backlog"
            )
            continue
        if entry == item.get("title") or (
            item.get("issue_number") is not None and entry == item.get("issue_number")
        ):
            errors.append(f"Item '{label}': blocked by itself ({entry!r})")
            continue
        key = _normalize_entry(entry, title_by_num)
        if key in seen_keys:
            errors.append(
                f"Item '{label}': duplicate blocked_by reference ({entry!r})"
            )
            continue
        seen_keys.add(key)
    return errors


def _build_dependency_graph(
    items: list[dict], title_by_num: dict[int, str]
) -> dict[str, list[str]]:
    """Build a title-keyed blocker graph; in-file ints map to their titles.

    Int entries that don't resolve to an in-file item are external refs and
    contribute no edge (they can never close an in-file cycle). Self-edges
    are dropped — they're already reported as self-blocks.
    """
    graph: dict[str, list[str]] = {}
    for item in items:
        title = item.get("title") or ""
        if not title:
            continue
        deps: list[str] = []
        for entry in item.get("blocked_by", []):
            if isinstance(entry, str):
                deps.append(entry)
            elif isinstance(entry, int) and not isinstance(entry, bool):
                dep_title = title_by_num.get(entry)
                if dep_title:
                    deps.append(dep_title)
        graph[title] = [d for d in deps if d != title]
    return graph


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    """Return one dependency cycle as a title path (closed), or ``None``.

    Iterative three-color DFS; dangling titles (not graph nodes) are skipped
    — they're reported separately as dangling refs.
    """
    state = dict.fromkeys(graph, "white")
    for start in graph:
        if state[start] != "white":
            continue
        state[start] = "gray"
        path = [start]
        stack = [iter(graph[start])]
        while stack:
            neighbor = next(stack[-1], None)
            if neighbor is None:
                state[path.pop()] = "black"
                stack.pop()
                continue
            if neighbor not in graph or state[neighbor] == "black":
                continue
            if state[neighbor] == "gray":
                return path[path.index(neighbor):] + [neighbor]
            state[neighbor] = "gray"
            path.append(neighbor)
            stack.append(iter(graph[neighbor]))
    return None


def validate_backlog(backlog: dict) -> list[str]:
    """Validate the backlog's ``blocked_by`` graph across stories + sub-issues.

    Checks (in order): duplicate item titles, entry types (int | str),
    dangling title refs (exact, case-sensitive match), self-blocks,
    duplicate refs within one list (including int/title mixed duplicates),
    and dependency cycles. Backward-only array order is a workflow
    convention and is NOT enforced here.

    Args:
        backlog (dict): Parsed backlog data.

    Returns:
        list[str]: Human-readable errors; empty means valid.

    Example:
        >>> validate_backlog({"stories": [{"title": "A", "blocked_by": []}]})
        []
    """
    items = _collect_items(backlog)
    titles = {item.get("title") or "" for item in items} - {""}
    title_by_num = _title_by_number(items)
    errors = _duplicate_title_errors(items)
    for item in items:
        errors.extend(_entry_errors(item, titles, title_by_num))
    cycle = _find_cycle(_build_dependency_graph(items, title_by_num))
    if cycle:
        errors.append(
            "Dependency cycle: " + " -> ".join(f"'{t}'" for t in cycle)
        )
    return errors
