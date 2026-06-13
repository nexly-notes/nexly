---
name: handoff
description: Build full task context — parallel Explore agents map the codebase, then an AskUserQuestion interview fills the gaps — and write project/handoffs/handoff.md (goals, context, implementation plan). Use when the user wants to prepare a handoff, build or capture context before implementation, brief another agent or session on a task, or says "create a handoff", "prep this task", or "build context for X". With no argument, it selects the next ready vertical slice (all dependencies met) from project/specs/vertical-slices.md.
argument-hint: <task-or-feature-to-hand-off>
model: fable
effort: xhigh
---

## Overview

**Goal:** Turn a task (`$ARGUMENTS`) into a complete, self-contained handoff at `project/handoffs/handoff.md` — codebase context gathered by `Explore` agents, goals and decisions extracted from the user by interview, and a concrete implementation plan. The bar: a fresh agent (or session) can implement from the handoff alone, without re-discovering context or re-asking the user.

_If no task is given, select the next ready vertical slice — see Task Selection below._

## Task Selection (no argument)

When `$ARGUMENTS` is empty, the task comes from the vertical slices doc instead of the user:

1. Read `project/specs/vertical-slices.md`; if absent, glob `project/specs/*/vertical-slices.md` and use the current phase's file (per `CLAUDE.md`). If none exists, ask the user what to hand off
2. From the Slice Map, find the slices whose `Depends on` entries are **all met**. A dependency is met only when its demo behavior verifiably exists in the repo — Phase 1 agents must confirm this against code, never assume it from the doc
3. Pick the earliest ready slice in slice order; its Goal / In / Out / Demo sections seed the exploration focus and the implementation plan
4. Confirm the pick as the first interview question, offering the next ready slice as the alternative

## Phase 1 — Explore

Launch 2–3 `Explore` agents **in parallel** — every `Agent` call in a **single message** — each owning a disjoint, task-scoped focus area. Pick areas relevant to the task, for example:

1. **Touched surface** — files, modules, types, and tests the task will touch; how they connect
2. **Conventions and constraints** — patterns the change must follow (state, styling, validation, error handling), project rules, performance budgets
3. **Risk and history** — recent git activity in the area, TODOs, partial implementations, spec/code drift

- Pass the task to each agent so it filters for relevance — a generic codebase survey is a failure
- Agents are read-only investigators; no focus-area overlap
- Synthesis is the orchestrator's job — never delegate it to another agent
- _No-argument runs:_ one agent also verifies the picked slice's dependencies exist in code (their demo behaviors). If a dependency is missing, re-select per Task Selection before interviewing

## Phase 2 — Interview

Grill the user with `AskUserQuestion` — multiple rounds, 1–4 questions per round. Exploration findings are the input: ask what the codebase **cannot** answer, never what it already does. Minimum coverage before writing:

1. **Goals and success criteria** — what does done look like, and for whom?
2. **Scope boundaries** — what is in, out, and deferred
3. **Decisions exploration surfaced** — conflicting patterns, integration points, data shape: offer 2–3 options grounded in findings, strongest first marked `(Recommended)`
4. **Constraints and quality bar** — testing expectations, performance, compatibility, deadlines

Run additional rounds while load-bearing unknowns remain; stop when the remaining questions would not change the plan. Never invent answers on the user's behalf.

## Phase 3 — Write the Handoff

1. Read the template at `.claude/skills/handoff/templates/handoff.md`
2. Fill every section from exploration findings and interview answers; reference code as `path:line`
3. Write to `project/handoffs/handoff.md` (create the directory if missing)

## Rules

- **MUST** run phases in order: Explore → Interview → Write. Skipping the interview is a failure
- **MUST** dispatch all Explore agents in one message (concurrent). Sequential dispatch is a failure
- **MUST** ask questions via `AskUserQuestion`, never as plain text
- **MUST NOT** modify source files — this skill's only write is the handoff file
- Every plan step and decision traces to a finding or an interview answer; the handoff contains no invented facts

## Acceptance Criteria

- [ ] Explore agents dispatched in parallel, each owning a distinct task-scoped focus area
- [ ] Interview covered goals, scope, surfaced decisions, and constraints via `AskUserQuestion`
- [ ] `project/handoffs/handoff.md` written with every template section filled
- [ ] A fresh agent could implement from the handoff alone, without re-asking the user
- [ ] No-argument runs: the chosen slice's dependencies were verified met in code, and the user confirmed the pick

## Completion

Tell the user the handoff is at `project/handoffs/handoff.md`, summarize the goals and the first plan step in one or two sentences, and list any open questions that survived the interview.
