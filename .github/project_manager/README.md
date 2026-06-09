# project_manager

Local JSON-based backlog management with one-way + mirror-back GitHub Projects (v2) sync. Day-to-day work reads and writes a single file — `backlog.json` — with no GitHub API calls. `sync` pushes the backlog to GitHub; `pull` mirrors GitHub state back. Both are **manual** subcommands (there is no file watcher).

Every backlog **item** — a story *or* a sub-issue — uses one unified shape. On GitHub each item becomes a real issue + project-board item with its own status, priority, labels, dates, acceptance criteria, and blocked-by edges. A story's `tasks` become its native **sub-issues** (nesting is one level deep).

## Layout

```
project_manager/
├── __init__.py              # Exposes ProjectManager, Syncer
├── cli.py                   # argparse wrapper — entry point
├── manager.py               # ProjectManager: list/view/update/add/progress/ready/sync/pull
├── sync.py                  # Syncer: push (sync) + mirror-back (pull) GitHub Issues & Projects v2
├── config.py                # Loads GitHub identity from .github/config.json; derives data paths
├── templates/
│   └── issue_view.txt       # Default template for `view` command
├── utils/
│   └── gh_utils.py          # `gh` CLI wrappers (run, gh_json)
└── tests/                   # Unit + e2e tests
```

The backlog itself lives at the repo root: `project/backlog.json` (resolved by `config.py`).

> **Note:** the old `watcher.py` / `resolver.py` (auto-resolve + auto-sync on file edit) were removed — sync is manual now. The `watchdog` dependency is no longer used.

The entry point is the `cli` module:

```bash
python -m project_manager.cli <command> [options]
```

---

## Schema

#### Statuses: `Backlog` · `Ready` · `In Progress` · `Done`
#### Priorities: `P0` · `P1` · `P2`

`Ready` is a derived "workable" status: `resolve` promotes unblocked `Backlog`
items into it, and `ready` lists what's sitting there. You don't hand-set it in
the usual flow — `resolve` does.

There is **one item shape**, reused for stories and sub-issues. Identity is the **`title`** (globally unique across all items, pre-sync) → **`issue_number`** (GitHub identity, minted by `sync`). There is no `id` and no `type`.

```
item := {
  "title": str, "description": str,
  "status": "Backlog|In Progress|Done", "priority": "P0|P1|P2",
  "goal": str, "notes": str,
  "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD",
  "acceptance_criteria": [str, ...], "labels": [str, ...],
  "blocked_by": [int, ...],          # issue numbers (backward-only ⇒ acyclic)
  "size": str, "points": int|null,
  "issue_number": int|null,          # minted by sync
  "tasks": [item, ...]               # parents only; sub-issues are leaves
}

root := { "project": str, "description": str,
          "dates": {"start": "YYYY-MM-DD", "end": "..."},
          "stories": [item, ...] }
```

A **lean** item (only `title`/`description`/`tasks`, `status` defaulting to `Backlog`, everything else empty) and a fully **groomed** item both load and sync without error. `blocked_by` holds **issue numbers**, so dependencies are named only after the blocker has been synced.

```json
{
  "project": "Avaris",
  "description": "Establish foundational infrastructure",
  "dates": { "start": "2026-02-17", "end": "2026-03-02" },
  "stories": [
    {
      "title": "Research feature X",
      "description": "Investigate feature X impact on accuracy.",
      "status": "In Progress", "priority": "P0",
      "goal": "Rank candidate features", "notes": "",
      "start_date": "2026-02-17", "end_date": "2026-02-20",
      "acceptance_criteria": ["Criterion 1"], "labels": ["spike"],
      "blocked_by": [], "size": "M", "points": 3,
      "issue_number": 447,
      "tasks": [
        {
          "title": "Run analysis",
          "description": "Score features against the historical dataset.",
          "status": "Backlog", "priority": "P1",
          "goal": "", "notes": "", "start_date": "", "end_date": "",
          "acceptance_criteria": [], "labels": [], "blocked_by": [],
          "size": "", "points": null, "issue_number": 512
        }
      ]
    }
  ]
}
```

### Two-pass authoring flow

