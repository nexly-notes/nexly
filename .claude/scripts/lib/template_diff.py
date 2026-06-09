"""markdown.py — Pure markdown parsers (sections, tables, bullets, bold meta).

None of these helpers touch the filesystem or raise on malformed input —
missing sections / tables / lines yield empty structures so callers can
iterate without guarding every call.
"""

import re
from typing import Literal

from markdown_it import MarkdownIt as _md

TABLE_PATTERN = r"^(\|.+\|[ \t]*\n)(\|[ \t]*[-:]+.*\|[ \t]*\n)((?:\|.+\|[ \t]*\n?)*)"


def extract_md_sections(md: str, level: int) -> list[tuple[str, str]]:
    """
    Extract every section at the given heading level from a markdown string.

    A section ends at the next heading of the same-or-higher level (so ``##``
    stops at ``##`` or ``#`` but not ``###``). Windows ``\\r\\n`` line endings
    are normalized first because the regex assumes ``\\n``.

    Args:
        md (str): Full markdown text.
        level (int): Heading depth (1 for ``#``, 2 for ``##``, etc.).

    Returns:
        list[tuple[str, str]]: ``[(heading_text, body), ...]`` in document
        order. Bodies have surrounding whitespace stripped.

    Example:
        >>> extract_md_sections("## A\\nbody-a\\n## B\\nbody-b", 2)
        [('A', 'body-a'), ('B', 'body-b')]
    """
    md = md.replace("\r\n", "\n")
    pattern = re.compile(
        rf"""
        ^[#]{{{level}}}(?![#])[ \t]+([^\n]+?)[ \t]*$  # heading text
        \n?                                             # optional newline after heading
        (.*?)                                           # content (DOTALL)
        (?=
            ^[#]{{1,{level}}}(?![#])[ \t]+              # next same-or-higher heading
            | \Z
        )
        """,
        re.MULTILINE | re.DOTALL | re.VERBOSE,
    )

    return [(m.group(1), m.group(2).strip()) for m in pattern.finditer(md)]


def extract_section(md: str, heading: str) -> tuple[str, str]:
    """
    Extract the section from a markdown string.
    """
    all_heading_levels = get_all_heading_levels(md)
    return next(
        (
            section
            for level in all_heading_levels
            for section in extract_md_sections(md, level)
            if section[0] == heading
        ),
        (heading, ""),
    )


def get_all_heading_levels(md: str) -> tuple[int, ...]:
    """
    Check the heading levels in a markdown string.
    """

    import re

    _HEADING_RE = re.compile(r"^(#{1,6})\s", re.MULTILINE)

    def _heading_levels(md: str) -> tuple[int, ...]:
        """Return a sorted tuple of ATX heading levels present in `md`."""
        levels = {len(hashes) for hashes in _HEADING_RE.findall(md)}
        return tuple(sorted(levels))

    return _heading_levels(md)


def extract_headings(md: str, levels: tuple[int, ...] | None = None) -> list[str]:
    """
    Extract the headings from a markdown string.
    """
    if levels is None:
        levels = get_all_heading_levels(md)
    headings = []
    for level in levels:
        headings.extend([heading for heading, _ in extract_md_sections(md, level)])
    return headings


def extract_section_body(md: str, heading: str) -> str:
    """
    Extract the body from a markdown string.
    """
    import re

    _comment_pattern = re.compile(r"<!--[\s\S]*?-->")

    def _extract_comments(md: str) -> list[str]:
        return [m.strip() for m in _comment_pattern.findall(md)]

    section = extract_section(md, heading)

    heading, body = section

    for comment in _extract_comments(body):
        body = body.replace(comment, "").strip()

    return body


_TABLE_PATTERN = re.compile(TABLE_PATTERN, re.MULTILINE)


def _parse_table_row(line: str, cols: int | None = None) -> list[str]:
    """Split a markdown ``| a | b | c |`` row into ``["a", "b", "c"]``.

    Example:
        >>> _parse_table_row("| a | b | c |")
        ['a', 'b', 'c']
        >>> _parse_table_row("| a | b | c |", cols=2)
        ['a', 'b']
    """
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells[:cols] if cols is not None else cells


