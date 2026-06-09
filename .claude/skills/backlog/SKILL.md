---
name: backlog
description: Two-phase backlog builder — the ProductOwner designs a lean product backlog (phase 1), then grooms it in place into the final groomed backlog (phase 2); the main agent writes project/backlog.json, gates each phase on user approval, validates the backlog schema, and optionally converts to GitHub.
argument-hint: <backlog-focus>
model: opus
effort: xhigh
---

## Overview

This skill takes a project from a **lean draft** to a **groomed backlog** in **two phases**, with a user-approval gate after each, then offers to push it to GitHub. The single deliverable is `project/backlog.json`.

1. **Phase 1 — lean design.** The **ProductOwner** designs a lean backlog (stories with `title` / `description` / `priority` only). The main agent writes it, **presents it to the user**, and asks for approval to continue. A lean backlog already validates and can `convert`.
2. **Phase 2 — grooming (optional).** On approval, the **ProductOwner** grooms every story (goal, notes, tasks, acceptance criteria, labels, size, points, and `blocked_by` dependencies). The main agent enriches `project/backlog.json` **in place**, validates, **presents the final backlog**, and asks whether to `convert`.

- **Deliverable:** `project/backlog.json` — one artifact. Authored **directly** by the main agent against `.claude/skills/backlog/sample_structure.json`. There is no markdown step and no separate sprint file.
- **Identity:** the **`title`** is the stable re-link key (unique across stories); the **GitHub issue number** (minted by `convert`) is the identity, and `blocked_by` references stories by that number.
- **Designer:** the **ProductOwner agent** owns content in both phases — story selection and priorities (phase 1), the buildable grooming detail (phase 2). See `.claude/agents/product-owner.md`.
- **Finalizer:** the **main agent** renders each design into JSON, runs the gates, validates, and (on approval) converts.

**Inputs follow a precedence:** the **user's instruction** comes first — a `<backlog-focus>` argument or any direction in the request governs scope, focus, and which sources to read. **Only when no instruction is given** does the skill fall back to the phase specs (`prd.md`, `design.md`, `tech-specs.md`).

_Content-level concerns go back to the ProductOwner or to the user via `AskUserQuestion` — never resolved unilaterally._

## Inputs

### User Instructions

```
$ARGUMENTS
```

## Schema

The backlog is a flat list of **stories**; each story maps 1:1 to a GitHub issue. Grooming is **optional** — a lean story (just the three required fields) validates and converts. Author against `sample_structure.json`.

**Top-level:** `project` (str), `description` (str), `dates.{start,end}` (YYYY-MM-DD), `stories` (list).

**Story — required fields:**

- `title` — short imperative title (non-empty); the **re-link key**, so it must be **unique across stories**
- `description` — one or two sentences of context (non-empty)
- `priority` — `P0` / `P1` / `P2`

**Story — optional (groomed) fields**, validated only when present:

- `status` — `Backlog` / `In Progress` / `Done` (default `Backlog`)
- `goal` — one line on why this story matters (non-empty)
- `notes` — extra body prose; **may be `""`**
- `tasks` — list of concrete steps, **≥1 entry**
- `acceptance_criteria` — list of objective, testable criteria, **≥1 entry**
- `labels` — list of labels, **must include ≥1 work-type label** from `feature` / `tech` / `bug` / `spike` / `chore` / `docs` / `review`; domain labels (`backend`, `frontend`, …) are allowed extras but don't satisfy the rule
- `blocked_by` — list of **issue numbers** this story depends on; each must resolve to another story's `issue_number` in this file, and a story may not list its own number
- `size` — `XS` / `S` / `M` / `L` / `XL`
- `points` — number (story points)
- `issue_number` — int, default `0`; populated by `convert` and written back, so leave it `0` for new stories

**Important!** Enum values are case-sensitive. The **work-type label is the sole carrier of issue type** — groomed stories must carry one. `blocked_by` references issue **numbers**, which only exist after a `convert` — so dependency grooming follows the two-pass flow (see **Validation**).

## Ordering