1. **Author** a lean backlog — each item carries only `title`, `description`, `tasks`.
2. **`sync`** — GitHub mints `issue_number`s (deduped by **title**), written back to parents *and* children.
3. **Groom** — fill `priority/goal/notes/dates/acceptance_criteria/labels/size/points` on parents *and* sub-issues; name hard deps as `blocked_by` issue numbers (backward-only ⇒ acyclic).
4. **`sync` again** — idempotent: bodies, labels, board fields (incl. dates), blocked-by edges, parent↔child sub-issue links.

---

## Commands

### list (alias: `ls`)

```bash
python -m project_manager.cli list
python -m project_manager.cli list --status "In Progress"
python -m project_manager.cli list --priority P0
python -m project_manager.cli list --subissues "Research feature X"   # sub-issues under a parent
python -m project_manager.cli list --subissues 447                    # ...or by issue number
python -m project_manager.cli list --sort-by priority
python -m project_manager.cli list --wide                         # adds SIZE / PTS columns
python -m project_manager.cli list --keys-only                    # issue numbers (or titles, pre-sync)
python -m project_manager.cli list --json
```

Columns: `#` (issue number) · STATUS · PRI · TITLE (`--wide` adds SIZE · PTS). No ID/TYPE columns.

### view

```bash
python -m project_manager.cli view "Research feature X"
python -m project_manager.cli view 447                  # by issue number
python -m project_manager.cli view 447 --raw            # key-value pairs
python -m project_manager.cli view 447 --tasks          # child sub-issues only
python -m project_manager.cli view 447 --ready-tasks    # children still in Backlog
python -m project_manager.cli view 447 --ac             # acceptance criteria only
python -m project_manager.cli view 447 --json
```

Accepts an item **title** or **issue number**. Viewing a story also shows its child sub-issues (unless a narrowing flag is passed).

### update

Works on **any item** (story or sub-issue), resolved by title or issue number.

```bash
python -m project_manager.cli update "Research feature X" --status "In Progress"
python -m project_manager.cli update 447 --priority P1 --size M --points 3
python -m project_manager.cli update 447 --goal "Rank features" --notes "see spike"
python -m project_manager.cli update 447 --start-date 2026-02-17 --end-date 2026-02-20
python -m project_manager.cli update 447 --labels infra p0          # replaces the list
python -m project_manager.cli update 447 --ac "Green CI" "Docs updated"
```

#### Status transitions

Valid flow: `Backlog → Ready → In Progress → Done`. Reverse arrows let you demote without `--force`. `resolve` writes the `Backlog → Ready` hop for you; you advance `Ready → In Progress` with `update`.

| From         | To                       |
|--------------|--------------------------|
| Backlog      | Ready, In Progress       |
| Ready        | In Progress, Backlog     |
| In Progress  | Done, Backlog            |
| Done         | In Progress              |

`--force` bypasses the guardrail for one-shot overrides.

### add-issue

```bash
python -m project_manager.cli add-issue --title "Research X"
python -m project_manager.cli add-issue --title "Fix crash" --description "Repros on iOS Safari."
```

Adds a **lean** top-level story (`status=Backlog`, empty groom fields, `tasks=[]`, `issue_number=null`). The title must be globally unique. There is no `--type` / `--priority` at creation — groom those later with `update`.

### add-subissue

```bash
python -m project_manager.cli add-subissue --story "Research X" --title "Write tests"
python -m project_manager.cli add-subissue --story 447 --title "Write tests" --description "Cover the 401 branch."
```

Appends a **lean child item** (a leaf — no nested `tasks`) under the parent issue (selected with `--story`, by title or issue number). The title must be globally unique. Nesting is one level — you cannot add a sub-issue under a sub-issue.

### summary

```bash
python -m project_manager.cli summary
python -m project_manager.cli summary --group-by priority
```

### progress

```bash
python -m project_manager.cli progress
```

Header is `{project} - {description}`. Shows overall completion, story status distribution, story completion, and per-story done ratios (child sub-issues with `status == "Done"` / total children).

### resolve

Derives readiness and **writes it**: promotes every workable `Backlog` story to the `Ready` status. A story is workable when its status is `Backlog` and every `blocked_by` issue number resolves to a `Done` item (across both nesting levels), or it has no deps. Sub-issues are never resolved. This is the only command that computes readiness; `ready` just reads the result.

