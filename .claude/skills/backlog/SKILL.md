---
name: backlog
description: Two-phase backlog builder — the ProductOwner designs a lean product backlog (phase 1), then grooms it in place into the final groomed backlog (phase 2); the main agent writes project/backlog.json, gates each phase on user approval, checks the backlog shape, and optionally syncs to GitHub via the project_manager CLI.
argument-hint: <backlog-focus>
model: opus
effort: xhigh
---

## Overview

This skill takes a project from a **lean draft** to a **groomed backlog** in **two phases**, with a user-approval gate after each, then offers to push it to GitHub. The single deliverable is `project/backlog.json`, managed by the **`.github/project_manager/`** package.

1. **Phase 1 — lean design.** The **ProductOwner** designs a lean backlog (stories with `title` / `description` / `priority` only). The main agent writes it, **presents it to the user**, and asks for approval to continue. A lean backlog already loads and can `sync`.
2. **Phase 2 — grooming (optional).** On approval, the **ProductOwner** grooms every story (goal, notes, dates, tasks as sub-issues, acceptance criteria, labels, size, points, and `blocked_by` dependencies). The main agent enriches `project/backlog.json` **in place**, checks it, **presents the final backlog**, and asks whether to `sync`.

- **Deliverable:** `project/backlog.json` — one artifact. Authored **directly** by the main agent against `.claude/skills/backlog/sample_structure.json`. There is no markdown step and no separate sprint file.
- **Identity:** the **`title`** is the stable re-link key (globally unique across **all items** — stories _and_ sub-issues); the **GitHub issue number** (minted by `sync`) is the identity, and `blocked_by` references items by that number.
- **Designer:** the **ProductOwner agent** owns content in both phases — story selection and priorities (phase 1), the buildable grooming detail (phase 2). See `.claude/agents/product-owner.md`.
- **Finalizer:** the **main agent** renders each design into JSON, runs the gates, checks the file, and (on approval) syncs.

**Inputs follow a precedence:** the **user's instruction** comes first — a `<backlog-focus>` argument or any direction in the request governs scope, focus, and which sources to read. **Only when no instruction is given** does the skill fall back to the phase specs (`prd.md`, `design.md`, `tech-specs.md`).

_Content-level concerns go back to the ProductOwner or to the user via `AskUserQuestion` — never resolved unilaterally._

## Inputs

### User Instructions

```
$ARGUMENTS
```

## CLI

All backlog/GitHub operations go through the `project_manager` CLI (package at `.github/project_manager/`). Run it from the repo root with `PYTHONPATH=.github`:

```bash
PYTHONPATH=.github python3 -m project_manager.cli <command> [options]
```

Commands used by this skill: `list` (load check), `sync` / `sync --dry-run` (push to GitHub / read-only preview). See `.github/project_manager/README.md` for the full command set (`view`, `update`, `resolve`, `ready`, `pull`, …).

## Schema

The backlog is a list of **stories**; there is **one unified item shape** for stories and sub-issues, and each item maps 1:1 to a GitHub issue. A story's `tasks` are **child items** (nesting is one level deep) that become native GitHub **sub-issues** on `sync`. Grooming is **optional** — a lean item loads and syncs without error. Author against `sample_structure.json`.

**Top-level:** `project` (str), `description` (str), `dates.{start,end}` (YYYY-MM-DD), `stories` (list of items).

**Item — lean core (phase 1):**

- `title` — short imperative title (non-empty); the **re-link key**, so it must be **globally unique across all items**
- `description` — one or two sentences of context (non-empty)
- `priority` — `P0` / `P1` / `P2` (the schema tolerates `""`, but this skill always sets one on stories)

**Item — groomed fields (phase 2)**, empty defaults (`""` / `[]` / `null`) are valid:

- `status` — `Backlog` / `Ready` / `In Progress` / `In Review` / `Done`; author everything as `Backlog` (`Ready` is derived — `resolve`/`sync` promote unblocked stories, never hand-set it here)
- `goal` — one line on why this item matters
- `notes` — extra body prose; may be `""`
- `start_date` / `end_date` — `YYYY-MM-DD` or `""`; map to the board's `Start date` / `Target date` fields
- `tasks` — list of **child items** (same shape, no nested `tasks`); stories only — sub-issues are leaves
- `acceptance_criteria` — list of objective, testable criteria; rendered as a checklist in the issue body
- `labels` — list of labels; include a work-type label (`feature` / `tech` / `bug` / `spike` / `chore` / `docs`) plus any domain labels (`backend`, `frontend`, `infra`, …)
- `blocked_by` — list of dependencies this item is blocked by; each entry is an **item title** (str — the pre-mint authoring form; must exactly match another item's title in this file) or an **issue number** (int — the durable form, also valid for external issues). `sync` converts titles to the minted numbers and writes them back. No self-blocks, no duplicates, no cycles (keep references backward-only)
- `size` — `XS` / `S` / `M` / `L` / `XL`
- `points` — int or `null` (story points)
- `issue_number` — int or `null`; **minted by `sync`** and written back, so leave it `null` for new items

**Important!** Enum values are case-sensitive. There is no `id` and no `type` field — identity is `title` → `issue_number`. Author `blocked_by` **by title** during grooming — no issue numbers needed; `sync` mints the numbers and converts the titles in one pass (see **Checks & sync**).

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

## Checks & sync

After writing or enriching the backlog:

1. **Self-check** against the **Schema** above: required lean fields present, global title uniqueness, enum casing.
2. **Validate** — checks the `blocked_by` graph (dangling titles, self-blocks, duplicates, cycles, duplicate item titles) with no GitHub calls:

   ```bash
   PYTHONPATH=.github python3 -m project_manager.cli validate
   ```

3. **Load check** — the CLI parses the file and prints every item:

   ```bash
   PYTHONPATH=.github python3 -m project_manager.cli list
   ```

4. **Read-only preview** — confirms what a sync would do (issues to create/update) with **zero** GitHub writes:

   ```bash
   PYTHONPATH=.github python3 -m project_manager.cli sync --dry-run
   ```

If any command errors, fix the JSON (or re-launch the ProductOwner for content issues) and re-run until clean.

**Important! Dependencies are authored by title, in one pass.** Groom `blocked_by` with item **titles** directly — no prior sync needed. `sync` validates the graph, mints issue numbers (title-deduped), converts each title entry to the minted number, sets the GitHub blocked-by edges, and writes the numbers back — after which the file carries only ints. Reference already-minted or external issues by **number**.

_Note `sync` also auto-promotes unblocked `Backlog` stories to `Ready` (pass `--no-resolve` to skip); title deps resolve pre-mint, so this works on a never-synced backlog too._

## Readable view

`project/backlog.json` is the source of truth, but a markdown view is easier to scan. After the backlog checks out, regenerate `project/backlog.md` beside it:

```bash
python3 .claude/skills/backlog/scripts/backlog-to-md.py
```

_Generated, never hand-edited — re-run after any backlog change (including `sync`, which writes issue numbers back). Issue numbers link to GitHub when `.github/config.json` is present._

## Instructions

1. **Respect the user's instruction first.** If `User Instructions` (see ## Inputs) is present and not empty, it governs scope, focus, and which sources to read. Follow it, reading only the specs or sources it points you to.
2. **Only if no instruction is provided**, search for and read the upstream specs for the active phase (locate `project/specs/<phase>/`, currently `mvp`): `prd.md`, `design.md`, `tech-specs.md`. _(`prd.md` is created by a prior phase — if it's missing, stop and ask via `AskUserQuestion` rather than guessing.)_
3. Read `.claude/skills/backlog/sample_structure.json` — the canonical groomed shape for the deliverable.

**Phase 1 — lean design:**

4. Launch the **ProductOwner** agent (Stage 1) to design the **lean** backlog. Pass it the user's instruction (when given) and/or the specs you read, plus a pointer to the **Schema** and **Ordering** sections above.
5. Render the design into JSON — lean stories only (`title` / `description` / `priority`, `status` `Backlog`, `issue_number` `null`, `tasks` `[]`) — preserving every content decision and the story **order** verbatim, and write `project/backlog.json`.
6. **Present the lean backlog to the user** and gate via `AskUserQuestion`: proceed to grooming, or revise first. Do not groom without approval. On a revise request, re-launch the ProductOwner and repeat phase 1.

**Phase 2 — grooming:**

7. On approval, launch the **ProductOwner** agent (Stage 2) to groom every story. Pass it the lean backlog plus the **Schema** grooming rules (including the unified item shape for `tasks` sub-issues and the label guidance).
8. Enrich `project/backlog.json` **in place** — keep each story's `title` / `description` / `priority`, add the groomed fields; author `tasks` as lean child items (globally unique titles, `issue_number` `null`). Do not change titles or the story order. Author `blocked_by` **by title** directly in this phase — `sync` converts titles to issue numbers later.
9. Run the checks (see **Checks & sync**). If anything errors, fix the JSON (or re-launch the ProductOwner for content issues) and re-run until clean. Then regenerate the readable view.
10. **Present the final groomed backlog** and ask via `AskUserQuestion` whether to `sync` (push to GitHub) now or leave it to the user.
    - If the user **confirms**, run the **single-pass** sync (see **Checks & sync**) — `sync` validates the graph, creates issues (title-deduped), converts title `blocked_by` entries to the minted numbers, rebuilds bodies, reconciles labels, mirrors board `Status` / `Priority` / `Start date` / `Target date`, sets the blocked-by edges, links sub-issues, and writes each `issue_number` (and the converted deps) back into `project/backlog.json`:

      ```bash
      PYTHONPATH=.github python3 -m project_manager.cli sync
      ```

      Regenerate the readable view after the sync (it rewrites the file).

    - If the user **declines**, stop after the checked backlog — the file is the final deliverable for this run.

## Rules

- **Important!** The user's instruction takes precedence over the default spec-driven flow. A `<backlog-focus>` (or any direction the user gives) governs scope and sources; the phase specs are the fallback, read only when no instruction is provided.
- **Important!** Both phases are gated by `AskUserQuestion`: lean → approval → groom → final → ask sync. Never groom or sync without the explicit go-ahead.
- **Important!** The ProductOwner owns content (both phases); the main agent owns file mechanics, gates, checks, and CLI calls. Roles do not swap.
- **Important!** The write target is `project/backlog.json` only, authored directly against `sample_structure.json`. Phase 2 enriches it **in place** — no separate sprint file.
- **Important!** The **`title`** is the stable re-link key (`sync` dedupes issues by it) and must be globally unique across all items — never reword a title in phase 2 in a way that breaks the link. The GitHub issue **number** is the identity.
- Author all statuses as `Backlog` — `Ready` is derived by `resolve`/`sync`, and the later statuses belong to execution, not authoring.
- Rendering may fix shape/formatting but must not change content (stories, priorities, descriptions, titles) or the story **order** — the build sequence is itself a content decision.
- Every `blocked_by` entry must be another item's exact **title** (pre-mint) or an issue **number**. No dangling pointers, no self-blocks, no duplicates, no cycles — `validate` enforces all of this. Keep acceptance criteria objective and testable.
- If a content or schema question is unresolvable, stop and ask via `AskUserQuestion` — do not guess.

## Acceptance Criteria

The skill is accepted only when every box below is checked:

- [ ] `project/backlog.json` is written by the main agent at exactly that path, and is groomed by the end of the run.
- [ ] The ProductOwner was launched for **both** phases and its designs were rendered into the JSON verbatim; content-level concerns were resolved by re-launching the ProductOwner or asking the user.
- [ ] Phase 1 presented the lean backlog and gated grooming on user approval via `AskUserQuestion`.
- [ ] Phase 2 enriched the backlog in place per the **Schema** — the groomed fields, enum casing, `tasks` as unified child items; titles and the story order unchanged from phase 1.
- [ ] Stories follow the **Ordering** build sequence (build order carried by array position); any dependency-driven deviation is justified in the story `description` or Open Questions.
- [ ] `validate`, `list`, and `sync --dry-run` all run clean on the final file (see **Checks & sync**).
- [ ] The final groomed backlog was presented and the user was asked via `AskUserQuestion` whether to `sync`. Sync ran only on explicit confirmation; on decline, the run stopped at the checked backlog.
- [ ] Every story is traceable to its source — the user's instruction when one was given, otherwise the upstream specs.

## References

- `.claude/skills/backlog/sample_structure.json` — canonical groomed JSON shape for the deliverable
- `.claude/skills/backlog/scripts/backlog-to-md.py` — renders the readable `project/backlog.md` view
- `.claude/agents/product-owner.md` — ProductOwner designer definition (phase 1 lean + phase 2 grooming)
- `.github/project_manager/` — the project-manager package; entry point `python3 -m project_manager.cli` (`list`, `sync`, `pull`, `update`, `resolve`, …)
- `.github/project_manager/README.md` — package docs: schema, commands, two-pass authoring flow, GitHub Actions automation
- Upstream specs (active phase `project/specs/<phase>/`, currently `mvp`): `prd.md`, `design.md`, `tech-specs.md`
