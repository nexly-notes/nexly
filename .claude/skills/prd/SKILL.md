---
name: prd
description: Ask discovery questions covering every PRD section and write project/specs/prd.md
argument-hint: <project-description>
model: sonnet
---

Ask the user enough discovery questions to populate every section of the PRD template, then write `project/specs/prd.md`. Keep answers lean and do not speculate beyond what the user provides.

## Questions

Use the per-section guide below as a minimum coverage map — split a prompt into follow-ups when an answer is thin, or combine prompts when context is already rich. Ask **one at a time** via `AskUserQuestion`.

### §1 TL;DR

- In three sentences: what are you building, who is it for, and why does it matter _now_?

### §2 Problem

- Which specific user segment has this problem, and how do they describe the pain today? (avoid "all users"; include evidence)
- What changed (market, platform, capability) that makes this the right moment?

### §3 Goals & non-goals

- What outcomes are you trying to achieve, and what is explicitly out of scope?

### §4 Success metrics

- What is the one primary metric that proves this worked, and what guardrail metrics must not regress?

### §5 User stories

- What are the 2–5 core scenarios? For each: who, how they handle it today, and what changes with this product.

### §6 Requirements

- Grouped by capability: what is Must (P0), Should (P1), and Nice (P2)?
- What are the hard non-negotiable constraints? (performance/reliability, security & privacy, platforms, dependencies)

### §7 Open questions

- What unknowns or pending decisions need to be resolved by `/specs-research` and `/decision`? (tech-stack picks live in the architecture doc, not here)

## Recommendations

Help the user decide instead of forcing them to generate from scratch. Anchor every recommendation in the project description (`$1`) and prior answers — never invent fictional users, metrics, or stack picks.

- **Choice-shaped questions** (success metrics, constraints, prioritization): supply 2–3 grounded `AskUserQuestion` options. Mark the strongest pick `(Recommended)` and place it first; the user can still pick "Other" to override.
- **Prose-shaped questions** (TL;DR, problem statement, goals, user stories): draft a proposed answer directly in the question text, then ask the user to confirm or revise via "Other". Cite which part of `$1` the draft is grounded in.
- If a question has no defensible recommendation given the available context, ask it open-ended and say so — do not fabricate options.

## Instructions

1. Walk through every PRD section sequentially, asking questions via `AskUserQuestion` and following the Recommendations guidance above. Do not move to the next section until the current one has enough material to populate.
2. After collecting all answers, read the PRD template at `${CLAUDE_PLUGIN_ROOT}/skills/prd/templates/prd.md`.
3. Populate the template with the user's answers — every section must be filled. Do not invent content the user did not provide; leave unknowns in §7 Open questions.
4. Write the completed document to `project/specs/prd.md`.

## Rules

- Ask questions **one at a time** via `AskUserQuestion` — never batch into a single call, never use plain-text questions.
- Cover every PRD section (§1–§7) before writing the file. Do not skip a section because it feels obvious — confirm with the user.
- NEVER invent users, metrics, stack picks, or constraints the user did not provide — leave unknowns in §8 Open questions.
- NEVER fabricate `AskUserQuestion` options when `$1` and prior answers can't support them — ask open-ended instead.
- NEVER write outside `project/specs/prd.md`.
- Every recommendation must trace to `$1` or a prior answer; cite the source in the question text.
