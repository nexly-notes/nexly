---
name: roadmap
description: Generate project/roadmap.md from project specs using the roadmap template.
allowed-tools: Bash, Read, Glob, Grep, Write, AskUserQuestion
argument-hint: <roadmap-scope-or-focus>
model: opus
---

## Overview

This skill turns upstream product, technical, and design specs into a milestone-based roadmap.

**Deliverable:** `project/roadmap.md` - authored by the main agent in the format defined by `.claude/skills/roadmap/template/roadmap.md`.

The roadmap is not a backlog. It should define build order, milestone goals, concrete build items, hard guardrails, and release gates. It should not break work into task IDs, story IDs, assignees, or issue-tracker fields.

## Inputs

Use the most relevant specs for the requested roadmap scope.

Default input locations:

- `project/specs/prd.md`
- `project/specs/tech-specs.md`
- `project/specs/design.md`
- `project/specs/**/prd*.md`
- `project/specs/**/tech-specs*.md`
- `project/specs/**/design*.md`

## Instructions

1. **Resolve scope.** Use `$ARGUMENTS` to identify the roadmap scope. If no scope is provided, infer the current release scope from available specs and state that scope in the roadmap metadata.
2. **Verify source specs exist.** Find the relevant PRD, technical spec or architecture decisions, and design spec when available. If no product spec exists, stop and ask the user for the missing source instead of inventing roadmap content.
3. **Read the template** at `.claude/skills/roadmap/template/roadmap.md`. Preserve its structure unless the source specs clearly require more milestones.
4. **Read the selected source specs** and extract:
   - Release scope and explicit exclusions.
   - Dependency order.
   - User-facing capabilities.
   - Infrastructure, data, auth, security, privacy, and operational prerequisites.
   - Performance, quality, CI, accessibility, and release success metrics.
5. **Draft the roadmap** by filling every template section:
   - Roadmap metadata with source paths and target window if known.
   - Global guardrails that prevent scope, terminology, privacy, design, or quality drift.
   - Sequential milestones (`M0`, `M1`, `M2`, ...), ordered by dependency.
   - Each milestone with one `Goal`, one ordered `Build` list, and one hard `Guardrail`.
   - Release gates with measurable thresholds from the specs.
6. **Validate the draft** before writing:
   - No template placeholders remain.
   - Every milestone has `Goal`, `Build`, and `Guardrail`.
   - Milestones are sequential with no skipped numbers.
   - Each build item is concrete and traceable to a source spec.
   - Release gates are measurable, or unresolved metrics are explicitly called out as assumptions.
7. **Write** the completed roadmap to `project/roadmap.md`.
8. **Report** the file path, selected source specs, milestone count, and any assumptions or unresolved questions.

## Rules

- **IMPORTANT:** Write only `project/roadmap.md`. Do not create backlog files, issue files, JSON files, or implementation code.
- **IMPORTANT:** Use `.claude/skills/roadmap/template/roadmap.md` as the canonical output structure.
- **IMPORTANT:** Do not invent product scope, metrics, technical constraints, or release dates. Use source specs or mark the item as an assumption.
- Preserve explicit non-goals and out-of-scope items as roadmap guardrails.
- Keep build order dependency-driven, not team-structure-driven.
- Use measurable guardrails wherever possible. If a guardrail cannot be measured, make it binary and verifiable.
- Do not include task IDs, story IDs, owners, assignees, estimates, or issue numbers. Those belong in a backlog, not the roadmap.
- If source specs conflict, stop and ask via `AskUserQuestion` rather than choosing silently.

## Acceptance Criteria

Task is done only when every box below is checked:

- [ ] `project/roadmap.md` is written at exactly that path.
- [ ] The roadmap follows `.claude/skills/roadmap/template/roadmap.md`.
- [ ] The metadata lists the selected source specs and roadmap scope.
- [ ] All milestones are sequential and dependency-ordered.
- [ ] Every milestone includes one `Goal`, one ordered `Build` list, and one `Guardrail`.
- [ ] Every guardrail is a hard exit criterion, not a suggestion.
- [ ] Release gates are measurable, or unresolved metrics are explicitly listed as assumptions.
- [ ] No backlog-only fields appear: story IDs, task IDs, assignees, estimates, issue numbers, or generated JSON.
- [ ] No placeholders from the template remain.

## References

- `.claude/skills/roadmap/template/roadmap.md` - canonical roadmap template
- `project/roadmap.md` - roadmap deliverable
- `project/specs/` - source specs
