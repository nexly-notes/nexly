---
name: implement
description: Write code against the plan (TDD-aware). Runs after /failing-tests when TDD is on, or right after /plan otherwise.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit
argument-hint: <optional-implementation-notes>
model: haiku
---

## Overview

### Goal

Write the code that satisfies the approved plan. In TDD mode, make the previously written failing tests pass without modifying them. In non-TDD mode, write straight from the plan and validate against the plan's acceptance criteria.

## Instructions

1. **Locate targets** — Use `Glob`/`Grep` to find the modules referenced by the plan. Prefer editing existing files (`Edit`) over creating new ones (`Write`).
2. **Implement** — Write the smallest code that fulfills the plan. Keep functions ≤ 15 lines, modular, semantic. Follow the docstring rules in `CLAUDE.md`.
3. **Validate** —
   - **TDD mode**: run the test command (e.g. `pytest <test_paths>`) until every failing test passes. Tests must not be modified.
   - **Non-TDD mode**: run the validator the plan specifies (script, command, or smoke run).
4. **Report** — Summarize files touched, command(s) run, and pass/fail outcome.

## Rules

- **MUST** keep changes within the plan's scope — no opportunistic refactors, no out-of-plan files.
- **MUST** follow project coding style (≤15 lines/function, semantic naming, docstring rules in `CLAUDE.md`).
- **MUST NOT** modify test files in TDD mode.
- **MUST NOT** invoke other phase skills (`/review`, `/simplify`, `/failing-tests`) — the orchestrator owns transitions.
- **MUST NOT** spawn agents — main agent writes the code directly.
- **MUST NOT** mark the phase complete while any required test or validator still fails.

## Acceptance Criteria

- All plan items have corresponding code changes on disk.
- TDD mode: every failing test passes; no test file was modified.
- Non-TDD mode: the plan's validator was run and reported success.
- Report includes: files touched, command(s) run, and pass/fail outcome.