def extract_table(
    md: str,
    rows: int | None = None,
    cols: int | None = None,
) -> list[list[str]]:
    """
    Extract the first markdown table found in *md*.

    The header separator row (``|---|---|``) is dropped so callers always get
    semantic rows. Pass ``rows`` / ``cols`` to truncate large tables — useful
    when only the first few cells matter (e.g. type prefixes from an ID
    conventions table).

    Args:
        md (str): Markdown text to search.
        rows (int | None): Max number of body rows to return (header always kept).
        cols (int | None): Max number of cells per row.

    Returns:
        list[list[str]]: Header row at index 0, then body rows. Empty list if
        no table is present.

    Example:
        >>> extract_table("| A | B |\\n|---|---|\\n| 1 | 2 |")
        [['A', 'B'], ['1', '2']]
    """
    match = _TABLE_PATTERN.search(md)
    if not match:
        return []

    header = _parse_table_row(match.group(1), cols)
    body_lines = match.group(3).strip().splitlines()
    if rows is not None:
        body_lines = body_lines[:rows]

    return [header] + [_parse_table_row(line, cols) for line in body_lines]


def check_list_type(
    list_type: Literal["bullet", "numbered", "checklist"], body: str
) -> bool:
    """
    Check if the content is a bullet item.
    """
    list_type_map = {
        "bullet": "- ",
        "numbered": "1. ",
        "checklist": "- [ ] ",
    }
    prefix = list_type_map[list_type]
    return all(line.strip().startswith(prefix) for line in body.splitlines())


def get_bullet_items_section(body: str) -> list[str]:
    """
    Get the bullet items section from a markdown string.
    """
    return [
        line.strip().removeprefix("- ").strip()
        for line in body.splitlines()
        if line.strip().startswith("- ")
    ]


def extract_list(
    list_type: Literal["bullet", "numbered", "checklist"], content: str
) -> list[str]:
    """
    Extract the list from a markdown string.
    """
    list_type_map = {
        "bullet": "- ",
        "numbered": "1. ",
        "checklist": "- [ ] ",
    }
    prefix = list_type_map[list_type]
    return [
        line.strip().removeprefix(prefix).strip()
        for line in content.splitlines()
        if line.strip().startswith(prefix)
    ]


def extract_bullet_items(content: str) -> list[str]:
    """
    Extract ``- item`` bullet items from a markdown blob.

    Args:
        content (str): Markdown text.

    Returns:
        list[str]: Bullet text with the leading ``- `` removed, in document order.

    Example:
        >>> extract_bullet_items("- foo\\n- bar\\nplain line")
        ['foo', 'bar']
    """
    return extract_list("bullet", content)


def extract_numbered_items(content: str) -> list[str]:
    """
    Extract ``1. item`` numbered items from a markdown blob.
    """
    return extract_list("numbered", content)


def extract_checklist_items(content: str) -> list[str]:
    """
    Extract ``- [ ] item`` checklist items from a markdown blob.
    """
    bullet_items = extract_bullet_items(content)
    if not bullet_items:
        return []
    if all(item.startswith("[ ] ") for item in bullet_items):
        return [item.removeprefix("[ ] ").strip() for item in bullet_items]
    return []


def match_substring(subject: str, candidates: list[str]) -> str | None:
    """
    Find a case-insensitive substring match between subject and any candidate.

    Matches in either direction (subject ⊆ candidate OR candidate ⊆ subject)
    plus equality, so partial titles like ``Add login`` will match the plan
    task ``Add login flow with OTP`` and vice versa.

    Args:
        subject (str): Candidate text to locate.
        candidates (list[str]): Allowed values to match against.

    Returns:
        str | None: The matched candidate (original casing/whitespace), or
        ``None`` if no entry matches.

    Example:
        >>> match_substring("Add login", ["Add login flow"])
        'Add login flow'
        >>> match_substring("totally unrelated", ["a", "b"]) is None
        True
    """
    # Normalize once; compare against each candidate's normalized form so
    # trailing spaces / mixed case never defeat a real match.
    normalized = subject.strip().lower()
    for c in candidates:
        c_lower = c.strip().lower()
        if normalized == c_lower or c_lower in normalized or normalized in c_lower:
            return c
    return None


