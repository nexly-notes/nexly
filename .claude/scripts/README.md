# Scripts — Workflow Hook System

Guardrail engine that enforces phase-based rules for the `claude-3PO` Claude Code plugin. Every Claude Code lifecycle event is routed through a dispatcher, validated against the current phase, recorded to a session-scoped state file, and resolved to decide whether the workflow advances.

## Architecture

```
Claude Code event (stdin JSON)
        │
        ▼
  dispatchers/*.py        ── entry points (one per hook event)
        │
        ├─► guardrails/*.py   ── validate ("allow" | "block")
        ├─► utils/recorder.py ── write raw data into state
        └─► utils/resolver.py ── evaluate state, complete phases,
                                  auto-start next phase,
                                  mark workflow complete
        │
        ▼
  stdout JSON (permissionDecision, continue:false, systemMessage, …)
```

All modules import from a shared `lib/` (I/O, extractors, parsers, state, violations, scoring, paths, shell), `config/` (declarative phase/agent/path config — `get_config()` returns a process-wide cached `Config()`), `constants/` (command whitelists, file patterns, phase sets, paths), and `models/` (Pydantic schema for state, batch entries).

**Layering rule:** `guardrails/*` never imports from `utils/*`, and `utils/recorder.py` never imports from `guardrails/*`. Pure helpers live in `lib/`; orchestration lives in `dispatchers/`.

## Workflow

The system supports a single workflow — `implement` — wired in `config/config.json`. A phase belongs to the workflow when its `workflows` array contains `"implement"`.

| Phase track                                                                                       |
| ------------------------------------------------------------------------------------------------- |
| explore → research → plan (checkpoint) → create-tasks → write-tests → write-code → write-report   |

Each phase entry carries an optional `mode` (e.g. `"read-only"` or `null`), `auto`, `checkpoint`, `parallel_with`, plus an optional `agent` + `agent_count`. The `Config` class derives phase lists from those flags — no separate enum is maintained. The `plan` phase carries `checkpoint: true`, so the resolver pauses there until the operator advances with `/continue`. Workflow ordering lives under the top-level `phases_order` map (one ordered list per workflow), surfaced via `Config.get_phases_order(workflow)`.

## Entry points (`dispatchers/`)

Wired in `hooks/hooks.json`. Each reads Claude's JSON from stdin, short-circuits when the session has no active workflow, then delegates.

| File                       | Hook event           | Role                                                                                                                                                                                                            |
| -------------------------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pre_tool_use.py`          | `PreToolUse`         | Looks up `TOOL_GUARDS[tool_name]` and emits `permissionDecision: "deny"` on block. Logs every block to `violations.md`.                                                                                         |
| `post_tool_use.py`         | `PostToolUse`        | `Recorder.record(...)` then `resolve(...)` to auto-complete phases and auto-start the next.                                                                                                                     |
| `post_tool_use_failure.py` | `PostToolUseFailure` | Bash-only. Records test execution even when the command exits non-zero (TDD-style failing tests still progress phase).                                                                                          |
| `subagent_start.py`        | `SubagentStart`      | Registers `Agent(name, status="in_progress", tool_use_id=agent_id)` so agent counts and completion are tracked.                                                                                                 |
| `subagent_stop.py`         | `SubagentStop`       | Marks the agent `completed` and runs `resolve` so phase-completion logic can fire.                                                                                                                              |
| `task_created.py`          | `TaskCreated`        | Validates task subject against project tasks and records the link.                                                                                                                                              |
| `task_completed.py`        | `TaskCompleted`      | Marks the child subtask done; when all siblings finish, marks the parent and syncs status to `project_manager`.                                                                                                 |
| `stop.py`                  | `Stop`               | Blocks session end until every required phase is complete (see `StopGuard`).                                                                                                                                    |
| `async/post_tool_use.py`   | `PostToolUse`        | Async batcher for slow downstream tasks.                                                                                                                                                                        |
| `async/task_completed.py`  | `TaskCompleted`      | Async. Runs `utils/auto_commit.py` to generate a commit message (headless Claude) and commit task output.                                                                                                       |

The dispatchers for `PreToolUse` and `TaskCreated` write `violations.md` (`lib/violations.py`) on every block for later audit.

## Guardrails (`guardrails/`)

Each guard is a class exposing `validate() → ("allow" | "block", message)`. `guardrails/__init__.py` wires them into `TOOL_GUARDS` (used by `PreToolUse`).

| Guard                 | Invoked on                | What it checks                                                                                                                                                              |
| --------------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PhaseGuard`          | `Skill` (PreToolUse)      | Phase transition follows the workflow ordering. Handles `/continue` as the universal advancer. Skips auto-phases. Allows parallel `explore`+`research`.                     |
| `CommandGuard`        | `Bash` (PreToolUse)       | Command is read-only, or matches the phase whitelist in `constants.COMMANDS_MAP`.                                                                                           |
| `FileWriteGuard`      | `Write` (PreToolUse)      | Phase permits writes; path matches the phase's target (`plan_file`, plan-declared code files, test patterns, report path). Plan writes must include all required sections.  |
| `FileEditGuard`       | `Edit` (PreToolUse)       | Phase permits edits; only `plan` permits Edit. Edits to the plan must preserve required sections.                                                                           |
| `AgentGuard`          | `Agent` (PreToolUse)      | Agent type matches the phase's required agent, under `agent_count`.                                                                                                         |
| `WebFetchGuard`       | `WebFetch` (PreToolUse)   | URL host is in `config.safe_domains`.                                                                                                                                       |
| `TaskCreateToolGuard` | `TaskCreate` (PreToolUse) | Requires `metadata.parent_task_id` + `parent_task_title` matching a known project task.                                                                                     |
| `TaskCreatedGuard`    | `TaskCreated`             | Subject matches a project task title; records child under parent.                                                                                                           |
| `StopGuard`           | `Stop`                    | All non-skipped phases completed.                                                                                                                                           |

## Recorder (`utils/recorder.py`)

Called by `post_tool_use.py` after a guard allows a tool. Dispatches on `tool_name`:

- **Skill** — records a phase transition (except for the no-op skill `continue`).
- **Write** — marks plan / test / code / report files written.
- **Edit** — marks the plan revised when the `plan` phase is active.
- **Bash** — appends the command to `state.commands`.

## Resolver (`utils/resolver.py`)

After the recorder writes raw data, the resolver evaluates phase-completion conditions for the current phase and auto-starts the next phase if needed. A single dispatch table — `_TOOL_RESOLVER_MAP` — keeps per-phase resolution logic table-driven; agent-gated phases (`explore`, `research`) resolve via `_resolve_agent_phase`.

When TDD is disabled (`state.tdd == False`) the resolver hops past the `write-tests` phase. Phases flagged `checkpoint: true` (currently `plan`) pause auto-advance until `/continue` skips the checkpoint.

## State (`models/state.py` + `lib/state_store/`)

`state.json` holds a single JSON object that is the workflow's session state. `StateStore` is the public entry point — it inherits `BaseState` (shared accessors) and exposes the implement-specific slice via `state.implement` (project tasks, plan files to modify).

## Validation flow per Claude Code event

1. `PreToolUse`: `Hook → dispatcher → guard.validate()`. Block returns a `permissionDecision: deny` JSON payload.
2. `PostToolUse`: `Hook → dispatcher → Recorder.record() → resolve()`.
3. `SubagentStop`: `Hook → dispatcher → record_agent_completion()` (which runs the resolver).
4. `Stop`: `Hook → StopGuard.validate()` — completes the session or blocks it with the missing requirements.
