---
name: plan
description: Create implementation plan from user instructions by delegating to planner agent
allowed-tools: Bash, Read, Glob, Grep, Write, Agent, EnterPlanMode, ExitPlanMode, AskUserQuestion
argument-hint: <user-instructions>
model: opus
hooks:
  Stop:
    - matcher: Write|Edit
      hooks:
        - type: command
          command: "python3 ${CLAUDE_SKILL_DIR}/hooks/extract_file_paths.py"
---

## Overview

**Goal:** Create an implementation plan using a customized plan mode workflow.

## Instructions

1. **Enter plan mode** — If the session is not already in plan mode (no plan-mode system message is present), call `EnterPlanMode` first. If already in it, continue.
2. **Add a documentation research agent** — When the @"Explore (agent)" agent(s) are launched to survey the codebase, launch one @"Researcher (agent)" agent in the **same parallel batch** (single message, foreground) to fetch the latest documentation for every library, framework, or API the work touches.
3. **Clarify only when it matters** — Use `AskUserQuestion` only if an important decision must be made (scope, approach, trade-off, validation strategy). If no such decision exists, skip clarification entirely — do not ask filler questions.
4. **Conform to the template** — The written plan must match `${CLAUDE_SKILL_DIR}/template/plan.md` exactly: every section, in order, two header levels max. `Files to Touch` must be one bare repository-relative path per bullet — no actions, annotations, tables, comments, or blank lines (the Stop hook parses this section verbatim for the downstream scope guard).

## Rules

- **Important!** The `Researcher` agent runs **alongside** `Explore` in one parallel batch — never as a separate later step.
- Do not run agents in the background, and do not use agent types other than `Explore` and `Researcher`.
- Write the plan only under `.claude/plans/`; nothing else is written in this phase.
- Do not ask clarifying questions when no real decision is at stake.

## References

- **Plan template:** `${CLAUDE_SKILL_DIR}/template/plan.md`
- **Plan output dir:** `.claude/plans/`
