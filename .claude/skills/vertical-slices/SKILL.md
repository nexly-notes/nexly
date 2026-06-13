---
name: vertical-slices
description: Decompose a phase PRD into ordered vertical slices - thin, end-to-end, independently demoable increments - and write vertical-slices.md into the same project/specs/<phase>/ directory as the PRD. Use this whenever the user wants to slice a PRD, create vertical slices, break a spec or requirements into buildable increments, plan demoable milestones, or decide what to build first from a PRD - even if they never say "vertical slice".
allowed-tools: Read, Glob, Grep, Write, AskUserQuestion
argument-hint: <prd-path-or-phase> (default: current phase)
---

## Overview

This skill turns a phase PRD into the build plan that sits between specs and a backlog: an ordered set of vertical slices.

**Deliverable:** `project/specs/<phase>/vertical-slices.md` - written to the same directory as the source PRD, in the format defined by `.claude/skills/vertical-slices/template/vertical-slices.md`.

A vertical slice is a thin increment that cuts through every layer the product needs (UI, application logic, data/services) to deliver one demoable behavior. The reason for slicing this way is integration risk: horizontal plans ("build the schema", "build all the components") hide integration failures until the end, while vertical slices force the full stack to work from the first slice.

The slices doc is not a backlog. It defines what each increment proves and in what order - no story IDs, tasks, estimates, or assignees.

**Important!** The doc exists to speed up development, not to re-spec the product. It earns its keep only if a developer can read a slice in under a minute and start building; anything that slows that down is bloat.

## Inputs

1. **Required - the source PRD**, resolved in this order:
   1. `$ARGUMENTS` is a path to a PRD file - use it; the phase is its parent directory name.
   2. `$ARGUMENTS` names a phase (e.g. `mvp`, `phase-2`) - use `project/specs/<phase>/prd.md`.
   3. No arguments - read the current phase from `CLAUDE.md` (e.g. `Current Phase: MVP`), lowercase it, and use `project/specs/<phase>/prd.md`.
   4. Still unresolved - if exactly one `project/specs/*/prd.md` exists (ignore `deprecated/`), use it; otherwise ask via `AskUserQuestion`.
2. **Optional:** `tech-specs.md`, `design.md`, `architecture.md` in the same directory - mine them for layers, dependencies, and constraints. Never invent content from them.

## Instructions

1. Resolve and read the source PRD. If it does not exist, stop and tell the user (suggest `/prd`); do not invent requirements.
2. Extract from the PRD: requirement IDs and priorities (FR/NFR tables, or requirement headings if the PRD has no IDs), goals, non-goals and out-of-scope items, success criteria, and dependencies.
3. Read the optional specs in the same directory if they exist.
4. Read the template at `.claude/skills/vertical-slices/template/vertical-slices.md`.
5. Design the slices using the principles below.
6. Self-check the draft adversarially before writing: hunt for horizontal slices, uncovered requirements, forward dependencies, undemoable slices, and invented scope. Fix everything you find.
7. Write the completed doc to `project/specs/<phase>/vertical-slices.md`.
8. Report: the file path, source specs read, slice count, requirement coverage, and any assumptions or open questions.

## Slicing Principles

- **Lean above all:** keep every field to one line; point to requirement IDs instead of restating PRD acceptance criteria - the PRD stays the single source of detail. A slice a developer can finish and demo in a few days beats a thorough one that takes weeks; split anything bigger.
- **Walking skeleton first:** slice 1 is the thinnest path through all layers that a user can see working (e.g. open the app, perform the core action, the result persists). Everything else builds on it.
- **Demoable, every slice:** each slice ends with a short demo script (1-3 steps) a human can actually run. If you cannot write one, it is not a slice - merge it into the slice that makes it visible.
- **Thin by acceptance criteria, not by layer:** when a requirement is too big for one slice, split it by trimming acceptance criteria (e.g. "search by title only; sort deferred"), never by shipping one layer alone.
- **Full coverage, explicit partials:** every in-scope requirement maps to at least one slice. Partial coverage must state what is deferred and to which slice.
- **Backward-only dependencies:** each slice depends only on earlier slices. Order is dependency-driven; within that, Must before Should before Nice.
- **Cross-cutting NFRs ride along:** attach each NFR to the slice where it first becomes testable; list purely global ones once in Coverage.
- **Respect non-goals:** out-of-scope items never appear inside a slice; restate them once in Coverage as exclusions so readers know they were not forgotten.
- **Right-size the set:** typically 4-10 slices. More than that usually means horizontal splitting crept in; fewer usually means slices too big to demo.

## Rules

- **Important!** Write only `project/specs/<phase>/vertical-slices.md`. No backlog files, no code, no edits to the PRD or other specs.
- Never invent scope: every slice item traces to a requirement ID, or to quoted PRD text when the PRD has no IDs.
- Never duplicate the PRD: no copied acceptance tables, persona text, or metric definitions. Reference, don't restate.
- A slice with no user-visible behavior is not a slice - fold infrastructure into the first slice that needs it.
- If specs conflict or the source PRD cannot be resolved, ask via `AskUserQuestion` instead of guessing.

## Acceptance Criteria

Task is done only when every box below is checked:

- [ ] `project/specs/<phase>/vertical-slices.md` is written, in the same directory as the source PRD.
- [ ] The doc follows the template with no placeholders left.
- [ ] Every in-scope requirement appears in at least one slice; partial coverage states what is deferred and where.
- [ ] Every slice has a goal, requirements, end-to-end path, demo script, and dependencies.
- [ ] Dependencies point only backward; slice 1 is a walking skeleton.
- [ ] PRD non-goals appear only as exclusions, never inside a slice.
- [ ] No backlog fields: story IDs, tasks, estimates, assignees, issue numbers.
- [ ] The doc is lean: one line per field, no PRD content restated, each slice readable in under a minute.

## References

- `.claude/skills/vertical-slices/template/vertical-slices.md` - canonical output structure
- `project/specs/<phase>/prd.md` - source PRD
- `project/roadmap.md` and `/backlog` - downstream consumers of the slices
