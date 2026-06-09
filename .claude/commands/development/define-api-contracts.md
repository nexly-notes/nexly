---
description: Define API contracts that fit the project's existing protocol, conventions, and constraints
argument-hint: [feature, surface, or service to contract]
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
---

# Define API Contracts

Defining the API contract for: **$ARGUMENTS**

If `$ARGUMENTS` is empty, ask what surface to contract before proceeding.

A contract here means the agreed boundary between a producer and its consumers: operations, request and response shapes, error model, auth, and the compatibility rules that govern change. It is protocol-agnostic — REST, GraphQL, gRPC, RPC/tRPC, async/event, or realtime.

---

## How to approach this

### 1. Read the project first

Don't propose anything until you understand the environment. Inspect:

- **Convention docs** — `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `README.md`, `prd.md`, `tech-spec.md`, anything in `docs/` or `spec/`. These override everything else.
- **Manifests** — `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `*.csproj`, `Gemfile`, `mix.exs`, etc. Tells you the language and ecosystem.
- **Existing API surface and tooling** — route files, controllers, resolvers, `.proto` files, OpenAPI/Swagger or AsyncAPI specs, GraphQL SDL, tRPC routers, JSON Schema, gateway/edge config, generated client SDKs. Read at least one existing operation end to end and one error path; they show the conventions you must mirror.
- **Cross-cutting plumbing** — auth middleware, validation layer (zod, pydantic, class-validator, protobuf), error handlers, serializers/DTO mappers, pagination helpers, API versioning setup.
- **Monorepo signals** — `pnpm-workspace.yaml`, `nx.json`, `turbo.json`, top-level `apps/` / `packages/` / `services/`. Identify which workspace owns this surface and which consumes it.

From that, classify (internally): protocol/style (REST, GraphQL, gRPC, RPC/tRPC/JSON-RPC, async/event, realtime, or polyglot), serialization format, transport, auth scheme, error model, versioning strategy, pagination style, naming/casing, validation tooling. If there's no API layer yet, say so explicitly and call out that you're proposing defaults rather than mirroring conventions.

### 2. Clarify only what you must

Ask AT MOST 3 questions, only when the answer materially changes the contract AND discovery didn't answer it. Common worthwhile gaps: who the consumers are (first-party UI, third-party, service-to-service) and their compatibility expectations; auth model and per-operation authorization; consistency/idempotency needs for mutations; expected list sizes and access patterns (drives pagination); whether this extends an existing versioned contract. Skip anything irrelevant to the protocol (no HTTP-status question for gRPC). Never ask process questions like "ready to proceed?".

### 3. Produce the contract

Use the project's exact contract syntax (OpenAPI if OpenAPI, GraphQL SDL if GraphQL, `.proto` if gRPC, tRPC router types if tRPC, AsyncAPI if event-driven, raw typed endpoint tables otherwise). Cover, in order:

1. **Restated understanding** — what surface you're contracting, the protocol/style and transport, who the consumers are, key assumptions. 2-3 sentences.
2. **Operations** — bullet list of every resource/operation/message/procedure, one line per item describing its purpose and the auth/scope it requires.
3. **Operation detail** — full detail per operation: identifier (verb + path / query/mutation name / rpc / topic), purpose, authorization required, request shape (path & query params, headers, body) with types/nullability/defaults/constraints, success response shape and status/result code, error responses, idempotency semantics, and pagination/filtering/sorting where the operation returns a collection.
4. **Shared schemas** — DTOs/types reused across operations, enums and their allowed values, ID and timestamp formats. Define each once; reference it from operations.
5. **Cross-cutting conventions** — auth scheme and where credentials go, the single error envelope/model, versioning strategy and placement, pagination strategy, content negotiation, naming/casing, date/time and money representation, nullability discipline, rate-limit and request-size posture.
6. **Examples** — at least one concrete request + success response and one error response per representative operation, with realistic values.
7. **Compatibility and versioning** — which changes are additive vs breaking for this surface, deprecation policy, how a consumer detects and migrates across versions.
8. **Assumptions and open questions** — every load-bearing assumption; what would change if any is wrong.

### 4. Offer scaffolding (do NOT write files yet)

Once the contract is reviewed, offer numbered options that match the detected tooling — e.g., "add paths to the existing `openapi.yaml` and regenerate types", "extend the GraphQL SDL and update resolvers' type signatures", "add messages/rpcs to the `.proto` and note the codegen command", "add a tRPC router with zod input/output schemas", "add an AsyncAPI channel", or "emit a typed endpoint table + request/response types in the project's validation library". Skip options for tooling that isn't present. Wait for the user's pick. When writing, mirror the project's exact style: file layout, indentation, quoting, casing, schema/component naming, and how existing operations are organized.

