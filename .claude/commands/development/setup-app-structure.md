---
description: Scaffold a new application's framework, directory layout, and baseline repo tooling — any stack
argument-hint: [stack] e.g. react-ts, next, fastapi, express, go
allowed-tools: Bash(mkdir:*), Bash(touch:*), Bash(npm:*), Bash(npx:*), Bash(pnpm:*), Bash(yarn:*), Bash(uv:*), Bash(pip:*), Bash(python:*), Bash(go:*), Bash(cargo:*), Bash(git:*), Bash(echo:*), Bash(cat:*), Bash(ls:*), Bash(tree:*), Write, Edit, Read
---

# Setup App Structure

You are scaffolding the directory structure and baseline tooling for a new application.

## When to use this vs related commands

- **This command** — project genesis for any stack (frontend, backend, mobile, full-stack): the framework scaffold, whole-repo folder shape, and baseline repo tooling (`README`, `.gitignore`, linter/formatter config, baseline `.env.example`). It also lays out the chosen architecture pattern *as static layout* — folders and file-placement conventions — deferring only *backend runtime layering* to `/development:backend-skeleton`. It installs only what the scaffolder and chosen CSS/UI solution intrinsically pull in; it does not own the feature/runtime/test dependency stack.
- **`/development:backend-skeleton`** — run _after_ this on a backend to turn that laid-out pattern into *running wiring* (entrypoint/config/routing/service/data-access seam, middleware, centralized error handling, health endpoint, a vertical slice a request flows through end to end).
- **`/development:setup-project`** — **owns the feature/runtime/test dependency stack** and local environment setup (deps, `.env`, services, git hooks, run-verification). Run it after scaffolding to install and verify.

The three compose as a pipeline — scaffold here → running wiring in `/development:backend-skeleton` → install and verify in `/development:setup-project` — and none reproduces another's work.

### Structure vs skeleton, and how far this goes by stack

- **The "does it run?" test.** This command produces *static shape* — folders, file-placement conventions, and the chosen architecture pattern laid out as real files. Nothing new executes. `/development:backend-skeleton` produces *running wiring* — the pattern implemented so a request flows end to end through one vertical slice. If nothing new executes it was structure; if you can hit an endpoint it was skeleton.
- **The boundary is fixed; the weight shifts by stack.** For a frontend or BaaS stack (e.g. Next.js + Supabase) this command is heavy — the frontend's internal architecture (`components/`, `lib/`, `stores/`, `hooks/`, the state/data-flow pattern) lives here — and `/development:backend-skeleton` is thin or skipped, since the backend is the BaaS wired as migrations/functions/access rules. For a traditional backend this command is thin (the framework default) and `/development:backend-skeleton` is heavy.

## Stack target

The user passed: **$ARGUMENTS**

If `$ARGUMENTS` is empty or ambiguous, search for any prd.md or tech-specs.md to understand the architecture. If no specs present, ask the user to clarify the stack before proceeding.

- **Frontend:** `react-ts`, `react-vite`, `next`, `vue`, `svelte`
- **Backend:** `express`, `fastapi`, `django`, `go`, `rails`
- **Full-stack:** `next-fullstack`, `t3`, `remix`
- **Mobile:** `expo`, `react-native`
- **Other:** ask the user to describe

Stop and wait for their reply before proceeding.

## Workflow

1. **Inspect the current directory.** Run `ls -la`. If there are existing files that would conflict, surface them and ask: overwrite, skip, or scaffold into a new subdirectory?

2. **Propose the structure first, then execute.** Before creating anything, output:
   - A tree diagram of the directories and files you intend to create
   - A short rationale for non-obvious choices (why `src/` is split this way, why this particular config is included)
   - The package manager and runtime versions you'll target
   - Any tradeoff decisions you'd otherwise silently make (CSS solution for React, ORM for backend, monorepo vs single package). A chosen CSS or UI solution is one cohesive unit — config plus the dependency the scaffolder pulls in plus the entry stylesheet — and you wire it completely here; never leave a config file pointing at a dependency you punted to a later command.

   Wait for confirmation ("looks good", "proceed", "ship it") before running setup commands. If the user requests changes, revise and re-confirm.

3. **Create the structure.** Once approved:
   - Prefer the framework's official scaffolder when one exists (`npm create vite@latest`, `npx create-next-app@latest`, `uv init`, `go mod init`, `cargo new`, `rails new`) over hand-rolling directories
   - Pin to current stable versions; no pre-release unless asked
   - Initialize git if not already a repo, with a `.gitignore` appropriate to the stack
   - Add a `README.md` with: project name (ask if unknown), one-line description, prerequisites, install/run/test commands, and a "Project structure" section mirroring the tree
   - Add `.env.example` if the stack uses env vars
   - Add linter/formatter config with sensible defaults (eslint + prettier for JS/TS, ruff for Python, gofmt is built in) — don't over-configure
   - Defer *backend runtime layering* to `/development:backend-skeleton` — don't hand-build a running entrypoint/routing/service stack here. But do lay out the chosen architecture as static shape: for a frontend or BaaS stack, create its folders (`components/`, `lib/`, `stores/`, `hooks/`, etc.) with real starter files, not empty stubs; for a traditional backend, leave the framework's default layout in place for the skeleton to build on.

4. **Verify the scaffold (structure only).** Confirm the official scaffolder completed cleanly and the expected files and tree exist. Do **not** run a standalone install of the feature/runtime/test dependency stack or a build/run smoke test — that stack and run-verification are owned by `/development:setup-project`. Whatever the scaffolder and your chosen CSS/UI solution intrinsically install is part of genesis and stays; don't re-install those, add a separate install step for them, or punt a config's own dependency to a later command.

5. **Report.** Print the final tree (`tree -L 3 -I 'node_modules|.venv|dist|.git|target'` or equivalent) and a brief "Next steps" list: which file the user probably wants to edit first, where tests live, and the pipeline to finish setup — for a backend, `/development:backend-skeleton` for the running wiring, then `/development:setup-project` to install dependencies and verify the app runs (for a frontend, `/development:setup-project` next).

## Principles

- **Minimum viable structure.** No speculative folders. Add a directory when there's a file to put in it.
- **Convention over configuration.** Match framework defaults; don't reorganize what the community already agrees on.
- **No placeholder cruft.** Don't fill folders with empty `index.ts` files to make the tree look populated.
- **Genesis and folder shape.** Own the scaffold, repo tooling, and the architecture laid out as folders and file-placement; defer only a backend's *runtime layering* to `/development:backend-skeleton`.
- **Keep cohesive units whole.** Never split a config from the dependency it requires across the command boundary — a config plus its dependency plus its entry file ship together or not at all.
- **Structure, not the dependency stack.** Install only what the scaffolder and chosen CSS/UI solution intrinsically pull in; the feature/runtime/test dependency stack and run-verification are `/development:setup-project`'s.
- **Stop and ask** on major tradeoff decisions rather than silently picking.
