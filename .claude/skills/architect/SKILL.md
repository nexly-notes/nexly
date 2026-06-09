---
name: architect
description: Read project/specs/prd.md, ask only the architecture gaps, and write project/specs/architecture.md
argument-hint: (none — reads project/specs/prd.md)
model: sonnet
---

**Goal:** Translate the PRD into a concrete architecture — capturing purpose, key decisions, tech stack, data flow, and risks in `project/specs/architecture.md`. Optional phase after `/prd`; skip when no architecture doc is needed.

## Inputs

- **Required:** `project/specs/prd.md` — source for problem, constraints, platforms, dependencies, success metrics. If missing, stop and tell the user to run `/prd` first.
- **Optional:** `project/specs/design.md`, `project/specs/research.md` — if they exist, mine them for additional constraints before asking the user.

## Questions

Use the per-section guide below as a minimum coverage map. For each section, first restate what is already implied by the PRD — it is input that grounds your options, not a final answer to copy through. Then open an `AskUserQuestion` for each remaining decision — batch related ones into a single call where it reads naturally, ask them separately when they are not related. Anything the PRD does not unambiguously settle is a decision to surface; decisions whose reversal would force a redesign are also worth confirming with the user, even when the PRD's language points toward an answer.

### §1 Purpose

- Largely derivable from PRD §1 TL;DR + §2 Problem. Confirm the restated purpose with the user. Ask only if scope / out-of-scope needs clarification.

### §2 Key Decisions

- Which significant architectural decisions have already been made? Capture each as an ADR row (decision, why, trade-off accepted).
- If no decisions are decided yet, leave the table seeded with placeholders.

### §3 Tech Stack

- Architecture style (modular monolith / microservices / serverless / event-driven) + one-line rationale.
- For each layer (language/runtime, frontend, backend/API, datastore, async/jobs, auth, infra/hosting): which is decided? If a layer's pick is not yet decided, resolve it now with an `AskUserQuestion` (2–3 grounded options + "Other"). Never invent a pick on the user's behalf, and never defer the decision to PRD §7.
- Module boundaries: one or two import rules that keep the chosen style intact.

### §4 Data Flow

- Walk the happy path for the most critical user story (from PRD §5).
- Confirm where auth checks and validation happen.
- Async flows only if relevant (background jobs, webhooks).

### §5 Risks

- Top 3–5 architectural risks with likelihood, impact, mitigation. Ground in PRD §6 Constraints and the picks made in §3.
- Assumptions whose breakage would force a redesign.

## Recommendations

Help the user decide instead of forcing them to generate from scratch. Anchor every recommendation in PRD content and prior answers — never invent fictional picks.

- **Choice-shaped questions** (style, layer picks, module-boundary rules): supply 2–3 grounded `AskUserQuestion` options. Mark the strongest pick `(Recommended)` and place it first; the user can still pick "Other" to override.
- **Prose-shaped questions** (purpose, data flow): draft a proposed answer from the PRD and ask the user to confirm or revise via "Other". Cite the PRD section the draft is grounded in.
- If a question has no defensible recommendation given the available context, ask it open-ended.

## Instructions

1. Read `project/specs/prd.md`. If missing, stop and tell the user to run `/prd` first.
2. Read the architecture template at `${CLAUDE_PLUGIN_ROOT}/skills/architect/templates/architecture.md`.
3. Walk through §1–§5 sequentially. For each, restate what is implied by the PRD, then open an `AskUserQuestion` for any architectural decision the PRD has not already settled. Do not move to the next section until the current one has enough material to populate.
4. If a tech-stack pick is still undecided when you reach §3, resolve it with an `AskUserQuestion` (2–3 grounded options + "Other") before writing §3. Do not defer the decision to PRD §7.
5. Write the completed document to `project/specs/architecture.md`.

## Rules

- Ask questions via `AskUserQuestion`, never as plain text. Batching related decisions into a single `AskUserQuestion` call is fine when the questions belong together.
- Cover every section (§1–§5) before writing the file.
- NEVER invent tech-stack picks, ADRs, or risks the user did not provide.
- NEVER write outside `project/specs/architecture.md`.
- NEVER invent a tech pick on the user's behalf. If a pick is undecided, resolve it via `AskUserQuestion` before writing §3 — do not defer it to PRD §7.
- Every recommendation must trace to the PRD or a prior answer; cite the source in the question text.
