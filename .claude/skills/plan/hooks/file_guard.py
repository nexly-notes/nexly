import sys
from pathlib import Path
import argparse

sys.path.insert(0, str(Path.cwd() / ".claude"))
from scripts.utils.hook import Hook  # type: ignore
from scripts.lib.state_store import StateStore  # type: ignore
from scripts.config.config import Config  # type: ignore


def get_file_path(hook_input: dict) -> str:
    file_path = hook_input.get("tool_input", {}).get("file_path", "")
    return file_path


def get_tool_name(hook_input: dict) -> str:
    tool_name = hook_input.get("tool_name", "")
    return tool_name


def main() -> None:
    hook_input = Hook.read_stdin()
    session_id = hook_input.get("session_id", "")
    file_path = get_file_path(hook_input)
    if not file_path:
        Hook.system_message("File path is required.")
        return
    state = StateStore(session_id=session_id)
    if not state.is_file_path_in_scope(file_path):
        Hook.block(
            f"File path {file_path} is not in scope. Stop and ask the user first if you need to touch any other files for this task."
        )
        return

    Hook.system_message(f"File path {file_path} is allowed to use this tool.")
