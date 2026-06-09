---
name: plan
description: Create implementation plan from user instructions by delegating to planner agent
allowed-tools: Task, Read, Glob, Grep, AskUserQuestion, TodoWrite, Agent, Write, WebFetch, WebSearch
argument-hint: <planning-instructions>
model: opus
hooks:
  PostToolUse:
    - matcher: Write|Edit
      hooks:
        - type: command
          command: "python3 $CLAUDE_PROJECT_DIR/.claude/hooks/build/plan_review.py"
---

## Overview

Create an actionable implementation plan by clarifying key decisions with the user and then delegating the design to the `Plan` agent — enforced by the plan guardrail.

## Instructions

If no instructions are provided, ask the user what to plan.

1. **Clarify** — Use `AskUserQuestion` to capture the user's key decisions before designing the plan. Cover whatever is relevant to this task (e.g. scope, approach, constraints, trade-offs, validation strategy). Ask 1–4 focused questions per round; run additional rounds if earlier answers reveal new decisions to resolve.
2. **Plan** — Invoke the `Plan` agent to design the plan, passing the user's answers into its prompt. It returns the design; it does not write to disk.
3. **Write** — The main agent writes the design to `.claude/plans/<plan-name>.md`.

## Rules

- **MUST** follow the phase sequence. This is not optional.
- **MUST** ask the user key-decision questions via `AskUserQuestion` before invoking the `Plan` agent — the answers shape the plan and are passed into the `Plan` agent's prompt
- **MUST** delegate plan **design** to the `Plan` agent — the main agent does not design the plan itself
- **MUST** have the **main agent** write the plan file — the `Plan` agent does not write to disk
- **MUST** save the plan to `.claude/plans/` — writes elsewhere are blocked
- **DO NOT** use agent types other than `Plan`
- **DO NOT** skip the Clarify phase — it always runs
- **DO NOT** invent answers on the user's behalf — if a decision is unclear, ask

## Acceptance Criteria

- Key decisions captured via `AskUserQuestion` and passed into the `Plan` agent's prompt
- Plan designed by the `Plan` agent and written by the main agent to `.claude/plans/`
- Plan saved with all required template sections
