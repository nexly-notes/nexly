---
name: research
description: Launch 2 parallel Research agents to investigate implementation strategies and the latest documentation. Explore agents may run in the same parallel batch.
argument-hint: <topic-or-area-to-research>
model: opus
---

## Overview

### Goal

Gather external context for `$ARGUMENTS` in one parallel pass — combining strategy research with up-to-date documentation lookups (2 `Research` agents) — so the next phase starts from an informed industry baseline instead of guesswork.

### Agent Focus Areas

1. **Research Agent 1 — Implementation strategies**: @"Research (agent)" Research best practices, architectural patterns, and proven approaches for the task at hand. Compare trade-offs. Identify what the industry recommends.

2. **Research Agent 2 — Latest documentation**: @"Research (agent)" Fetch and summarize the latest official documentation for all relevant libraries, frameworks, and APIs involved in this task. Focus on recent versions and any breaking changes.

## Instructions

1. Identify the technologies and patterns relevant to the current task
2. Launch both Research agents **in parallel** — emit both `Agent` tool calls in a **single message** so they execute concurrently. Sequential dispatch is not allowed.
3. Each agent should focus on its assigned area
4. Agents run in foreground — wait for both parallel agents to complete

## Rules

- **MUST** launch both Research agents **in parallel** in a **single message** (concurrent dispatch). Sequential or staggered launches are a failure.
- **MUST** include `Explore` agents in the same parallel batch. Both `Research` and `Explore` agents run concurrently in one message — dispatching only Research agents is a failure.
- **MUST NOT** allow focus-area overlap. Each agent owns its area exclusively (strategy vs. docs).
- **MUST NOT** modify source files. All agents are read-only investigators.
- Synthesis is the orchestrator's job, not an agent's. Do not delegate the final summary to another agent.

## Acceptance Criteria

- [ ] Both Research agents dispatched **in parallel** in one message (concurrent execution).
- [ ] Each agent prompt includes the user-provided topic (`$ARGUMENTS`).
- [ ] Both agents returned without errors; no missing focus areas in the synthesis.
- [ ] Synthesis covers each of the 2 areas distinctly — no duplicated findings across agents.
- [ ] Synthesis ends with a concrete recommendation for the next phase (not a generic "more work needed").
- [ ] No source files were modified during research.

## Completion

Once both agents complete, synthesize findings and advance to the next phase.