Structure the backlog as a **foundation-first build sequence**: each group unblocks the ones after it, so the backlog reads top-to-bottom in the order the work is built. **Build order is carried by array position** — the order of `stories` in the file _is_ the build order. Within a group, order by `priority`.

1. **Project setup** — repo, framework, dependencies.
2. **App structure** — folders, components, routes / navigation, architecture pattern.
3. **Database & models** — schema, entities, relationships.
4. **API contracts** — endpoint / function signatures and shared types.
5. **Backend skeleton** — stubbed services and handlers.
6. **Frontend screens (mock data)** — UI shells wired to fixtures.
7. **Feature implementation** — backend + frontend, one feature at a time, together.
8. **Frontend ↔ backend integration** — swap mock data for the real services.
9. **Auth & permissions** — authentication and access control.
10. **Test & debug.**
11. **Polish & optimize.**
12. **Deploy & release.**

- Not every group yields a story — skip groups the specs do not justify; never invent scope to fill one. A group may also map to several stories.
- Map each story to the **earliest** group it genuinely belongs to.
- _A real hard dependency may override the default order (e.g. when a security model like per-user RLS must exist before any feature touches data). State the reason in the story `description`, and surface non-obvious reorderings in Open Questions — do not silently reshuffle._

## Validation

The validator enforces the **lenient** schema — the required fields plus the groomed fields _when present_. It runs on a lean draft or a groomed backlog:

```bash
python3 .github/scripts/projects/cli.py validate project/backlog.json
```

- Exit `0` + `Backlog validation passed` → valid.
- Non-zero exit + error lines → invalid. Each line names the offending `stories[i].field` and why.

_The validator checks the required `title` / `description` / `priority`, **title uniqueness**, the groomed fields when present (enum casing, the work-type-label rule, ≥1 task / criterion), and the `blocked_by` closure — every entry is an issue number that resolves to another story's `issue_number` in-file, with no self-block._

**Important! The two-pass dependency flow.** Issue numbers don't exist until `convert` mints them, and `blocked_by` is a list of issue numbers — so dependencies are authored **after** a first convert:

1. `convert` the backlog → issue numbers are minted and written back.
2. Groom `blocked_by` with the now-known issue numbers.
3. `convert` again (idempotent) → the GitHub "blocked by" edges are set.

_A backlog with no `blocked_by` (e.g. the lean draft) is unaffected by step 1._

## Readable view

`project/backlog.json` is the source of truth, but a markdown view is easier to scan. After the backlog validates, regenerate `project/backlog.md` beside it:

```bash
python3 .claude/skills/backlog/scripts/backlog-to-md.py
```

_Generated, never hand-edited — re-run after any backlog change (including `convert`, which writes issue numbers back). Issue numbers link to GitHub when `.github/config.json` is present._

## Instructions

