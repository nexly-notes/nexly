---
name: implement
description: Implement a story from the project backlog
allowed-tools: Bash, Read, Glob, Grep, Write
argument-hint: <story-id> [--tdd] [--skip-explore] [--skip-research] [--reset] [--takeover]
model: haiku
hooks:
  Stop:
    - hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/build/code_review.py tests"
          async: true

        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/build/code_review.py performance"
          async: true

        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/build/code_review.py security"
          async: true

        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/build/code_review.py requirements"
          async: true
---

!`python3 '${CLAUDE_PLUGIN_ROOT}/scripts/utils/initializer.py' implement ${CLAUDE_SESSION_ID} $ARGUMENTS`

## Overview

### Goal

Implement the specified backlog story end-to-end through the phased workflow — from exploration through code review, PR creation, and CI — producing shipped, verified code.

### Story Context

!`python3 '${CLAUDE_PLUGIN_ROOT}/../.github/scripts/projects/cli.py' view $0`

## Instructions

- Follow the phased workflow strictly. The guardrails enforce phase ordering.
- **Phases are skills.** Invoke `/explore`, `/research`, `/plan`, etc. to enter each phase.
- **Auto-phases start automatically** — do NOT invoke `/create-tasks`, `/write-tests`, or `/write-code`.
- All agents must be run in the **foreground** (not background).
- Agent counts must match the limits or the guardrail will block you.
- Only read and write files relevant to the current phase.
- `story_id` is **required** for implement workflow.
- If another session is already active for the same story, the initializer will fail. Use `--reset` to start fresh or `--takeover` to continue where the old session left off.
- Ask questions if unsure. Use `AskUserQuestion`.

## Phases

Trigger `/explore` and `/research` in parallel. The rest run sequentially.

1. `/explore` — survey the codebase.
2. `/research` — gather external knowledge and best practices.
3. `/plan` — produce the implementation plan.
4. `/failing-tests` — write failing tests first.
5. `/implement` — implement against the plan.
6. `/simplify` — QA the implementation.
7. `/review` — score and revise the code until approved.

## Rules

- Follow phase order strictly. Guardrails enforce it.
- Do not skip phases unless in the `skip` list.
- Do not invoke auto-phases as skills.
- Do not invoke agents beyond their max count.
- Do not stop until all phases are completed — the stop hook will block you.
- Validate work through tests, not assumptions.

## References

- **Plan template**: `${CLAUDE_PLUGIN_ROOT}/templates/implement-plan.md`
- **Plan**: `.claude/plans/latest-plan.md`
- **Report**: `.claude/reports/report.md`
