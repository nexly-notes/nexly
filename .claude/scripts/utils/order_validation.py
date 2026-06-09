def validate_order(
    prev: str | None, next_item: str, order: list[str]
) -> tuple[bool, str]:

    if next_item not in order:
        return False, f"Invalid next item '{next_item}'"

    # First transition has no prev — force callers to hit the canonical start.
    if prev is None:
        if next_item != order[0]:
            return False, f"Must start with '{order[0]}', not '{next_item}'"
        return True, f"Allowed to start with '{order[0]}'"

    if prev not in order:
        return False, f"Invalid previous item '{prev}'"

    prev_idx = order.index(prev)
    next_idx = order.index(next_item)

    # Three distinct error messages so the caller can tell whether the user
    # is re-invoking, going backwards, or skipping ahead.
    if next_idx == prev_idx:
        return False, (
            f"Cannot re-invoke '{prev}'. The phase has already been entered — "
            f"advance to the next phase, or complete its tasks instead of restarting it."
        )
    if next_idx < prev_idx:
        return False, f"Cannot go backwards from '{prev}' to '{next_item}'"
    if next_idx > prev_idx + 1:
        skipped = order[prev_idx + 1 : next_idx]
        return False, f"Must complete {skipped} before '{next_item}'"

    return True, f"Phase is allowed to transition to '{next_item}'"