def validate_bullet_section(section_name: str, body: str) -> None:
    """
    Enforce that a markdown section uses ``- item`` bullets (not ``###`` subsections).

    Args:
        section_name (str): Heading of the section being checked (for the error
            message — not used to look up the body).
        body (str): Markdown body of the section.

    Raises:
        ValueError: If ``###`` subsections appear in the body, or if no bullet
            items are present.

    Example:
        >>> validate_bullet_section("Tasks", "- one\\n- two")
        >>> # Raises ValueError when body has ### subsections or no bullets.
    """
    # Subsection + empty-bullets are separate authoring mistakes — two distinct
    # error messages so the writer knows which rule to fix.
    if "### " in body:
        raise ValueError(
            f"'{section_name}' must use bullet items (- item), not ### subsections. "
            f"See the plan template for the correct format."
        )
    if not any(line.strip().startswith("- ") for line in body.splitlines()):
        raise ValueError(
            f"'{section_name}' must have at least one bullet item (- item). "
            f"See the plan template for the correct format."
        )


def require_section(sections: dict[str, str], heading: str) -> list[str]:
    """
    Return non-empty bullet items from a required H2 section, or raise.

    Missing *and* empty sections both raise — callers use this to enforce that
    a review report actually lists file paths under a given heading.

    Args:
        sections (dict[str, str]): Section-map produced by
            :func:`extract_section_map`.
        heading (str): Required H2 heading text.

    Returns:
        list[str]: Bullet items found under the heading.

    Raises:
        ValueError: If the section is missing or contains no bullet items.

    Example:
        >>> require_section({"Files to revise": "- a.py"}, "Files to revise")
        ['a.py']
    """
    # Missing section short-circuits before the bullet walk — distinct error message
    # keeps the two failure modes diagnosable by the caller.
    if heading not in sections:
        raise ValueError(f"'{heading}' section is required")
    items = extract_bullet_items(sections[heading])
    if not items:
        raise ValueError(f"'{heading}' section is empty — provide file paths")
    return items


def extract_section_map(content: str, level: int) -> dict[str, str]:
    """
    Return ``{heading.strip(): body}`` for every section at the given heading level.

    Args:
        content (str): Full markdown text.
        level (int): Heading depth (1 for ``#``, 2 for ``##``, etc.).

    Returns:
        dict[str, str]: Heading-to-body map. Later sections with the same
        heading clobber earlier ones — by design, since duplicate headings
        in a single doc are an authoring bug.

    Example:
        >>> extract_section_map("## A\\nbody", 2)
        {'A': 'body'}
    """
    return {name.strip(): body for name, body in extract_md_sections(content, level)}


def extract_md_body(content: str) -> str:
    """
    Strip a YAML frontmatter block (``---ed ... ---``) and return the markdown body.

    Args:
        content (str): Full markdown including optional frontmatter.

    Returns:
        str: Body with leading newlines trimmed; the unchanged input if no
        frontmatter is present.

    Example:
        >>> extract_md_body("---\\nkey: val\\n---\\n# Title")
        '# Title'
    """
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return content


def extract_frontmatter(content: str) -> dict[str, str]:
    """
    Extract flat ``key: value`` pairs from a YAML frontmatter block.

    Only handles the simple ``key: value`` shape — nested YAML, lists, or
    multi-line values aren't supported because the workflow frontmatter
    schema is intentionally flat. Missing or malformed frontmatter returns
    ``{}`` so callers can ``.get(...)`` without exception handling.

    Args:
        content (str): Markdown text potentially starting with ``---``.

    Returns:
        dict[str, str]: Frontmatter keys to values; empty when absent.

    Example:
        >>> extract_frontmatter("---\\nsession_id: abc\\n---\\n# Title")
        {'session_id': 'abc'}
    """
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()
    return fm


