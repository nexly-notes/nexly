---
name: explore
description: Launch 3 parallel Explore agents to analyze the codebase (structure, git/deps, technical health). Research agents may run in the same parallel batch.
argument-hint: <topic-or-area-to-explore>
model: opus
---

## Overview

### Goal

Gather full internal context for `$ARGUMENTS` in one parallel pass — using 3 `Explore` agents to analyze the codebase — so the next phase starts from an informed baseline instead of guesswork.

### Agent Focus Areas

1. **Explore Agent 1 — Project structure & configuration**: @"Explore (agent)" Analyze the project layout, build config, entry points, and key directories. Identify the critical files and their relationships.

2. **Explore Agent 2 — Git activity & dependencies**: @"Explore (agent)" Analyze recent git history, dependency graph, and package versions. Identify active areas and potential risks.

3. **Explore Agent 3 — Implementation state & technical health**: @"Explore (agent)" Analyze code quality, test coverage, TODOs, and technical debt. Identify areas needing attention.

## Instructions

1. Identify the technologies and patterns relevant to the current task
2. Launch all 3 Explore agents **in parallel** — emit every `Agent` tool call in a **single message** so they execute concurrently. Sequential dispatch is not allowed.
3. Each agent should focus on its assigned area
4. Agents run in foreground — wait for all parallel agents to complete

## Rules

- **MUST** launch all 3 Explore agents **in parallel** in a **single message** (concurrent dispatch). Sequential or staggered launches are a failure.
- **MUST** include `Research` agents in the same parallel batch. Both `Explore` and `Research` agents run concurrently in one message — dispatching only Explore agents is a failure.
- **MUST NOT** allow focus-area overlap. Each agent owns its area exclusively (e.g., only Agent 2 reads git history; only Agent 3 evaluates code quality).
- **MUST NOT** modify source files. All agents are read-only investigators.
- Synthesis is the orchestrator's job, not an agent's. Do not delegate the final summary to another agent.

## Acceptance Criteria

- [ ] All 3 Explore agents dispatched **in parallel** in one message (concurrent execution).
- [ ] All 3 agents returned without errors; no missing focus areas in the synthesis.
- [ ] Synthesis covers each of the 3 areas distinctly — no duplicated findings across agents.
- [ ] Synthesis ends with a concrete recommendation for the next phase (not a generic "more work needed").
- [ ] No source files were modified during exploration.

## Completion

Once all 3 agents complete, synthesize findings and advance to the next phase.
