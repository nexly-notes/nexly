"""GitHub Projects (v2) field model: metadata, fields, and field writes.

Owns everything about the project board itself — fetching the project id /
fields / items, the ``field_name -> {id, type, options}`` field-map, ensuring
fields exist, and writing a single field value (both the ``gh project
item-edit`` CLI path and the GraphQL mutation builders used by the batched
field pass).

Field specs: ``CONVERT_FIELDS`` (``Status`` + ``Priority`` + ``Size`` +
``Points``) are ensured + synced by ``convert`` — the single push for the
groomed backlog.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from projects import gh


# ── Field specs ────────────────────────────────────────────────────────────

# Board fields the convert pass ensures + syncs from the groomed backlog.
CONVERT_FIELDS: list[tuple[str, str, list[str] | None]] = [
    ("Status", "SINGLE_SELECT", ["Backlog", "In Progress", "Done"]),
    ("Priority", "SINGLE_SELECT", ["P0", "P1", "P2"]),
    ("Size", "SINGLE_SELECT", ["XS", "S", "M", "L", "XL"]),
    ("Points", "NUMBER", None),
]

# Keys `gh project item-list --format json` emits alongside `id`/`content`
# when the corresponding project field is set; mapped to canonical names.
_REMOTE_RAW_KEYS: list[tuple[str, str]] = [
    ("Status", "status"),
    ("Priority", "priority"),
    ("Size", "size"),
    ("Points", "points"),
]


# ── Project metadata ───────────────────────────────────────────────────────


_PROJECT_ID_QUERY = """
query($owner: String!, $number: Int!) {
  user(login: $owner) {
    projectV2(number: $number) { id }
  }
}
"""


def get_project_id(project_number: int, owner: str) -> str:
    """Get the project node ID via GraphQL.

    Assumes a user-owned project; an org-owned project answers under
    ``organization`` instead of ``user`` and would 404 here.
    """
    result = gh.gh_json(
        [
            "gh", "api", "graphql",
            "-f", f"query={_PROJECT_ID_QUERY}", "-f", f"owner={owner}",
            "-F", f"number={project_number}",
        ]
    )
    return result["data"]["user"]["projectV2"]["id"]


def get_project_fields(project_number: int, owner: str) -> list[dict]:
    """Get all project fields with their IDs and options."""
    return gh.gh_json(
        [
            "gh", "project", "field-list", str(project_number),
            "--owner", owner, "--format", "json",
        ]
    ).get("fields", [])


def get_project_items(project_number: int, owner: str) -> list[dict]:
    """Get all project items."""
    return gh.gh_json(
        [
            "gh", "project", "item-list", str(project_number),
            "--owner", owner, "--format", "json", "--limit", "200",
        ]
    ).get("items", [])


def build_field_map(fields: list[dict]) -> dict[str, dict]:
    """Build ``field_name -> {id, type, options: {option_name: option_id}}``."""
    fmap: dict[str, dict] = {}
    for f in fields:
        entry: dict[str, Any] = {"id": f["id"], "type": f.get("type", "")}
        if "options" in f:
            entry["options"] = {opt["name"]: opt["id"] for opt in f["options"]}
        fmap[f.get("name", "")] = entry
    return fmap


def find_item_id(items: list[dict], number: int) -> str | None:
    """Find the project item ID that matches the given issue number."""
    for item in items:
        if item.get("content", {}).get("number") == number:
            return item["id"]
    return None


# ── Field creation ─────────────────────────────────────────────────────────


def _create_project_field_mutation(project_id: str, field_name: str, inner: str) -> str:
    return f"""
    mutation {{
      createProjectV2Field(input: {{
        projectId: {json.dumps(project_id)},
        {inner},
        name: {json.dumps(field_name)}
      }}) {{
        projectV2Field {{ ... on ProjectV2Field {{ id }} }}
      }}
    }}
    """


def _single_select_options_arg(options: list[str]) -> str:
    return ", ".join(
        f'{{name: {json.dumps(opt)}, color: GRAY, description: ""}}' for opt in options
    )


def _create_single_select_field(project_id: str, field_name: str, options: list[str]) -> None:
    mutation = (
        f"mutation {{ createProjectV2Field(input: {{"
        f"projectId: {json.dumps(project_id)},"
        f" dataType: SINGLE_SELECT,"
        f" name: {json.dumps(field_name)},"
        f" singleSelectOptions: [{_single_select_options_arg(options)}]"
        f"}}) {{ projectV2Field {{ ... on ProjectV2SingleSelectField {{ id }} }} }} }}"
    )
    gh.run(["gh", "api", "graphql", "-f", f"query={mutation}"], check=False)


def _create_simple_field(project_id: str, field_name: str, data_type: str) -> None:
    mutation = _create_project_field_mutation(project_id, field_name, f"dataType: {data_type}")
    gh.run(["gh", "api", "graphql", "-f", f"query={mutation}"], check=False)


def ensure_project_field(
    project_id: str,
    field_name: str,
    field_type: str,
    field_map: dict[str, dict],
    options: list[str] | None = None,
) -> bool:
    """Create a project field if it doesn't exist. Returns True if created."""
    if field_name in field_map:
        return False
    print(f"  Creating missing field: {field_name} ({field_type})")
    if field_type == "SINGLE_SELECT" and options:
        _create_single_select_field(project_id, field_name, options)
    elif field_type in ("NUMBER", "TEXT"):
        _create_simple_field(project_id, field_name, field_type)
    return True


