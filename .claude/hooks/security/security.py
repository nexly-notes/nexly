#!/usr/bin/env python3
"""
PreToolUse Hook: Security validation for dangerous commands and paths.

Blocks critical system-damaging operations using exit code 2.
"""

import re
import sys
from pathlib import Path
from typing import Any
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.utils.hook import Hook  # type: ignore

# Critical paths that should never be modified
CRITICAL_PATHS = {
    "/etc/passwd",
    "/etc/shadow",
    "/boot/",
    "/sys/",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}

# Critical command patterns (regex) - tuples of (pattern, description)
# Uses regex to avoid false positives with absolute paths
CRITICAL_COMMAND_PATTERNS = [
    (r"rm\s+-[rf]+\s+/\s*$", "rm -rf / (wipes root filesystem)"),
    (r"rm\s+-[rf]+\s+/\*", "rm -rf /* (wipes root contents)"),
    (r"rm\s+-[rf]+\s+/etc(?:\s|$)", "rm -rf /etc (destroys system config)"),
    (r"rm\s+-[rf]+\s+/boot(?:\s|$)", "rm -rf /boot (destroys bootloader)"),
    (r"rm\s+-[rf]+\s+/sys(?:\s|$)", "rm -rf /sys (destroys system interface)"),
    (r"dd\s+if=/dev/zero\s+of=/dev/", "dd to device (overwrites disk)"),
    (r"mkfs\.(ext|xfs|btrfs)", "mkfs (formats filesystem)"),
    (r">\s*/dev/sd", "redirect to disk device"),
    (r">\s*/dev/nvme", "redirect to nvme device"),
    (r":\(\)\{\s*:\|:&\s*\};:", "fork bomb"),
    (r"chmod\s+-[rR]+\s+777\s+/\s*$", "chmod 777 / (destroys permissions)"),
]

# Safe directories (operations here are allowed)
# No leading slash so both absolute and relative paths match
SAFE_DIRECTORIES = {".claude/", "src/", "tests/"}


def block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def read_stdin() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            print("Error: empty stdin", file=sys.stderr)
            sys.exit(1)
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)


def log(message: str) -> None:
    path = Path(__file__).parent.parent / "logs" / "security.log"
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(message + "\n")


def check_dangerous_path(file_path: str | None) -> tuple[bool, str | None]:
    """Return (False, reason) if path is dangerous, (True, None) otherwise."""
    if not file_path:
        return True, None
    # Skip safe project directories
    if any(safe_dir in file_path for safe_dir in SAFE_DIRECTORIES):
        return True, None

    for pattern in CRITICAL_PATHS:
        if pattern in file_path:
            return (
                False,
                f"BLOCKED: Attempting to modify critical system file: {pattern}",
            )

    return True, None


def check_dangerous_command(command: str | None) -> tuple[bool, str | None]:
    """Return (False, reason) if command is dangerous, (True, None) otherwise."""
    if not command:
        return True, None

    for pattern, description in CRITICAL_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return (
                False,
                f"BLOCKED: System-damaging command detected: {description}",
            )

    return True, None


def get_tool_input(raw_input: dict) -> dict | None:
    hook_event_name = raw_input.get("hook_event_name")
    tool_name = raw_input.get("tool_name")

    if hook_event_name is None:
        Hook.system_message("WARNING: hook_event_name is missing")

    if hook_event_name not in ("PreToolUse", "PostToolUse"):
        return None

    if not tool_name:
        Hook.system_message("WARNING: tool_name is missing")

    return raw_input.get("tool_input")


def validate_security(input_data: dict | None) -> None:
    """
    Validate tool input for security risks.

    Exits with code 2 if dangerous operation detected.
    Returns None if operation is safe.
    """
    if input_data is None:
        return

    tool_input = get_tool_input(input_data)
    if tool_input is None:
        return

    tool_name = input_data.get("tool_name")

    if tool_name in ("Write", "Edit", "MultiEdit"):
        file_path = tool_input.get("file_path")
        is_safe, error = check_dangerous_path(file_path)
        if not is_safe:
            Hook.block(error or "Unknown error")

    if tool_name == "Bash":
        command = tool_input.get("command")
        is_safe, error = check_dangerous_command(command)
        if not is_safe:
            Hook.block(error or "Unknown error")


def main():
    """Standalone entry point for direct execution."""
    input_data = read_stdin()
    validate_security(input_data)
    sys.exit(0)


if __name__ == "__main__":
    main()