_BOLD_METADATA_PATTERN = re.compile(r"^\*\*([^*:]+?):\*\*\s*(.*)$")


def extract_bold_metadata(content: str) -> dict[str, str]:
    """
    Parse bold-label metadata rows (``**Key:** value``) into a dict.

    Values are stripped of surrounding whitespace and backticks; placeholders
    like ``[your project]`` or ``<TBD>`` are returned as-is so callers can flag
    them as un-filled-in.

    Args:
        content (str): Markdown text containing bold metadata lines.

    Returns:
        dict[str, str]: ``{label: value}`` for every recognized line.

    Example:
        >>> extract_bold_metadata("**Status:** Draft\\n**Owner:** Alice")
        {'Status': 'Draft', 'Owner': 'Alice'}
    """
    meta: dict[str, str] = {}
    for line in content.splitlines():
        match = _BOLD_METADATA_PATTERN.match(line.strip())
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip().strip("`")
            meta[key] = value
    return meta


_TYPE_MAP = {
    "paragraph_open": "text",
    "bullet_list_open": "bullet",
    "ordered_list_open": "ordered_list",
    "fence": "code",
    "code_block": "code",
    "blockquote_open": "blockquote",
    "hr": "hr",
    "table_open": "table",
}


def _collect_body_blocks(tokens, start, end, source_lines):
    """Collect (type, content) for each top-level body token in the range."""
    blocks = []
    for i in range(start, end):
        t = tokens[i]
        if t.level != 0:  # skip nested tokens (inside lists, quotes, etc.)
            continue
        if t.type in _TYPE_MAP:
            # token.map is [start_line, end_line) in 0-indexed source lines
            content = "\n".join(source_lines[t.map[0] : t.map[1]]) if t.map else ""
            blocks.append({"type": _TYPE_MAP[t.type], "content": content})
    return blocks


def build_md_tree(markdown_text):
    # enable("table") because the default CommonMark preset doesn't recognize
    # GFM pipe tables — without this, tables parse as plain paragraphs.
    tokens = _md().enable("table").parse(markdown_text)
    source_lines = markdown_text.splitlines()
    heading_idxs = [i for i, t in enumerate(tokens) if t.type == "heading_open"]

    # capture orphan body before the first heading (or all of it if no headings)
    # so callers can diff "stuff written outside any section"
    pre_end = heading_idxs[0] if heading_idxs else len(tokens)
    pre_blocks = _collect_body_blocks(tokens, 0, pre_end, source_lines)

    sections = []
    for n, idx in enumerate(heading_idxs):
        body_start = idx + 3
        body_end = heading_idxs[n + 1] if n + 1 < len(heading_idxs) else len(tokens)
        blocks = _collect_body_blocks(tokens, body_start, body_end, source_lines)
        sections.append(
            {
                "level": int(tokens[idx].tag[1]),
                "text": tokens[idx + 1].content,
                "body_types": [b["type"] for b in blocks],
                "body_content": [b["content"] for b in blocks],
            }
        )

    root = {
        "level": 0,
        "text": "ROOT",
        "body_types": [b["type"] for b in pre_blocks],
        "body_content": [b["content"] for b in pre_blocks],
        "children": [],
    }
    stack = [root]
    for s in sections:
        node = {**s, "children": []}
        while stack[-1]["level"] >= node["level"]:
            stack.pop()
        stack[-1]["children"].append(node)
        stack.append(node)
    return root


def _format_kv_diff(label, template_val, actual_val):
    """Format a single-line template/actual diff."""
    return f"{label}\n  template: {template_val}\n  actual:   {actual_val}"


def _indent_block(text, prefix="    "):
    """Indent each line of text; return ``(empty)`` placeholder for empty input."""
    return (
        "".join(prefix + line for line in text.splitlines(keepends=True))
        if text
        else f"{prefix}(empty)"
    )


