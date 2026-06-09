import sys
from pathlib import Path
import argparse

sys.path.insert(0, str(Path.cwd() / ".claude"))
from scripts.utils.hook import Hook  # type: ignore
from scripts.lib.state_store import StateStore  # type: ignore
from scripts.lib.extractor import extract_section  # type: ignore

from pathlib import Path


def is_valid_path(path_str: str) -> bool:
    try:
        path = Path(path_str)
        path.resolve(strict=False)
        return True
    except (OSError, ValueError):
        return False


def extract_file_paths(content: str) -> list[str]:
    file_paths = extract_section(content, "Files to Touch")[1].splitlines()

    fp_list = []
    for file_path in file_paths:
        if is_valid_path(file_path):
            parsed_file_path = file_path.strip().removeprefix("- ").strip()
            fp_list.append(parsed_file_path)

    return fp_list


def get_hook_event_name(hook_input: dict) -> str:
    return hook_input.get("hook_event_name", "")


def get_content(hook_input: dict) -> str:
    return hook_input.get("tool_input", {}).get("content", "")


def get_old_string(hook_input: dict) -> str:
    return hook_input.get("tool_input", {}).get("old_string", "")


def get_new_string(hook_input: dict) -> str:
    return hook_input.get("tool_input", {}).get("new_string", "")


def get_file_path(hook_input: dict) -> str:
    return hook_input.get("tool_input", {}).get("file_path", "")


def patch_edit_content(hook_input: dict) -> str:
    content = get_content(hook_input)
    old_string = get_old_string(hook_input)
    new_string = get_new_string(hook_input)
    if not old_string or not new_string:
        return content
    return content.replace(old_string, new_string)


def is_plan_directory(path: str) -> bool:
    directory = str(Path(path).parent)
    return directory.endswith(".claude/plans")


def main() -> None:
    hook_input = Hook.read_stdin()
    session_id = hook_input.get("session_id", "")
    file_path = get_file_path(hook_input)
    tool_name = Hook.tool_name(hook_input)
    hook_event_name = Hook.hook_event_name(hook_input)

    state = StateStore(session_id=session_id)

    if hook_event_name != "PreToolUse":
        Hook.system_message("This hook is only allowed to be used in PreToolUse event.")
        return

    if not tool_name in ("Write", "Edit"):
        Hook.system_message(
            "This hook is only allowed to be used in Write or Edit tool."
        )
        return

    if not is_plan_directory(file_path):
        Hook.system_message(
            "File path is not in plan directory. Skipping file paths extraction."
        )
        return

    content = (
        get_content(hook_input)
        if tool_name == "Write"
        else patch_edit_content(hook_input)
    )

    extracted_file_paths = extract_file_paths(content)

    if not extracted_file_paths:
        Hook.block(
            "No file paths found. Please add valid file paths in the 'Files to Touch' section."
        )
        return

    state.set_file_paths(extracted_file_paths)
    Hook.system_message(f"File paths: {extracted_file_paths}")


if __name__ == "__main__":
    main()