Candidates rank by `priority` (P0 < P1 < P2), then `title`.

```bash
python -m project_manager.cli resolve
python -m project_manager.cli resolve --top                  # resolve only the top-ranked candidate
python -m project_manager.cli resolve --story "Research X"   # resolve one story (if workable)
```

### ready

Read-only listing of **stories** whose `status` is already `Ready` (i.e. what `resolve` has marked workable). Sub-issues never appear here. Ranked by `priority`, then `title`. To start one, move it on with `update <story> --status "In Progress"`.

```bash
python -m project_manager.cli ready
python -m project_manager.cli ready --top                    # single top-ranked story
python -m project_manager.cli ready --story "Research X"     # narrow to one story
python -m project_manager.cli ready --json
```

### sync

Pushes **every item** (stories + sub-issues) to GitHub Issues + Projects (v2). Requires the `gh` CLI authenticated. Defaults come from `config.py`.

```bash
python -m project_manager.cli sync
python -m project_manager.cli sync --dry-run                 # read-only preview
python -m project_manager.cli sync --repo owner/repo --project 5 --owner owner
python -m project_manager.cli sync --delete-all
python -m project_manager.cli sync --delete-all --dry-run
```

Passes: ensure required board fields + options (incl. the `Ready` Status option) → resolve/create issues (title-deduped) → refresh bodies → reconcile labels → add to project + batch field updates (Status · Priority · Start date · Target date) → set blocked-by edges → reconcile native sub-issue links → write minted numbers back.

> Local `end_date` maps to GitHub's built-in **`Target date`** board field (not a separate "End date" field). `start_date` maps to `Start date`.

> The board's `Status` field needs a `Ready` option for `resolve`'s output to push. `sync` ensures it: it's included when the field is created, and appended to a pre-existing `Status` field (existing options are re-sent so they're preserved; their colors reset to gray once when `Ready` is first added).

The issue body is rebuilt from the item's `description` and its `acceptance_criteria` (`## Acceptance Criteria` checklist). Tasks are **native sub-issues**, not body checkboxes. Field/body/edge/link passes diff against the remote snapshot, so an unchanged re-sync emits zero create/link mutations.

> `sync --dry-run` is **fully read-only**: it reads the open-issue list and the project's fields, prints a plan (issues it would create, how many it would update, and any missing board fields or the `Ready` option it would add), and makes **zero** GitHub writes. (`pull --dry-run` is likewise read-only.)

### pull

Mirrors GitHub state back into `backlog.json` (full mirror).

```bash
python -m project_manager.cli pull
python -m project_manager.cli pull --dry-run                 # prints a per-item diff, writes nothing
python -m project_manager.cli pull --repo owner/repo --project 5 --owner owner
```

**GitHub wins** per item for `priority`, `labels`, `title`, `description`, `blocked_by`, and the parent↔child sub-issue structure. **Preserved locally** (never overwritten): each item's `status`, `start_date`/`end_date`, `goal`, `notes`, `size`, `points`, `acceptance_criteria`, and the root `dates`. A new GitHub issue becomes a new story (or a sub-issue of a known parent); board-absent local stories are kept as-is. The tree follows GitHub's sub-issue links, flattened to one level. Run `sync` before `pull` so every item is numbered and on the board.

---

## config

The GitHub identity is externalized to **`.github/config.json`** — edit that file to retarget:

```json
{
  "project": "nexly-notes",
  "repo": "nexly-notes/nexly",
  "owner": "nexly-notes",
  "project_number": 1
}
```

`config.py` is a thin loader: it reads `config.json` for the identity and derives the repo-relative `DATA_PATHS` in code. Override per-invocation with `--repo`, `--project`, and `--owner` on `sync` / `pull`.

---

## Tests

```bash
python -m pytest project_manager/tests -q          # unit (e2e auto-skipped)
python -m pytest project_manager/tests/test_sync_e2e.py -m e2e   # live GitHub (destructive)
```

`test_manager.py` / `test_cli.py` cover local backlog operations; `test_sync.py` covers push + pull logic with mocked `gh`; `test_sync_e2e.py` is the opt-in end-to-end suite.