def _format_body_diff(
    section_name,
    template_types,
    actual_types,
    template_content,
    actual_content,
    path,
):
    """Format a body-mismatch report with type lines and raw template/actual content."""
    # Comma-join types so multi-block sections (e.g. ['text', 'bullet']) read cleanly
    t_types = ", ".join(template_types) or "(none)"
    a_types = ", ".join(actual_types) or "(none)"
    return (
        f"Section '{section_name}' not matching\n\n"
        f"Template received type: {t_types}\n"
        f"Actual received type: {a_types}\n\n"
        f"Template:\n{_indent_block(template_content)}\n\n"
        f"Actual:\n{_indent_block(actual_content)}\n\n"
        f"Path: {path}"
    )


_PLACEHOLDER_RE = re.compile(r"^\{[^}]+\}$")


def _is_placeholder(text):
    """True when heading text is a wildcard placeholder like ``{Plan Title}``."""
    return bool(_PLACEHOLDER_RE.match((text or "").strip()))


def _pair_sections(template_list, actual_list):
    """
    Pair template sections with actual sections.

    Pass 1 matches by exact heading text. Pass 2 lets any ``{placeholder}``
    template heading consume the next still-unpaired actual heading in order.
    Returns (paired, missing_in_actual, extra_in_actual).
    """
    a_remaining = list(actual_list)
    paired, t_unpaired = [], []
    # Pass 1: exact-name match consumes from actual on first hit
    for t in template_list:
        match_idx = next(
            (i for i, a in enumerate(a_remaining) if a.get("text") == t.get("text")),
            None,
        )
        if match_idx is not None:
            paired.append((t, a_remaining.pop(match_idx)))
        else:
            t_unpaired.append(t)
    # Pass 2: placeholder templates wildcard-match remaining actuals in order
    missing = []
    for t in t_unpaired:
        if _is_placeholder(t.get("text", "")) and a_remaining:
            paired.append((t, a_remaining.pop(0)))
        else:
            missing.append(t)
    return paired, missing, a_remaining


def _dump_node(node):
    """Render a section node + its body + children back into markdown text."""
    # rebuild the ATX heading marker from level so nested sections stay nested
    parts = [f"{'#' * node['level']} {node.get('text', '?')}"]
    parts.extend(c for c in node.get("body_content", []) if c)
    for child in node.get("children", []):
        parts.append(_dump_node(child))
    # join with blank line so heading/body/children get markdown's block separator;
    # strip trailing newlines per part so token slices that include them don't double up
    return "\n\n".join(p.rstrip("\n") for p in parts)


def _format_presence_diff(section_label, name, side, content):
    """Format a missing/extra section diff with the dumped body content."""
    # ``side`` is "missing" (present in template only) or "extra" (actual only)
    source = "expected" if side == "missing" else "actual"
    return (
        f"{section_label}: section '{name}' {side} in actual\n"
        f"{source.capitalize()} content:\n{_indent_block(content)}"
    )


def _diff_table_block(t_content, a_content, label):
    """Compare two markdown tables for column count, row count, and header text."""
    t_table = extract_table(t_content)
    a_table = extract_table(a_content)
    if not t_table or not a_table:
        # extract_table returns [] when the pattern doesn't match — skip silently
        # rather than spam diffs on something we can't parse on either side
        return []
    t_header, *t_body = t_table
    a_header, *a_body = a_table
    diffs = []
    if len(t_header) != len(a_header):
        diffs.append(
            _format_kv_diff(
                f"{label}: column count differs", len(t_header), len(a_header)
            )
        )
    if len(t_body) != len(a_body):
        diffs.append(
            _format_kv_diff(f"{label}: row count differs", len(t_body), len(a_body))
        )
    if t_header != a_header:
        diffs.append(_format_kv_diff(f"{label}: headers differ", t_header, a_header))
    return diffs