---

## Protocol essentials

The minimum each contract must address:

- **REST / HTTP** — resource-oriented paths (no verbs in paths), correct method semantics and status codes, idempotency for `PUT`/`DELETE` (and `POST` via idempotency key where it creates), one consistent error body (default RFC 9457 `problem+json` unless the project differs), pagination style, content types, `ETag`/conditional requests if mutation conflicts matter.
- **GraphQL** — types, queries/mutations/subscriptions, deliberate nullability per field (over-nulling weakens guarantees; over-non-nulling makes one failure poison the response), pagination convention (Relay connections vs offset — match the project), error strategy (top-level `errors` vs typed result unions), and a note on resolver fan-out/N+1 for list fields.
- **gRPC / protobuf** — `service` and `rpc` definitions, message field numbers with reserved ranges for removed fields, streaming kind per rpc (unary/server/client/bidi), proto3 field presence/optionality, package name and versioning, and the error model (status codes + `google.rpc.Status` details).
- **RPC / tRPC / JSON-RPC** — procedure namespacing and naming, input and output schemas (the validation library is the contract), error code taxonomy, and transport/batching behavior.
- **Async / event / messaging** — channel/topic/queue naming, message envelope and payload schema, schema-registry and compatibility mode (backward/forward/full), delivery semantics (at-least-once is the default assumption), ordering and partition/routing key, idempotency/dedup key for consumers, retry and dead-letter policy.
- **Realtime (WebSocket / SSE)** — connection lifecycle and auth at connect time, the set of message types and their framing, reconnection/resume semantics (event IDs, last-known cursor), heartbeat, and backpressure/rate handling.

---

## Quality bar

- **Match the project over generic best practices.** `CLAUDE.md` / `AGENTS.md` and existing operations override anything in this command. A consistent contract beats an ideal-but-foreign one.
- **The contract is the boundary, not the storage model.** Never expose internal/derived/storage fields — password hashes, provider IDs, soft-delete columns, raw audit fields, internal enums. Decide field visibility explicitly; the serializer enforces it.
- **Backward compatibility by default.** Additive changes only unless a version bump is on the table. Flag every breaking change (renamed/removed field, narrowed type, optional → required, changed enum value or status code, tightened validation) with a deprecation and migration path.
- **One error model, everywhere.** Every operation reports failure through the same shape and the same code taxonomy. Bespoke per-endpoint error formats are a defect.
- **Everything typed and bounded.** Every field has a type, explicit nullability, and a format/constraint where it matters. No untyped blobs, no `any`, no free-form JSON without a schema. Every collection response is paginated and bounded.
- **Authorization is per-operation.** State the required authentication and the authorization rule for each operation, not just a global "auth required" note.
- **State idempotency and retry semantics** for every mutating or async operation — what a duplicate delivery or retried request does.
- **Greenfield is not a free hand.** Propose conservative, named defaults the user can override: REST + JSON, RFC 9457 errors, cursor pagination, semver with URL or header versioning, UTC ISO-8601 timestamps, OAuth2/JWT bearer auth.

---

## Common pitfalls to avoid

- Verbs in REST paths (`/getUser`, `/createOrder`) or doing everything over `POST`; wrong status codes (200 with an error body, 200 instead of 201/204, 500 for client mistakes).
- A different error shape per endpoint, or success-shaped bodies that hide failures.
- Unbounded list endpoints with no pagination, no max page size, and no default ordering — a latent outage.
- Leaking persistence into the contract: DB column names, internal enum values, soft-delete timestamps, IDs that couple clients to storage, PII no consumer asked for.
- Silent breaking changes — renaming a field, narrowing a type, making an optional field required, removing an enum value, or changing a default — shipped without a version or deprecation.
- Over-specifying speculative operations, parameters, or "flexible" catch-all payloads nobody requested.
- GraphQL: blanket non-null (one resolver failure nulls the whole response) or blanket nullable (no guarantees for consumers); offset pagination where the project uses connections.
- protobuf: renumbering or reusing field tags, not reserving removed tags/names, changing a field's type in place.
- Async: assuming exactly-once delivery, omitting an idempotency/dedup key, or leaving schema-compatibility mode and dead-letter behavior unspecified.
- Ambiguous primitives: timestamps without timezone or format, money as a float, enums as free strings, IDs without a stated format.
- No stated request-size limits, rate limits, or auth scope per operation.