# ── Single field write (gh project item-edit) ──────────────────────────────


def _value_flag(value: Any) -> tuple[str, str] | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return "--number", str(value)
    if isinstance(value, str):
        return "--text", str(value)
    return None


def _append_value_flag(cmd: list[str], field_name: str, value: Any) -> bool:
    flag = _value_flag(value)
    if flag is None:
        print(f"  ⚠ Unsupported value type for '{field_name}': {type(value)}", file=sys.stderr)
        return False
    cmd += list(flag)
    return True


def _append_option_flag(
    cmd: list[str], field_name: str, options: dict[str, str], value: Any
) -> bool:
    option_id = options.get(value)
    if not option_id:
        print(
            f"  ⚠ Option '{value}' not found for field '{field_name}'. "
            f"Available: {list(options.keys())}",
            file=sys.stderr,
        )
        return False
    cmd += ["--single-select-option-id", option_id]
    return True


def _item_edit_cmd(project_id: str, item_id: str, field_id: str) -> list[str]:
    return [
        "gh", "project", "item-edit", "--id", item_id,
        "--field-id", field_id, "--project-id", project_id,
    ]


def set_field(
    project_id: str,
    item_id: str,
    field_map: dict[str, dict],
    field_name: str,
    value: Any,
) -> None:
    """Set a project field value using the correct flags for its type."""
    if value is None or value == "":
        return
    field = field_map.get(field_name)
    if not field:
        print(f"  ⚠ Field '{field_name}' not found in project", file=sys.stderr)
        return
    cmd = _item_edit_cmd(project_id, item_id, field["id"])
    ok = (
        _append_option_flag(cmd, field_name, field["options"], value)
        if field.get("options")
        else _append_value_flag(cmd, field_name, value)
    )
    if ok:
        gh.run(cmd, check=False)


# ── GraphQL field-value builders (batched field pass) ──────────────────────


def _gql_value(field_name: str, value: Any) -> dict[str, str] | None:
    if isinstance(value, bool):
        print(f"  ⚠ Unsupported value type for '{field_name}': {type(value)}", file=sys.stderr)
        return None
    if isinstance(value, (int, float)):
        return {"number": str(value)}
    if isinstance(value, str):
        return {"text": json.dumps(value)}
    print(f"  ⚠ Unsupported value type for '{field_name}': {type(value)}", file=sys.stderr)
    return None


def _gql_option_value(
    options: dict[str, str], field_name: str, value: Any
) -> dict[str, str] | None:
    option_id = options.get(value)
    if not option_id:
        print(
            f"  ⚠ Option '{value}' not found for field '{field_name}'. "
            f"Available: {list(options.keys())}",
            file=sys.stderr,
        )
        return None
    return {"singleSelectOptionId": json.dumps(option_id)}


def build_field_value(
    field_map: dict[str, dict], field_name: str, value: Any
) -> dict[str, str] | None:
    """Convert a field name + value into the GraphQL ``value`` input object."""
    if value is None or value == "":
        return None
    field = field_map.get(field_name)
    if not field:
        print(f"  ⚠ Field '{field_name}' not found in project", file=sys.stderr)
        return None
    if field.get("options"):
        return _gql_option_value(field["options"], field_name, value)
    return _gql_value(field_name, value)


def mutation_for_field(
    project_id: str, item_id: str, field_id: str, gql_value: dict[str, str], idx: int
) -> str:
    value_parts = ", ".join(f"{k}: {v}" for k, v in gql_value.items())
    return (
        f"m{idx}: updateProjectV2ItemFieldValue(input: {{"
        f"projectId: {json.dumps(project_id)}, "
        f"itemId: {json.dumps(item_id)}, "
        f"fieldId: {json.dumps(field_id)}, "
        f"value: {{{value_parts}}}"
        f"}}) {{ projectV2Item {{ id }} }}"
    )


# ── Remote field-value snapshot ────────────────────────────────────────────


def extract_item_field_values(raw_item: dict[str, Any]) -> dict[str, Any]:
    """Pull known project-field values from a ``gh project item-list`` entry.

    Reads the lowercased top-level keys the CLI emits and translates them to
    canonical field names. Absent / empty values are dropped so the caller
    can treat ``key in result`` as "remote has a value for this field".

    Example:
        >>> extract_item_field_values({"id": "X", "status": "Backlog"})
        {'Status': 'Backlog'}
    """
    result: dict[str, Any] = {}
    for canonical, raw_key in _REMOTE_RAW_KEYS:
        val = raw_item.get(raw_key)
        if val is None or val == "":
            continue
        result[canonical] = val
    return result


def build_remote_values_map(items: list[dict]) -> dict[str, dict[str, Any]]:
    """Build ``{item_id: {field_name: current_value}}`` for all project items."""
    return {
        item["id"]: extract_item_field_values(item)
        for item in items if item.get("id")
    }


def should_skip_field(field_name: str, raw: Any, remote_values: dict[str, Any]) -> bool:
    """True when the in-memory value already matches the remote snapshot."""
    if field_name not in remote_values:
        return False
    return remote_values[field_name] == raw
