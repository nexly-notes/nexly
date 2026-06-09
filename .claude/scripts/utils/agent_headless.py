"""subprocess_agents.py — Subprocess wrappers for git and headless agents.

Generic subprocess helpers (``run_git``, ``invoke_headless_agent``) — thin
wrappers around ``subprocess.run`` that swallow errors rather than raise, so
workflow code can treat "agent failed" and "agent said nothing" the same way.
Fail-open by design for the Claude/Codex helpers, because those calls enrich
context rather than gate control.

Public dataclasses (``ClaudeOptions``, ``CodexOptions``, ``InvokeConfig``,
``AgentResponse``) replace the old loose ``**kwargs`` so the agent-flavor
split is type-visible at call sites.
"""

import json
import subprocess
from typing import Annotated, Type, TypeVar, overload
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable
from typing_extensions import Literal


# ---------------------------------------------------------------------------
# Constants + type aliases
# ---------------------------------------------------------------------------


DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_TOOLS: tuple[str, ...] = ("Read", "Grep", "Glob")
DEFAULT_SETTINGS_PATH = "/home/emhar/claude-3PO/settings.json"
GIT_TIMEOUT_SECONDS = 30

ConformanceCheck = Callable[[str], tuple[bool, str]]


# ---------------------------------------------------------------------------
# Dataclasses — agent-flavor options + invocation config + parsed response
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClaudeConfig:

    model: str = "haiku"
    bare: bool = False
    tools: tuple[str, ...] = DEFAULT_TOOLS
    allowed_tools: tuple[str, ...] | None = None
    output_format: str = "text"
    settings: str | None = None
    session_id: str | None = None
    json_output: bool = False
    json_schema: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CodexConfig:

    session_id: str | None = None
    output_schema: Path | None = None
    json_output: bool = False
    model: str | None = None


AgentConfig = Annotated[ClaudeConfig | CodexConfig, Literal["codex", "claude"]]


# ---------------------------------------------------------------------------
# Argv builders — one per agent flavor, dispatched by option type
# ---------------------------------------------------------------------------


def build_claude_argv(prompt: str, options: ClaudeConfig) -> list[str]:
    argv: list[str] = ["claude"]
    if options.bare:
        argv.append("--bare")
    argv.extend(["-p", prompt])
    argv.extend(["--tools", ",".join(options.tools)])
    argv.extend(["--output-format", options.output_format])
    argv.extend(["--model", options.model])
    # Session resume is optional; only wire the flag when the caller pinned a session.
    if options.settings:
        argv.extend(["--settings", DEFAULT_SETTINGS_PATH])
    if options.allowed_tools:
        argv.extend(["--allowedTools", ",".join(options.allowed_tools)])
    if options.session_id:
        argv.extend(["--session-id", options.session_id])
    if options.json_output:
        argv.append("--json")
    if options.json_schema:
        argv.extend(["--json-schema", json.dumps(options.json_schema)])
    return argv


def build_codex_argv(prompt: str, options: CodexConfig) -> list[str]:
    argv = ["codex", "exec", "--skip-git-repo-check"]
    if options.json_output:
        argv.append("--json")
    if options.output_schema:
        argv.extend(["--output-schema", str(options.output_schema)])
    if options.session_id:
        argv.extend(["resume", options.session_id])

    argv.append(prompt)
    return argv


def build_argv(prompt: str, config: AgentConfig) -> list[str]:
    if isinstance(config, ClaudeConfig):
        return build_claude_argv(prompt, config)
    if isinstance(config, CodexConfig):
        return build_codex_argv(prompt, config)


# ---------------------------------------------------------------------------
# Headless agent invocation
# ---------------------------------------------------------------------------


def run_headless(
    prompt: str,
    config: AgentConfig,
    *,
    timeout: int,
    cwd: Path | None = None,
) -> str | None:
    argv = build_argv(prompt, config)
    try:
        result = subprocess.run(
            argv,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# JSONL response parsing
# ---------------------------------------------------------------------------


def parse_agent_response(raw: str) -> tuple[str, str, str]:
    session_id = ""
    text = ""
    # One scan: take first populated thread_id, overwrite text so last chunk wins.
    for line in raw.split("\n"):
        if not line.startswith("{"):
            continue
        data = json.loads(line)
        if not session_id:
            session_id = data.get("thread_id", "") or ""
        item_text = data.get("item", {}).get("text", "")
        if item_text:
            text = item_text
    return session_id, text, raw


# ---------------------------------------------------------------------------
# Self-correcting agent loop
# ---------------------------------------------------------------------------


CONFIG_MAP: dict[Literal["codex", "claude"], Type[AgentConfig]] = {
    "codex": CodexConfig,
    "claude": ClaudeConfig,
}


def run_headless_parallel(commands: list[list[str]]) -> list[str]:
    """Start all commands, wait for all, return list of (returncode, stdout, stderr)."""
    procs = [
        subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for cmd in commands
    ]
    results = [(p.wait(), *p.communicate()) for p in procs]
    if any(result[0] != 0 for result in results):
        return []
    return [result[1] for result in results]