1. **Respect the user's instruction first.** If `User Instructions` (see ## Inputs) is present and not empty, it governs scope, focus, and which sources to read. Follow it, reading only the specs or sources it points you to.
2. **Only if no instruction is provided**, search for and read the upstream specs for the active phase (locate `project/specs/<phase>/`, currently `mvp`): `prd.md`, `design.md`, `tech-specs.md`. _(`prd.md` is created by a prior phase — if it's missing, stop and ask via `AskUserQuestion` rather than guessing.)_
3. Read `.claude/skills/backlog/sample_structure.json` — the canonical groomed shape for the deliverable.

**Phase 1 — lean design:**

4. Launch the **ProductOwner** agent (Stage 1) to design the **lean** backlog. Pass it the user's instruction (when given) and/or the specs you read, plus a pointer to the **Schema** and **Ordering** sections above.
5. Render the design into JSON — lean stories only (`title` / `description` / `priority`, `status` `Backlog`, `issue_number` `0`) — preserving every content decision and the story **order** verbatim, and write `project/backlog.json`.
6. **Present the lean backlog to the user** and gate via `AskUserQuestion`: proceed to grooming, or revise first. Do not groom without approval. On a revise request, re-launch the ProductOwner and repeat phase 1.

**Phase 2 — grooming:**

7. On approval, launch the **ProductOwner** agent (Stage 2) to groom every story. Pass it the lean backlog plus the **Schema** grooming rules (including the work-type-label requirement).
8. Enrich `project/backlog.json` **in place** — keep each story's `title` / `description` / `priority`, add the groomed fields. Do not change titles or the story order. Defer `blocked_by` to the two-pass flow (it needs issue numbers).
9. Run the validator (see **Validation**). If it errors, fix the JSON (or re-launch the ProductOwner for content issues) and re-run until it passes. Then regenerate the readable view.
10. **Present the final groomed backlog** and ask via `AskUserQuestion` whether to `convert` (push to GitHub) now or leave it to the user.
    - If the user **confirms**, run the **two-pass** convert (see **Validation**) — `convert` creates issues, applies labels, mirrors board `Status`/`Priority`/`Size`/`Points`, and writes each `issue_number` back into `project/backlog.json`:

      ```bash
      python3 .github/scripts/projects/cli.py convert
      ```

      If the design carries dependencies, add `blocked_by` as the now-known issue numbers (re-launch the ProductOwner if needed), validate, then `convert` again to set the GitHub edges. Regenerate the readable view after each convert.

    - If the user **declines**, stop after the validated backlog — the file is the final deliverable for this run.

## Rules

- **Important!** The user's instruction takes precedence over the default spec-driven flow. A `<backlog-focus>` (or any direction the user gives) governs scope and sources; the phase specs are the fallback, read only when no instruction is provided.
- **Important!** Both phases are gated by `AskUserQuestion`: lean → approval → groom → final → ask convert. Never groom or convert without the explicit go-ahead.
- **Important!** The ProductOwner owns content (both phases); the main agent owns file mechanics, gates, validation, and CLI calls. Roles do not swap.
- **Important!** The write target is `project/backlog.json` only, authored directly against `sample_structure.json`. Phase 2 enriches it **in place** — no separate sprint file.
- **Important!** The **`title`** is the stable re-link key (convert matches issues by it) and must be unique — never reword a story's title in phase 2 in a way that breaks the link. The GitHub issue **number** is the identity.
- Rendering may fix shape/formatting but must not change content (stories, priorities, descriptions, titles) or the story **order** — the build sequence is itself a content decision.
- Every `blocked_by` entry must be an issue number resolving to another story's `issue_number` in the file. No dangling pointers, no self-blocks, no cycles. Keep acceptance criteria objective and testable.
- If a content or schema question is unresolvable, stop and ask via `AskUserQuestion` — do not guess.

## Acceptance Criteria

The skill is accepted only when every box below is checked:

- [ ] `project/backlog.json` is written by the main agent at exactly that path, and is groomed by the end of the run.
- [ ] The ProductOwner was launched for **both** phases and its designs were rendered into the JSON verbatim; content-level concerns were resolved by re-launching the ProductOwner or asking the user.
- [ ] Phase 1 presented the lean backlog and gated grooming on user approval via `AskUserQuestion`.
- [ ] Phase 2 enriched the backlog in place per the **Schema** — the groomed fields, enum casing, ≥1 work-type label per story; titles and the story order unchanged from phase 1.
- [ ] Stories follow the **Ordering** build sequence (build order carried by array position); any dependency-driven deviation is justified in the story `description` or Open Questions.
- [ ] The validator reports `Backlog validation passed`.
- [ ] The final groomed backlog was presented and the user was asked via `AskUserQuestion` whether to `convert`. Conversion ran only on explicit confirmation; on decline, the run stopped at the validated backlog.
- [ ] Every story is traceable to its source — the user's instruction when one was given, otherwise the upstream specs.

## References

- `.claude/skills/backlog/sample_structure.json` — canonical groomed JSON shape for the deliverable
- `.claude/skills/backlog/scripts/backlog-to-md.py` — renders the readable `project/backlog.md` view
- `.claude/agents/product-owner.md` — ProductOwner designer definition (phase 1 lean + phase 2 grooming)
- `.github/scripts/projects/cli.py` — the projects CLI (`validate`, `convert`, and the state subcommands)
- `.github/scripts/projects/README.md` — the projects package + groomed backlog lifecycle
- Upstream specs (active phase `project/specs/<phase>/`, currently `mvp`): `prd.md`, `design.md`, `tech-specs.md`
