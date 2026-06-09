---
description: Set up this project's local development environment from scratch
argument-hint: [optional: specific stack hint, e.g. "python", "node", "rust"]
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
model: sonnet
---

# Set up project environment

You are setting up a fresh local development environment for this project. The user has just cloned the repo (or wants to reset their env) and needs everything ready to run.

If `$ARGUMENTS` is non-empty, treat it as a hint about the stack and skip detection where possible. Otherwise, detect the stack yourself.

## When to use this vs related commands

- **This command** — **owns the feature/runtime/test dependency stack** and local environment setup: toolchain checks, installing those dependencies, `.env` files, local services, git hooks, and verifying the environment actually runs. The scaffolder-intrinsic dependencies and the chosen CSS/UI-solution unit come whole from `/development:setup-app-structure` and are not re-installed here. Use it whenever dependencies need installing or the environment needs (re)building — whether the repo was just scaffolded or freshly cloned.
- **`/development:setup-app-structure`** — creates the project scaffold, whole-repo folder shape, and baseline repo tooling, and installs whatever the scaffolder and chosen CSS/UI solution intrinsically pull in. It does not install the feature/runtime/test stack; run this command after it.
- **`/development:backend-skeleton`** — builds the backend's running wiring (the architecture pattern implemented as a vertical slice). It does not install dependencies; run this command to install and verify.

The three form a pipeline: scaffold → running wiring → **install and verify here**.

## Step 1 — Detect the stack

Look for these markers in the repo root (and one level down if needed):

- `package.json` → Node/JS/TS. Note the package manager: `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb` → bun, otherwise npm.
- `pyproject.toml` / `requirements.txt` / `Pipfile` / `uv.lock` → Python. Prefer `uv` if `uv.lock` exists, else `poetry` for pyproject, else `pip` + venv.
- `Cargo.toml` → Rust (cargo).
- `go.mod` → Go.
- `Gemfile` → Ruby (bundler).
- `composer.json` → PHP (composer).
- `mix.exs` → Elixir.
- `pubspec.yaml` → Dart/Flutter.
- `Dockerfile` / `docker-compose.yml` → note for later, may need `docker compose up`.
- `.nvmrc` / `.tool-versions` / `.python-version` / `rust-toolchain.toml` → pinned versions, respect them.
- `Makefile` / `justfile` / `Taskfile.yml` → check for a `setup`, `bootstrap`, or `install` target and prefer it over manual steps.

**If none of these markers are found** (a specced-but-unscaffolded repo), infer the intended stack from project docs instead of giving up:

- Read `CLAUDE.md`, `AGENTS.md`, `README.md`, and the spec/architecture docs — `prd.md`, `tech-specs.md` / `tech-spec.md`, `architecture.md`, and anything under `project/specs/`, `docs/`, or `spec/`.
- Extract the intended language, framework, package manager, and any pinned runtime versions.
- **Set up the package manager** accordingly: ensure the right one is installed/enabled at the specified version (e.g., Corepack for pnpm/yarn, `uv` or `poetry` for Python, the `cargo`/`go` toolchain). Respect any pinned version files or versions named in the docs.
- **Configure the manifest yourself. This is non-negotiable and never gated by a question.** Write or correct the package manager manifest (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.) with the chosen package manager, pinned versions, scripts, and the dependencies the docs call for — without asking.
- Do **not** do full app scaffolding — framework boilerplate, directory layout, `README`, `.gitignore`, and linter/formatter config remain `/development:setup-app-structure`'s job. You own the manifest; that command owns the scaffold around it.
- If the docs are silent or contradictory on the stack, stop and ask the user rather than guessing.

After this there is always a manifest to install from. If the broader app structure is still missing, note that `/development:setup-app-structure` handles full scaffolding, then continue with the manifest you configured.

State your findings in one short sentence before acting.

## Step 2 — Verify required toolchain

Check that the required runtime/package manager exists at the right version. Run `--version` checks. If something is missing or wrong:

- Don't silently install global tooling.
- Tell the user exactly what's missing, the expected version (from any pinned version file), and the recommended way to install it on their OS.
- Stop and ask before proceeding.

## Step 3 — Look for project-defined setup

Before doing anything manual, check for:

1. A `setup`, `bootstrap`, `init`, or `install` target in `Makefile` / `justfile` / `Taskfile.yml` / `package.json` scripts.
2. A `scripts/setup.sh`, `bin/setup`, or `script/bootstrap` file (Rails/GitHub convention).
3. Instructions in `README.md`, `CONTRIBUTING.md`, or `docs/development.md`.

If any exist, prefer them over inventing your own steps. Read them, summarize what they'll do, and run them. If running them would install dependencies, apply the Step 4 confirmation gate first.

## Step 4 — Install dependencies

Only if Step 3 didn't cover it.

**Confirm before running the install command.** The manifest is already configured (Step 1) and that is never gated — but actually installing dependencies is. Show the user the exact install command and the working directory, then ask which they want:

- **Claude runs it** — you execute the install command now.
- **User installs it themselves** — do not run anything. Print the exact command(s) and working directory, treat dependency installation as the user's to complete, and continue with the setup steps that don't require installed deps. Explicitly flag any later verification you must skip as a result.

Wait for the answer before running any install command. This gate applies only to the install command — never to configuring the manifest, which you always do.

Once the user opts for Claude to run it:

- Run the appropriate install command for the detected stack.
- For Python without a project-defined setup, create a virtual environment in `.venv` first, then install.
- For Node, run the install command matching the lockfile.
- Stream output so the user can see what's happening; don't suppress errors.

## Step 5 — Environment variables

- If `.env.example` / `.env.sample` / `.env.template` exists and `.env` does not, copy it to `.env`.
- Read the example and list the variables the user will likely need to fill in. Group them: definitely required, optional, has sensible default.
- Do **not** invent or guess secret values. Leave placeholders in place and tell the user which ones to set.

## Step 6 — Local services

If `docker-compose.yml` (or `compose.yaml`) is present:

- List the services it defines.
- Ask the user whether to start them now. Don't auto-start — they may have these running already or want different ports.

If the project uses a database with migrations (Django, Rails, Prisma, Alembic, Diesel, Ecto, etc.), point this out and offer to run migrations after services are up.

## Step 7 — Git hooks

If `.husky/`, `.pre-commit-config.yaml`, `lefthook.yml`, or similar exists, install the hooks (`pre-commit install`, `lefthook install`, husky install via the package's own install script, etc.).

## Step 8 — Verify

Run the smallest possible sanity check that proves the environment works:

- A test command (`npm test`, `pytest`, `cargo test`, `go test ./...`) — but only a quick subset if the full suite is slow.
- Or a build / typecheck / lint command if tests are heavy.
- Or just `--version` on the project's main CLI if it's a tool.

Report what passed and what didn't.

## Step 9 — Summarize

End with a short, scannable summary:

- ✅ what's working
- ⚠️ what needs the user's attention (env vars to fill, services to start, manual steps)
- ▶️ the exact command to start the dev server / run the app

Keep this summary tight. The user wants to start coding, not read a wall of text.

---

**Rules throughout:**

- Don't `sudo` anything without asking.
- Don't install global packages without asking.
- Don't modify files outside the repo without asking.
- If a step fails, stop and report it rather than papering over with workarounds.
- If the repo looks empty or unrecognizable, say so and ask the user what kind of project this is.
