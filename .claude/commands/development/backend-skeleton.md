---
description: Build a runnable backend skeleton that fits the project's stack and conventions
argument-hint: [stack or service to skeleton] e.g. fastapi, express-ts, go, spring
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# Build Backend Skeleton

Building the backend skeleton for: **$ARGUMENTS**

If `$ARGUMENTS` is empty, detect the stack from the repo; if there's no stack to detect, ask before proceeding.

A skeleton is the load-bearing backbone a backend grows into: a runnable server, a layered structure, and wired cross-cutting concerns. It is **not** the product. Where `/development:setup-app-structure` lays out *static shape* — the architecture pattern as folders and file-placement, with nothing executing — this command produces *running wiring*: the pattern implemented so a request flows end to end. The "does it run?" test draws the line — if nothing new executes it was structure; if you can hit an endpoint it was skeleton.

- **In scope:** entrypoint and config/env loading, routing/handler layer, a service layer, a data-access seam, models/schemas, middleware, centralized error handling, structured logging, a health/readiness endpoint, one thin vertical slice to prove the layering, and the dev ergonomics (run/test/lint scripts, `.env.example`).
- **Out of scope:** real features, business rules, full data models, auth providers, integrations. Leave clearly marked seams (`# TODO: feature handlers here`) instead of implementing them.
- **Not this command:** whole-app framework scaffolding, top-level repo tooling (`README`, `.gitignore`, linter/formatter config), the architecture pattern *laid out as static folders*, and non-backend stacks belong to `/development:setup-app-structure`. **Dependency installation and run-verification are owned by `/development:setup-project`** — this command never installs dependencies as a step. The three compose as a pipeline: scaffold (`/development:setup-app-structure`) → running wiring (this) → install and verify (`/development:setup-project`).
- **Weight shifts by stack:** this command is heavy for a traditional backend and thin or skipped for a frontend/BaaS stack, where the backend is the BaaS — wired as schema/migrations, serverless functions, and access/security rules — not a hand-rolled server. When that is the case, this "skeleton" is that BaaS wiring, not a separate running process.

---

## How to approach this

### 1. Read the project first

Don't propose anything until you understand the environment. Inspect:

- **Convention docs** — `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `README.md`, anything in `docs/` or `spec/`. These override everything else.
- **Manifests and lockfiles** — `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`/`build.gradle`, `*.csproj`, `Gemfile`, `mix.exs`. Tells you the language, framework, and package manager (lockfile decides: `pnpm-lock.yaml`, `uv.lock`, `poetry.lock`, etc.).
- **Existing backend** — route/controller files, an existing service or repository, middleware, error handlers, the entrypoint. If a backend already exists, you are extending its conventions, not inventing new ones — and you must not overwrite working code.
- **Sibling contracts** — an already-defined data model (`design-data-model`) or API contract (`define-api-contracts`), OpenAPI/proto/SDL, migrations, env files, `docker-compose`. The skeleton must slot into these, not contradict them.
- **Monorepo signals** — `pnpm-workspace.yaml`, `nx.json`, `turbo.json`, top-level `apps/` / `services/` / `packages/`. Identify which workspace owns this backend and how its siblings are structured.

From that, classify (internally): language and framework, package manager, sync vs async runtime, persistence presence and access style, config strategy, logging and error conventions, test tooling, deployment target. If there's no backend yet, say so and note you're proposing defaults rather than mirroring conventions.

**Project precedence.** Decide whether a runnable project already exists, and act accordingly:

- **Backend already runs** — extend its conventions and layering; do not re-scaffold.
- **Project exists but has no backend** — add the skeleton into the existing layout and tooling; reuse its package manager, linter, and scripts.
- **Empty or near-empty repo** — bootstrap only a *minimal runtime* (just the framework's own generator output, enough to host the skeleton). Do not reproduce whole-app genesis (`README`, `.gitignore`, linter config, non-backend setup) — that's `/development:setup-app-structure`'s — and do not treat this as owning dependency installation. Recommend `/development:setup-app-structure` for tooling and `/development:setup-project` to install and verify.

### 2. Clarify only what you must

Ask AT MOST 3 questions, only when the answer materially changes the skeleton AND discovery didn't answer it. Common worthwhile gaps: framework choice (only if greenfield and genuinely ambiguous); whether persistence is in scope for the skeleton (and which engine/ORM) or just a stubbed seam; whether an auth boundary should exist as middleware now or later; sync vs async style if the language supports both. Skip anything the repo already answers. Never ask process questions like "ready to proceed?".

### 3. Propose the skeleton (do NOT write yet)

Before creating anything, output:

- A **tree diagram** of directories and files you intend to create, with one-line purposes for non-obvious ones.
- The **layering** you'll use and why (request flow: entrypoint → middleware → route/handler → service → data-access → model), and where the seams for future features are.
- **Cross-cutting decisions** you'd otherwise make silently: config/env loading approach, logging library, error-handling strategy, validation library, ORM/driver or none, test framework.
- **Defaults you're choosing on greenfield**, explicitly labeled as overridable.

Wait for confirmation ("looks good", "proceed", "ship it"). If the user requests changes, revise and re-confirm.

### 4. Build it

Once approved:

- Prefer the framework's official generator when one exists (`npx create-*`, `uv init` / framework CLI, `spring init`, `cargo new`, `rails new --api`, `dotnet new webapi`) over hand-rolling.
- Pin current stable versions; no pre-release unless asked.
- Implement the layers as thin, real code — not empty files. Each layer has one obvious responsibility and a clear seam where features attach.
- Wire the cross-cutting concerns for real: config loaded from env with validation, structured logging, a single centralized error handler, request validation at the boundary, graceful shutdown.
- Add a working `GET /health` (and a readiness check if there are dependencies) that returns without touching business logic.
- Add **one thin vertical slice** (e.g. an in-memory `ping` resource through handler → service → data seam) purely to prove the layering compiles and flows end to end. Mark it as a template to delete or copy.
- Add `.env.example` with every variable the skeleton reads (no secret values), and `run` / `test` / `lint` scripts in the project's idiomatic place.
- Do **not** create or overwrite `README`, `.gitignore`, or linter/formatter config — those are owned by `/development:setup-app-structure`. Wire `run`/`test`/`lint` *scripts* into whatever config already exists; don't author the config files here.
- Match the project's exact style: file naming, casing, import order, error and logging conventions, directory layout of any existing service.

### 5. Verify it (without installing dependencies)

Dependency installation and the authoritative run-verification are owned by `/development:setup-project`; this command does not install anything.

- **Make the skeleton correct by construction** — types, imports, wiring, and the vertical slice must be coherent so it boots the moment dependencies exist.
- **If dependencies are already present** (a prior scaffolder or `/development:setup-project` run installed them), opportunistically verify: boot the server, hit the health endpoint for a 200, run typecheck/build/lint and the vertical-slice test. Fix any failure.
- **If dependencies are not installed**, do not install them. State plainly that the skeleton is structurally complete but unverified, and that `/development:setup-project` is the next step to install and verify.

### 6. Report

End with a tight, scannable summary:

- The final tree (`tree -L 3` excluding deps/build dirs, or equivalent).
- The exact command to start the server and to run tests.
- Where to add the first real feature (which directory/seam), and which file the vertical-slice template lives in so they can copy or delete it.
- The next pipeline step: `/development:setup-project` to install dependencies and verify the app runs. If you only bootstrapped a minimal runtime, also point to `/development:setup-app-structure` for whole-app tooling (`README`, `.gitignore`, linter/formatter).
- Anything still needing the user's attention (env vars to fill, services to start, decisions deferred).

---

## Layering essentials

The minimum a skeleton must establish, regardless of language:

- **Entrypoint** — process bootstrap only: load config, build the app, start the server, register graceful shutdown. No business logic.
- **Config** — one typed, validated source of truth read from the environment; fails fast on missing required vars; no scattered `process.env` / `os.getenv` reads.
- **Routing / handler layer** — maps transport to calls; parses and validates input at the boundary; never contains business rules or data access.
- **Service layer** — where business logic will live; transport-agnostic and unit-testable without a server.
- **Data-access seam** — a repository/gateway interface even if backed by an in-memory stub, so persistence can be added later without touching handlers or services.
- **Models / schemas** — request/response and domain types defined once and reused; the validation boundary.
- **Middleware** — cross-cutting request concerns (request ID, logging, auth boundary placeholder, rate-limit hook) as composable units, not inlined per handler.
- **Error handling** — one centralized handler turning typed errors into consistent transport responses; no bespoke error formatting per handler.
- **Observability** — structured logging with a correlation/request ID, and a health (plus readiness if there are dependencies) endpoint.
- **Test harness** — the project's test runner wired so the vertical slice has at least one passing test that runs without external services.

---

## Quality bar

- **Match the project over generic best practices.** `CLAUDE.md` / `AGENTS.md` and any existing backend override anything in this command. A consistent skeleton beats an ideal-but-foreign one.
- **Runnable by construction.** The skeleton must boot and pass a health check the moment dependencies are installed — verify it if deps are already present, but installing them is `/development:setup-project`'s job, not this command's. A structure that can't run once installed is not a skeleton.
- **Thin but real.** Every file does its one job in real code. No empty placeholder files padding the tree; no business logic smuggled into the skeleton.
- **Seams over implementations.** Where a feature, auth provider, or database belongs, leave a clearly marked interface and a `TODO`, not a half-built guess.
- **One responsibility per layer.** Handlers don't query data; services don't parse requests; the entrypoint holds no logic. The dependency direction points inward (transport → service → data seam).
- **Idempotent and non-destructive.** Detect existing files and ask before overwriting. Re-running on a partially built backend should extend, not clobber.
- **Greenfield is not a free hand.** Propose conservative, named defaults the user can override: the framework's API-only preset, env-based typed config, structured JSON logging, a centralized error handler, an in-memory repository stub, the ecosystem's standard test runner.

---

## Common pitfalls to avoid

- Building features instead of a skeleton — real endpoints, business rules, or a full data model nobody asked for yet.
- Reproducing whole-app genesis (framework scaffold for the entire repo, `README`, `.gitignore`, linter config) that belongs to `/development:setup-app-structure`.
- Installing dependencies or owning run-verification here instead of deferring to `/development:setup-project`.
- Empty-file scaffolding: directories full of `index.ts`/`__init__.py` stubs that make the tree look done but don't run.
- A skeleton that isn't correct by construction — it won't boot even once dependencies are installed.
- Inventing a new structure beside an existing backend instead of mirroring its layering and conventions.
- Overwriting working files because discovery was skipped.
- God entrypoint: routing, config, DB setup, and logic all in `main`/`app.ts`/`server.py`.
- Handlers reaching straight into the database, so there's no seam to add a real data layer later.
- Scattered config reads and unvalidated env vars that fail deep in a request instead of at startup.
- Per-handler error formatting and ad-hoc logging instead of one centralized handler and structured logs.
- Speculative abstraction: plugin systems, generic base repositories, dependency-injection frameworks the project never asked for.
- Pinning pre-release or wildcard versions; ignoring the lockfile's package manager.
- Committing a real `.env`, or omitting `.env.example` so the next person can't run it.
