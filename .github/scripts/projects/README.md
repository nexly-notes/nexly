# projects

A single Python package + CLI that drives the **backlog lifecycle** on **GitHub Issues + Projects (v2)**: author a product backlog (lean or groomed), validate it, then push it to GitHub in one command.

- **Backlog** — `docs/backlog.json`: a flat list of **stories**. Each story needs only `title`, `description`, and `priority`; grooming (`status`, `goal`, `notes`, `tasks`, `acceptance_criteria`, `labels`, `blocked_by`, `size`, `points`) is **optional** and added later. A **lean** backlog validates and converts just like a groomed one.
- **Identity** — the **GitHub issue number** is a story's identity, minted by `convert` and written back as `issue_number`. The **`title`** is the re-link key (so titles must be unique). `blocked_by` references other stories by their **issue number**.
- **`convert`** — the single GitHub push: creates/updates one issue per story (matched by `title`), writes the issue body (Goal / Tasks / Acceptance Criteria / Notes when present), applies labels, mirrors `Status` / `Priority` / `Size` / `Points` to the board, sets `blocked_by` edges, and writes each `issue_number` back into the JSON.

*Authored by the two-phase `/backlog` skill (`.claude/skills/backlog/`), driven by the ProductOwner agent. This package is the machinery it calls.*

## Usage

Two equivalent invocations (the first is path-robust from any cwd):

```bash
python3 .github/scripts/projects/cli.py <command> …
cd .github/scripts && python3 -m projects <command> …
```

**Commands** (`--repo` / `--project` / `--owner` override the configured identity on every command):

```
validate <path>                     # check a backlog JSON (lean or groomed) against the lenient schema
convert [--dry-run] | sync          # backlog -> issues + board, write issue_number back
list [--status S][--priority P][--json]
order [--json]                      # work sequence by priority, blocker before dependent (exit 1 on a cycle)
view <issue-number>                 # issue + its Status/Priority/Size/Points
status <n> <value>                  # set the item's Status
delete <n> [--keep-issue]           # remove from project (and delete the issue)
delete-all [--dry-run]              # tear down the project + clear backlog issue_numbers
```

*`convert --dry-run` runs every pass (it still creates/updates issues) but does not write `issue_number` back to the JSON.*

*`convert` is idempotent — a no-op re-run makes no changes (issues are re-linked by `title`; unchanged bodies, fields, and edges are skipped; `--add-label` is a no-op when the label is present).*

### Two-pass dependency flow

Issue numbers don't exist until `convert` runs, and `blocked_by` is a list of issue numbers — so dependencies are authored **after** a first convert:

1. **Convert** the lean backlog — GitHub mints issue numbers, written back into `backlog.json`.
2. **Groom** (the `final-backlog` workflow) — adds `tasks` / `acceptance_criteria` / `labels` / `size` / `points`, names each story's hard dependencies by title, and resolves them to the now-known issue numbers as `blocked_by` (backward-only in the build order, so the graph stays acyclic).
3. **Convert again** (idempotent) — sets bodies, labels, board fields, and the GitHub "blocked by" edges.

*A backlog with no `blocked_by` (e.g. the initial lean draft) is unaffected by step 1.*

## Layout

One package, concern-split modules, one CLI dispatching every subcommand:

- **`config.py`** — loads `.github/config.json`; `Identity` + repo-root / backlog paths.
- **`gh.py`** — shared `gh`/GraphQL client: run, batched mutations, node-ids, issue list/view, labels, plus the issue-body refresh and `blocked_by` edges used by `convert`.
- **`board.py`** — Projects v2 fields: metadata, field-map, ensure/create fields, `set_field`. `CONVERT_FIELDS` = `Status` + `Priority` + `Size` + `Points`, all ensured and synced by `convert`.
- **`backlog.py`** — `stories` load/save/clear (writeback matches by `title`); `build_issue_body` (`description` → `## Goal` → `## Tasks` → `## Acceptance Criteria` → `## Notes`, empty sections skipped).
- **`conversion.py`** — the `convert` workflow (the single push for the backlog).
- **`state.py`** — `list` / `order` / `view` / `status` / `delete` / `delete-all`.
- **`validation.py`** — the lenient backlog schema (`validate`).
- **`cli.py` / `__main__.py`** — the one argparse tree + dispatch.

## Config

GitHub identity lives in **`.github/config.json`** — edit it to retarget:

```json
{ "project": "nexly-notes", "repo": "nexly-notes/nexly", "owner": "nexly-notes", "project_number": 1 }
```

*Secrets stay with `gh` auth — nothing sensitive is stored here.*

## Data shape

- **`docs/backlog.json`** — see `.claude/skills/backlog/sample_structure.json` and the `/backlog` skill. Required per story: `title` (unique), `description`, `priority`. Grooming fields are validated **only when present**.
- **`title`** is the re-link key, so it must be unique across stories. **`issue_number`** is the identity (`0` / absent until `convert` mints it). **`blocked_by`** is a list of issue numbers; each must resolve to an in-file `issue_number` and a story may not block itself.
- **`labels`** (when present) must include at least one **work-type label** — `feature` / `tech` / `bug` / `spike` / `chore` / `docs` / `review`; the label is the sole carrier of issue type, and domain labels (`backend`, `frontend`, …) are allowed extras but don't satisfy the rule.

**Important!** One issue per story, matched by `title`. `convert` is the only GitHub write and is idempotent. Because it creates issues in parallel, **issue numbers are not sequential in build order** — build order lives in the array/markdown order, and `order` derives sequencing from priority + `blocked_by` edges, not raw issue numbers.

## Tests

```bash
python3 -m pytest .github/scripts/projects/tests -q          # unit suite (gh mocked, no network)
```

The live end-to-end test (`convert → delete-all` against the real project) is opt-in and **destructive** to the configured project:

```bash
cd .github/scripts && RUN_LIVE_TESTS=1 python3 -m pytest projects/tests -m e2e -q
```

**Important!** Live board ops (`convert`, `status`, `list`, `order`, `view`, `delete-all`) need a `gh` token with the **`project`** scope (a plain `repo` token can't read/write the board). Grant it with `gh auth refresh -s project,read:project` on the **correct** account — `validate` and the unit suite need no scopes.
