---
description: Design a data model that fits the project's existing conventions and constraints
argument-hint: [feature or domain to model]
allowed-tools: Read, Grep, Glob, Bash, Write
---

# Design Data Model

Designing a data model for: **$ARGUMENTS**

If `$ARGUMENTS` is empty, ask what to model before proceeding.

---

## How to approach this

### 1. Read the project first

Don't propose anything until you understand the environment. Inspect:

- **Convention docs** — `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `README.md`, `prd.md`, `tech-spec.md` anything in `docs/ or /spec`. These override everything else.
- **Manifests** — `package.json`, `pyproject.toml`, `Gemfile`, `go.mod`, `Cargo.toml`, `pom.xml`, `*.csproj`, `mix.exs`, etc. Tells you the language and ecosystem.
- **Data-layer config** — ORM and migration config (`prisma/schema.prisma`, `drizzle.config.*`, `alembic.ini`, `ormconfig.*`, `sqlc.yaml`, `supabase/`, `convex/`, etc.), env files, `docker-compose` services.
- **Existing schema and migrations** — read at least one schema file and one recent migration. They show the conventions you must mirror.
- **Monorepo signals** — `pnpm-workspace.yaml`, `nx.json`, `turbo.json`, top-level `apps/` / `packages/` / `services/`. Identify which workspace this design belongs to.

From that, classify (internally): language, database paradigm (relational / document / key-value / graph / wide-column / time-series / vector / search / polyglot), engine, ORM and migration tooling, ID strategy, timestamp convention, soft-delete pattern, multi-tenancy approach, naming case. If there's no data layer yet, say so explicitly and call out that you're proposing defaults rather than mirroring conventions.

### 2. Clarify only what you must

Ask AT MOST 3 questions, only when the answer materially changes the design AND discovery didn't answer it. Common worthwhile gaps: expected scale, multi-tenancy isolation model, soft-delete / audit / versioning needs, consistency requirements (strong / eventual / transactional), hot access patterns. Skip anything irrelevant to the paradigm (no normalization question for a KV store). Never ask process questions like "ready to proceed?".

### 3. Produce the design

Use the project's exact syntax (Prisma if Prisma, Drizzle if Drizzle, SQLAlchemy if SQLAlchemy, raw DDL otherwise). Cover, in order:

1. **Restated understanding** — what you're modeling, the paradigm and engine, key assumptions. 2-3 sentences.
2. **Entities / collections / nodes** — bullet list, one line per item describing its purpose.
3. **Schema** — full detail: fields with types, nullability, defaults; primary keys; foreign keys with on-delete behavior; unique and check constraints; indexes with explicit reasoning ("supports list-by-user in §6.2").
4. **Diagram** — Mermaid `erDiagram` for relational or document-with-references; `flowchart LR` for graph; concrete row / key / document examples for KV, time-series, vector, search.
5. **Design decisions** — justify the non-obvious choices: normalization or embedding, partition key, ID strategy, soft-delete approach, timestamp / audit strategy, enum strategy, consistency model, multi-tenancy isolation.
6. **Access patterns** — top 3-5 expected operations and how the schema serves each. Name the indexes or keys each relies on. For wide-column and KV, this section is non-negotiable — a bad partition key or key scheme is the #1 failure mode.
7. **Scale and evolution** — unbounded-growth tables (with partitioning / archiving / TTL plan), hot row / key / partition risks, read scaling, migration-friendliness, backup considerations.
8. **Assumptions and open questions** — every load-bearing assumption you made; what would change if any is wrong.

### 4. Offer scaffolding (do NOT write files yet)

Once the design is reviewed, offer numbered options that match the detected tooling — e.g., "add to `prisma/schema.prisma` and generate a migration", "create Alembic migration in `alembic/versions/`", "generate Mongoose schema in `src/models/`", "raw SQL migration with the project's timestamp pattern". Skip options for tools that aren't present. Wait for the user's pick. When writing, mirror the project's exact style: indentation, quotes, import order, file naming, casing, header comments.

---

## Paradigm essentials

The minimum each design must address:

- **Relational** — normalization level, FK on-delete behavior, indexes justified by access patterns.
- **Document** — embed-vs-reference decisions with reasoning; compound / partial / TTL indexes; validation rules.
- **Key-value** — concrete key naming scheme (`order:{tenant}:{id}`), value shape, TTLs, secondary indexes if supported.
- **Graph** — node labels, relationship types with direction and properties, indexes on lookup properties.
- **Wide-column** (Cassandra, Scylla, DynamoDB) — partition key justified against access patterns, sort / clustering key, hot-partition and partition-size analysis.
- **Time-series** — tags vs fields distinction, timestamp granularity, retention policy, downsampling.
- **Vector** — embedding dimension and source model, metadata schema for filtering, index type (HNSW / IVF / flat), distance metric.
- **Search** — mappings / analyzers per field, refresh strategy.

---

## Quality bar

- **Match the project over generic best practices.** `CLAUDE.md` / `AGENTS.md` override anything in this command.
- **Never carry internal fields into the API layer.** Password hashes, payment provider IDs, fraud signals, raw audit columns, soft-delete timestamps — mark them internal in the schema notes; the API serializer must strip them.
- **Prefer additive migrations.** Flag every destructive change (drop, rename, type narrowing, NOT NULL added to an existing column) with a rollback plan. For online migrations, propose expand → backfill → contract phases explicitly.
- **Surface contradictions.** If discovery shows two ORMs configured, two databases in use, or conflicting conventions, raise it before designing.
- **Be explicit about polyglot choices.** If the project has multiple stores, name which one this design targets and why.
- **Greenfield is not a free hand.** Propose conservative defaults (Postgres, UUID v7 or ULID, snake_case, UTC timestamps, soft-delete only if requested) and label them as defaults the user can override.

---

## Common pitfalls to avoid

- Proposing features the engine doesn't support: CHECK constraints on MySQL < 8.0.16, transactions across DynamoDB partitions beyond the 100-item `TransactWriteItems` limit, foreign keys in sharded setups (Vitess and similar), JOINs in document or KV stores.
- Designing for "future flexibility" no one asked for: premature polymorphism, EAV tables, unused JSON catch-all columns.
- Storing derived values that can be computed at read time, then watching them drift.
- Indexes added "just in case" — every index has a write cost; justify each one.
- Soft-delete columns the API forgets to filter on, a frequent source of "deleted data still visible" bugs.
- Auto-increment IDs exposed to clients — couples storage to API and breaks the moment you shard or migrate.