def _normalize_blocks(types, contents):
    """
    Collapse consecutive same-type blocks (e.g. two paragraphs become one).
    Adjacent ``text``/``text`` blocks differ only because of an authoring blank
    line — semantically they're one block, so treat them as such for comparison.
    Returns ``(merged_types, merged_contents)``.
    """
    out_types, out_contents = [], []
    for t, c in zip(types, contents):
        if out_types and out_types[-1] == t:
            out_contents[-1] = f"{out_contents[-1]}\n\n{c}"
        else:
            out_types.append(t)
            out_contents.append(c)
    return out_types, out_contents


def _diff_typed_blocks(types, t_contents, a_contents, here):
    """Per-block deep checks for matching body types (currently: tables)."""
    diffs = []
    for i, btype in enumerate(types):
        if btype == "table":
            label = (
                f"{here}: table block {i + 1}" if len(types) > 1 else f"{here}: table"
            )
            diffs.extend(_diff_table_block(t_contents[i], a_contents[i], label))
    return diffs


def _diff_matched_section(t, a, here):
    """Diff a template/actual pair already matched by heading name."""
    diffs = []
    if t["level"] != a["level"]:
        diffs.append(_format_kv_diff(f"{here}: level differs", t["level"], a["level"]))
    # normalize first so consecutive same-type blocks (typically paragraphs)
    # don't trigger spurious mismatches over blank-line authoring choices
    t_types, t_contents = _normalize_blocks(
        t.get("body_types", []), t.get("body_content", [])
    )
    a_types, a_contents = _normalize_blocks(
        a.get("body_types", []), a.get("body_content", [])
    )
    if t_types != a_types:
        diffs.append(
            _format_body_diff(
                t.get("text", "?"),
                t_types,
                a_types,
                "\n".join(t_contents),
                "\n".join(a_contents),
                here,
            )
        )
    else:
        # types align — run type-aware deep checks (table shape, etc.)
        diffs.extend(_diff_typed_blocks(t_types, t_contents, a_contents, here))
    diffs.extend(_compare_children(t["children"], a["children"], here))
    return diffs


def _compare_children(template_list, actual_list, path="root"):
    """
    Compare two lists of sibling sections.
    Sections are paired by exact heading text first, then ``{placeholder}``
    template headings consume any remaining unpaired actuals in order.
    """
    diffs = []
    section_label = "Top-level" if path == "root" else path
    paired, missing, extra = _pair_sections(template_list, actual_list)

    # missing/extra dumped with full body so the reader sees what's gone / new
    for node in missing:
        diffs.append(
            _format_presence_diff(
                section_label, node.get("text", "?"), "missing", _dump_node(node)
            )
        )
    for node in extra:
        diffs.append(
            _format_presence_diff(
                section_label, node.get("text", "?"), "extra", _dump_node(node)
            )
        )

    # for placeholder pairs, show the actual heading in the breadcrumb so paths
    # read like "Mock Feature Plan > Tasks" not "{Plan Title} > Tasks"
    for t, a in paired:
        display = (
            a.get("text", "?")
            if _is_placeholder(t.get("text", ""))
            else t.get("text", "?")
        )
        here = display if path == "root" else f"{path} > {display}"
        diffs.extend(_diff_matched_section(t, a, here))

    return diffs


def _compare_md_trees(template, actual) -> tuple[bool, list[str]]:
    """
    Compare two root nodes from build_md_tree (orphan body + heading tree).
    Returns (is_identical, list_of_differences).
    """
    diffs = []
    # diff orphan body that lives BEFORE any heading (or all of it if no headings)
    if template.get("body_types") != actual.get("body_types"):
        diffs.append(
            _format_body_diff(
                "Pre-heading content",
                template.get("body_types", []),
                actual.get("body_types", []),
                "\n".join(template.get("body_content", [])),
                "\n".join(actual.get("body_content", [])),
                "Top-level",
            )
        )
    diffs.extend(
        _compare_children(
            template.get("children", []), actual.get("children", []), "root"
        )
    )
    return (len(diffs) == 0, diffs)


def trees_identical(template, actual) -> tuple[bool, list[str]]:
    """Convenience wrapper: just returns True/False."""
    return _compare_md_trees(template, actual)
