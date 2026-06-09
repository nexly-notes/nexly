---
name: design
description: Phase 4 of the specs pipeline. Launches a design agent to produce project/specs/design.md (UX/UI specification). Use when the user asks to create UX specs, design specs, or invokes /design after /decision has completed.
allowed-tools: Bash, Read, Glob, Grep, Write, Agent, AskUserQuestion
argument-hint: <feature-description>
model: haiku
---

**Goal**: Produce `project/specs/design.md` — a lean UX/UI design specification — by delegating to a design subagent that fills in the design template.

## Context

Translates product intent and prior technical decisions into a concrete UX/UI specification — user journeys, screen states, wireframes, accessibility, and open assumptions — so that backlog and implementation work has a single, traceable design source.

| Depends on | Path                              |
| :--------- | :-------------------------------- |
| Vision     | `project/specs/product-vision.md` |
| Decisions  | `project/specs/decisions.md`      |

## Instructions

1. **Verify dependencies exist**. If `product-vision.md` or `decisions.md` is missing, stop and report the missing dependency to the user — do not proceed.
2. **Read the design template** at `${CLAUDE_SKILL_DIR}/templates/design.md` to understand the required structure.
3. **Read the dependency specs** to ground design choices in product intent and prior decisions.
4. **Launch one design subagent** (foreground only) with:
   - The feature description (`$ARGUMENTS`)
   - Paths to the template and dependency specs
   - Instruction to fill in every section of the template — no placeholders left in the final output
5. **Validate the output** against the template structure (all 13 top-level sections present, no `<...>` placeholders in critical fields).
6. **Write** the validated content to `project/specs/design.md`.
7. **Report** to the user: file location, sections covered, any open assumptions or risks the agent flagged.

## Rules

- NEVER create `design.md` if `product-vision.md` or `decisions.md` is missing — guardrails enforce phase order.
- NEVER write actual code (HTML, CSS, JSX, etc.) — this phase produces specification only; wireframes go in §5.2 as links or ASCII.
- NEVER fabricate user research data; mark unknowns as assumptions in §12.1.
- DO NOT create files outside `project/specs/`.
- Do not invoke more than one design agent for this phase.
- Do not overwrite an existing `design.md` without explicit user approval (use `AskUserQuestion`).
- Use `AskUserQuestion` for any clarification — never plain-text questions.

## Acceptance Criteria

- `project/specs/design.md` exists and follows `${CLAUDE_SKILL_DIR}/templates/design.md` structure.
- All 13 top-level sections are present and populated (no leftover `<...>` placeholders in headers, scope, or critical decision tables).
- Design choices traceably reference prior `decisions.md` entries where applicable.
- Accessibility (§8) and Screen States (§5.3) are filled — these are the most common skip points.
- User receives a report with file path, summary of journeys covered, and flagged risks.

## References

- **Design template**: `${CLAUDE_SKILL_DIR}/templates/design.md`
- **Vision input**: `project/specs/product-vision.md`
- **Decisions input**: `project/specs/decisions.md`
- **Pipeline overview**: `.claude/skills/specs/SKILL.md`
