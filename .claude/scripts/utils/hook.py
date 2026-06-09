"""hook.py — Stdin/stdout protocol helpers for Claude Code hook scripts.

Claude Code invokes hook scripts with a JSON payload on stdin and reads
their decision back from stdout (or stderr) plus an exit code. This class
collects all the response shapes — allow, block, allow-with-context, system
message, discontinue — into named static methods so hook scripts can stay
declarative (``Hook.advanced_block(...)``) instead of hand-rolling JSON +
sys.exit calls everywhere.
"""

from typing import Any
import sys
import json


class Hook:
    """Static helpers for reading hook stdin and writing hook responses.

    Every method here calls ``sys.exit`` — they're intended as the *final*
    statement of a hook script. The exit code carries semantic meaning to
    Claude Code: 0 = allow / advisory, 1 = debug / error, 2 = block.

    Example:
        >>> Hook.success_response("ok")  # doctest: +SKIP
    """

    @staticmethod
    def read_stdin() -> dict[str, Any]:
        """
        Read and parse the hook payload from stdin.

        Exits with code 1 (treated as a debug error by Claude Code) on empty
        input or malformed JSON — there's no meaningful way to continue without
        a payload, so failing fast beats silently mis-routing.

        Returns:
            dict[str, Any]: Parsed JSON payload.

        Example:
            >>> payload = Hook.read_stdin()  # doctest: +SKIP
        """
        try:
            raw = sys.stdin.read()
            if not raw.strip():
                print("Error: empty stdin", file=sys.stderr)
                sys.exit(1)
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"Error: invalid JSON on stdin: {e}", file=sys.stderr)
            sys.exit(1)

    @staticmethod
    def advanced_output(output: dict[str, Any]) -> None:
        """
        Emit a structured hook response as JSON on stdout and exit 0.

        Args:
            output (dict[str, Any]): The full hook response object (must match
                Claude Code's ``hookSpecificOutput`` schema).

        Returns:
            None: Process exits before returning.

        Example:
            >>> Hook.advanced_output({"systemMessage": "ok"})  # doctest: +SKIP
        """
        print(json.dumps(output))
        sys.exit(0)

    @staticmethod
    def block(message: str) -> None:
        """
        Block the tool call by printing *message* on stderr and exiting 2.

        Exit code 2 is the simple "deny" signal — Claude sees the stderr
        message as the reason. Use :meth:`advanced_block` when you need the
        structured ``permissionDecision`` shape (e.g. for PreToolUse).

        Args:
            message (str): Human-readable block reason shown to Claude.

        Returns:
            None: Process exits before returning.

        Example:
            >>> Hook.block("not allowed")  # doctest: +SKIP
        """
        print(message, file=sys.stderr)
        sys.exit(2)

    @staticmethod
    def advanced_block(hook_event_name: str, message: str) -> None:
        """
        Emit a structured ``deny`` decision (used by PreToolUse-style hooks).

        Args:
            hook_event_name (str): Hook event name (e.g. ``"PreToolUse"``).
            message (str): Human-readable reason for the block.

        Returns:
            None: Process exits before returning.

        Example:
            >>> Hook.advanced_block("PreToolUse", "denied")  # doctest: +SKIP
        """
        output = {
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            },
        }
        Hook.advanced_output(output)

    @staticmethod
    def success_response(message: str) -> None:
        """Print *message* to stdout and exit 0 — the simple allow path.

        Example:
            >>> Hook.success_response("allowed")  # doctest: +SKIP
        """
        print(message)
        sys.exit(0)

    @staticmethod
    def debug(message: str) -> None:
        """Print *message* to stderr and exit 1 (Claude treats this as a debug error).

        Example:
            >>> Hook.debug("something off")  # doctest: +SKIP
        """
        print(message, file=sys.stderr)
        sys.exit(1)

    @staticmethod
    def system_message(message: str) -> None:
        """
        Emit a ``systemMessage`` JSON response — surfaces text in the chat without blocking.

        Args:
            message (str): Text to display in the Claude session.

        Returns:
            None: Process exits before returning.

        Example:
            >>> Hook.system_message("note for user")  # doctest: +SKIP
        """
        print(json.dumps({"systemMessage": message}))
        sys.exit(0)

    @staticmethod
    def discontinue(reason: str) -> None:
        """
        Tell Claude Code to stop the conversation entirely.

        Args:
            reason (str): User-visible reason for the stop.

        Returns:
            None: Process exits before returning.

        Example:
            >>> Hook.discontinue("workflow finished")  # doctest: +SKIP
        """
        output = {"continue": False, "stopReason": reason}
        print(json.dumps(output))
        sys.exit(0)

    @staticmethod
    def send_context(hook_event_name: str, context: str) -> None:
        """
        Inject *context* into the conversation as additional system context.

        The exact JSON shape depends on the hook event: PreToolUse needs an
        explicit ``permissionDecision: "allow"`` to confirm the tool may run,
        while post/start events only need ``additionalContext``. Unknown event
        names raise ``ValueError`` — silently dropping context would make the
        bug invisible.

        Args:
            hook_event_name (str): One of ``PreToolUse``, ``PostToolUse``,
                ``UserPromptSubmit``, ``SubagentStart``, ``SessionStart``.
            context (str): Text to surface to Claude as system context.

        Returns:
            None: Process exits before returning.

        Raises:
            ValueError: If *hook_event_name* isn't one of the supported events.

        Example:
            >>> Hook.send_context("PreToolUse", "extra context")  # doctest: +SKIP
        """
        match hook_event_name:
            case "PreToolUse":
                output: dict[str, Any] = {
                    "systemMessage": context,
                    "hookSpecificOutput": {
                        "hookEventName": hook_event_name,
                        "permissionDecision": "allow",
                        "permissionDecisionReason": "",
                        "additionalContext": context,
                    },
                }
            case "PostToolUse" | "UserPromptSubmit" | "SubagentStart" | "SessionStart":
                output = {
                    "systemMessage": context,
                    "hookSpecificOutput": {
                        "hookEventName": hook_event_name,
                        "additionalContext": context,
                    },
                }
            case _:
                raise ValueError(f"Invalid hook event name: {hook_event_name}")
        Hook.advanced_output(output)
        sys.exit(0)

    @staticmethod
    def allow(message: str) -> None:
        print(message)
        sys.exit(0)

    @staticmethod
    def hook_event_name(hook_input: dict) -> str:
        return hook_input.get("hook_event_name", "")

    @staticmethod
    def tool_name(hook_input: dict) -> str:
        return hook_input.get("tool_name", "")
