# {Project Name} - {Release / Scope} Roadmap

_Derived from `{source spec paths}`. Scope is `{timebox or release boundary}` only. Each milestone carries a **Guardrail**: the single binding constraint that, if violated, means the milestone is not done and work is off track._

## Roadmap Metadata

**Project:** `{Project name}`
**Roadmap Scope:** `{MVP / Phase 2 / Beta / Launch / Internal release}`
**Source Specs:** `{project/specs/...}`
**Target Window:** `{start date or sprint} -> {end date or release target}`
**Last Updated:** `{YYYY-MM-DD}`

## Roadmap Principles (Global Guardrails)

1. **{Principle name}** - {Binding project-wide constraint. State what must happen, and what is explicitly excluded.}
2. **{Principle name}** - {Consistency rule that prevents drift across milestones.}
3. **{Principle name}** - {Terminology, data model, design, security, privacy, or operational constraint.}
4. **{Principle name}** - {Quality gate that applies before any milestone can be called complete.}

## M0 - {Foundation / Setup Milestone}

- **Goal:** {One sentence describing what this milestone unlocks.}
- **Build:**
  1. {Concrete build item with enough detail to implement or verify.}
  2. {Concrete build item.}
  3. {Concrete build item.}
- **Guardrail:** {Hard exit criterion for this milestone. If this is false, do not advance.}

## M1 - {Milestone Name}

- **Goal:** {One sentence describing the user or system outcome.}
- **Build:**
  1. {Concrete build item.}
  2. {Concrete build item.}
  3. {Concrete build item.}
- **Guardrail:** {Hard exit criterion for this milestone. Include measurable thresholds where possible.}

## M2 - {Milestone Name}

- **Goal:** {One sentence describing the user or system outcome.}
- **Build:**
  1. {Concrete build item.}
  2. {Concrete build item.}
  3. {Concrete build item.}
- **Guardrail:** {Hard exit criterion for this milestone. Include dependencies, quality gates, or performance budgets if relevant.}

## M3 - {Milestone Name}

- **Goal:** {One sentence describing the user or system outcome.}
- **Build:**
  1. {Concrete build item.}
  2. {Concrete build item.}
  3. {Concrete build item.}
- **Guardrail:** {Hard exit criterion for this milestone.}

## Release Gate (Definition of Done)

_The release is validated only when these green-light thresholds hold:_

1. {Measurable adoption, usage, quality, revenue, operational, or learning threshold.}
2. {Measurable threshold.}
3. {Measurable threshold.}
4. {Measurable threshold.}
5. {Measurable threshold.}

**Important!** Build order is dependency-driven (`M0 -> M1 -> M2 -> ...`). A milestone's Guardrail is a hard exit criterion, not a guideline. Do not advance past a milestone whose guardrail is unmet.

<!-- ## Template Rules

- Keep milestones sequential (`M0`, `M1`, `M2`, ...). Do not skip numbers.
- Each milestone must include exactly one `Goal`, one ordered `Build` list, and one `Guardrail`.
- Keep build items concrete enough to verify. Avoid vague verbs like "improve" unless paired with a measurable target.
- Put exclusions in `Roadmap Principles`, not hidden inside milestone text.
- Release gates must be measurable. If a gate cannot be measured, rewrite it or move it to assumptions. -->
