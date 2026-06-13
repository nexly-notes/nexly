# Handoff: VS-001 Walking Skeleton

**Date:** 2026-06-12 · **Task:** A student signs up (ToS gate), creates a note, types rich text, and it persists per-user to Supabase with 30s auto-save · **Status:** Ready for implementation · **Difficulty:** Large (size `l`)

- *Why Large:* widest slice of the MVP — touches every layer at once (env/Zod, Supabase clients, SQL schema + RLS, middleware, auth UI, data layer, new routes, store rework, autosave), ~15-20 new files plus an external service dependency (live Supabase project, CLI link/push). No single step is hard — all standard, well-documented patterns — but integration breadth and the live-demo verification bar push it above Medium. Not XL: no novel algorithms, no data migration, performance budgets untouched.

---

## 1. Goals

> Why this task exists and what done looks like. From the interview, not inferred.

- Deliver the end-to-end spine every other slice builds on: Supabase Auth gating the app, a `notes` row owned by the signed-in user, the existing Tiptap editor saving into it every 30s, and an `events` table recording `note_created` / `note_opened`
- Selected as the next ready vertical slice from `project/specs/mvp/vertical-slices.md:26-34` (VS-001 has no dependencies; user confirmed the pick)

**Success criteria (the slice demo, `project/specs/mvp/vertical-slices.md:33`):**

1. Sign up, accept the ToS, create a note, type a heading and list, wait for "Auto-saved"
2. Sign out and back in, reopen the note — content intact
3. A second account cannot see the first account's note

---

## 2. Context

> What an implementer must know before touching code. From exploration and interview; no invented facts.

**What exists (working, tested):**

- Two-mode editor shell is complete and tested: `src/components/editor/note-editor.tsx` mounts Tiptap 3 (StarterKit + Placeholder, `immediatelyRender: false`), syncs editability pre-paint via `useClientLayoutEffect` + `editor.setEditable(isWriteMode)`, and handles `Ctrl+M` at window scope
- Mode state lives in `src/stores/note-store.ts` (Zustand 5 + Immer): `{ mode, setMode, toggleMode }` — **mode only; no content, title, user, or save state**
- `src/types/note.ts:2` defines `NoteMode = "create" | "study"` with `create → "Lecture"` label — the `edit` value and Create/Edit/Study rename belong to **VS-002**, not this slice (`project/specs/mvp/vertical-slices.md:150`); existing tests assert `"Lecture Mode"` (`src/components/editor/note-editor.test.tsx:32`) — do not rename
- `src/app/page.tsx` renders `<NoteEditor />` directly with no note identity, no auth gate; `src/components/editor/editor-header.tsx` holds the title in local `useState`, never persisted
- `src/components/editor/status-bar.tsx` computes word/char counts from `useTiptapState`; shows mode label, **no save indicator yet**
- 11 passing tests: `src/stores/note-store.test.ts` (4), `src/components/editor/note-editor.test.tsx` (7); ProseMirror DOM shims in `vitest.setup.ts:5-33`; vitest config: jsdom, globals, `src/**/*.test.{ts,tsx}`

**What does not exist (verified absences):**

- No Supabase client code anywhere (`src/lib/` does not exist), no middleware, no auth routes/forms, no `/api` routes, no server actions
- No `supabase/` directory, no migrations, no schema, no RLS policies in the repo
- No persistence of any kind — no localStorage, no save logic; reload loses everything
- Zod is not installed
- `@supabase/ssr@^0.10.3` and `@supabase/supabase-js@^2.105.4` are installed but unused (`package.json`)
- `.env.local` already contains live credentials for a provisioned Supabase project (URL, publishable key, secret key); `.env.example` defines `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `OPENAI_API_KEY`, `ALLOWED_ORIGIN`

**Spec requirements bounding this slice:**

- Data model (`project/specs/mvp/tech-specs.md:97-138`): `notes` (id uuid, user_id uuid, title text, content jsonb — Tiptap doc, word_count int, created_at, updated_at); `events` (id uuid, user_id uuid, type text, value int nullable, created_at) — events are **metadata only, never note content**; RLS per-user isolation, events insert-own
- FR-003 partial (`project/specs/mvp/prd.md`): plain 30s save only — retry/backoff, amber unsaved badge, `beforeunload` warning, and localStorage recovery copy are **VS-003**
- FR-009 partial: sign-up requires beta ToS acceptance — didactic lecture notes only, PHI prohibited (`project/specs/mvp/design.md:357-361`); runaway backstop is VS-008
- FR-012 partial: `events` schema + `note_created` / `note_opened` only; later events ride their slices
- Status bar shows "Auto-saved" when clean (`project/specs/mvp/design.md:227-234`)
- Design invariant: single blue accent `#3ba9ff`; modes differ by layout/badge/status bar only, never color (`src/app/globals.css:40-41`)

**Conventions to follow:**

- TypeScript strict; `@/*` → `src/*` alias; kebab-case files, PascalCase components, camelCase functions, `is/has/can` booleans
- Zustand + Immer idiom as in `src/stores/note-store.ts`; tests use RTL with `data-testid` hooks and `waitFor` for async editor mount
- Validate at the boundary, treat external input as hostile; prefer empty collections over null returns (CLAUDE.md)
- npm in this sandbox needs `--cache "$TMPDIR/npm-cache"` (EROFS otherwise)
- **Important!** Read `node_modules/next/dist/docs/` before Next.js work (AGENTS.md); use the supabase skill for Supabase work

**Key files:**

| File                                        | Why it matters                                                       |
| :------------------------------------------ | :------------------------------------------------------------------- |
| `src/app/page.tsx`                          | Becomes the signed-in landing (bare note list); currently bare editor |
| `src/components/editor/note-editor.tsx`     | Editor shell to bind to a real note + autosave                       |
| `src/components/editor/editor-header.tsx`   | Title is local-only `useState`; must persist with the note           |
| `src/components/editor/status-bar.tsx`      | Gains the "Auto-saved" indicator                                     |
| `src/stores/note-store.ts`                  | Extends with note identity/content/save status                       |
| `src/types/note.ts`                         | Gains `Note` row type; do NOT touch `NoteMode` (VS-002)              |
| `.env.example` / `.env.local`               | Env contract; live project credentials already present               |
| `project/specs/mvp/tech-specs.md`           | Data model, RLS, save design — source of truth                       |
| `project/specs/mvp/vertical-slices.md:26-34`| VS-001 scope contract and demo script                                |

---

## 3. Decisions

> Made during the interview. Binding unless the user reopens them.

| Decision               | Choice                                                                 | Why                                                                                                    |
| :--------------------- | :--------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------- |
| Slice pick             | VS-001 Walking skeleton                                                 | Only slice with all dependencies met; baseline (two-mode shell, zero persistence) verified in code      |
| Reopen path            | `/notes/[id]` editor route + bare unstyled note list on signed-in landing with a New Note button | Satisfies the reopen demo without building VS-004; routes survive when VS-004 replaces the list         |
| Data access            | Browser supabase-js + RLS for notes/events CRUD; `@supabase/ssr` server client only for auth/session (middleware, server components) | Least moving parts; RLS is the security boundary; matches tech-specs (Edge Functions are for AI only)   |
| Schema management      | Supabase CLI migrations committed under `supabase/migrations/`          | Reviewable, reproducible for every later slice                                                          |
| Email confirmation     | Disabled for beta — sign-up grants an instant session                   | Zero friction for the 2-week beta; can be enabled later without form changes                            |
| Zod                    | Add now: `src/lib/env.ts` Zod env loader + sign-up form validation      | Matches tech-specs and "validate at the boundary" from day one (backlog story #11)                      |
| Done bar               | TDD (Vitest/RTL, Supabase mocked) + manual 3-step demo against the live project with two accounts; CI green | CLAUDE.md prefers TDD; RLS isolation can only be proven against the real project                         |
| DB apply               | Implementing agent installs Supabase CLI, links the provisioned project, pushes migrations itself | Enables end-to-end demo verification; user provides an access token if linking requires it              |

---

## 4. Implementation Plan

> Ordered, concrete steps. Each step names the files and the change. TDD: write the failing test first wherever a step is unit-testable.

1. **Env loader** — `npm install zod --cache "$TMPDIR/npm-cache"`; create `src/lib/env.ts` exporting Zod-validated env access (public vars parsed client-safe; `SUPABASE_SECRET_KEY` server-only). Test: invalid/missing env throws with a clear message
2. **Supabase clients** — `src/lib/supabase/client.ts` (browser client via `createBrowserClient` from `@supabase/ssr`) and `src/lib/supabase/server.ts` (server client with cookie handling). Follow current `@supabase/ssr` docs (use the supabase skill) — `getAll`/`setAll` cookie pattern, never the deprecated `get/set/remove`
3. **Schema migrations** — install/link Supabase CLI; author `supabase/migrations/<ts>_walking_skeleton.sql`: `notes` and `events` tables per tech-specs columns; RLS enabled; policies: notes full CRUD `using (auth.uid() = user_id)`, events insert-own only; `updated_at` trigger. Push to the live project. Disable email confirmation in Auth settings
4. **Auth middleware** — `src/middleware.ts` using the `@supabase/ssr` session-refresh pattern; unauthenticated users redirected to `/login`, authenticated users away from `/login`/`/signup`
5. **Auth UI** — `src/app/(auth)/signup/page.tsx` and `src/app/(auth)/login/page.tsx` with email/password forms (Zod-validated); sign-up includes a required ToS checkbox ("beta — didactic lecture notes only; no patient-identifying information (PHI)") that blocks submit until checked; sign-out control in the editor header or landing. Style with existing Tailwind tokens, single blue accent
6. **Note types + data layer** — add `Note` type to `src/types/note.ts` (matching the table row; content as Tiptap JSON); `src/lib/notes.ts` with `createNote()`, `getNote(id)`, `listNotes()`, `saveNote(id, {title, content, word_count})` using the browser client; `src/lib/events.ts` with `logEvent(type, value?)` (fire-and-forget, swallow failures — instrumentation must never break editing). `createNote` logs `note_created`; opening logs `note_opened`. Tests with the Supabase client mocked
7. **Routes** — `/notes/[id]/page.tsx` loads the note server-side (server client), 404s on missing/foreign (RLS returns empty), renders `<NoteEditor>` seeded with the note; rework `src/app/page.tsx` into the signed-in landing: bare list of the user's notes (title + updated_at, unstyled is fine) + New Note button that calls `createNote` and redirects to `/notes/[id]`
8. **Bind editor to note + autosave** — extend `src/stores/note-store.ts` with note identity, title, and save status (`saved | saving | unsaved`); wire `editor-header.tsx` title into the store; add a 30s interval autosave (e.g. `src/hooks/use-autosave.ts`) that serializes `editor.getJSON()`, computes word count, and calls `saveNote` — plain save only, no retry/recovery (VS-003); save on unmount too. Show "Auto-saved" in `status-bar.tsx` when clean per design.md. Keep existing mode behavior untouched; existing 11 tests must stay green
9. **Verify** — full suite: `npm run lint`, `npm run typecheck`, `npm run build`, `npm test`; then manually walk the 3-step demo against the live project with two accounts (second account must not see the first's note — RLS proof)

**Testing approach:** TDD with Vitest + RTL (Supabase mocked in unit/component tests) per interview; plus the manual live demo as the final gate.

---

## 5. Scope

**In scope:** email/password sign-up with ToS gate (instant session); login/sign-out; middleware gating; `notes` + `events` tables with RLS via committed CLI migrations; blank-note create; `/notes/[id]` route + bare landing list; title + content (Tiptap JSON) + word_count persistence; plain 30s autosave with "Auto-saved" indicator; `note_created` / `note_opened` events; Zod env loader + form validation.

**Out of scope:** save retry/backoff, unsaved badge, `beforeunload` warning, localStorage recovery (VS-003); search/sort/delete and the real library UI (VS-004); `edit` mode value, three-way `Ctrl+M`, Lecture→Create label rename (VS-002 — leave `NoteMode` and the "Lecture" label alone); autocomplete/AI (VS-005+); slash menu/extended formatting (VS-009); PWA/onboarding/Default Mode (VS-010); email confirmation flow; Playwright; version history (Phase 2).

---

## 6. Acceptance Criteria

- [ ] Sign-up requires the ToS checkbox and grants an immediate session; login and sign-out work
- [ ] Unauthenticated access to `/` and `/notes/[id]` redirects to login
- [ ] New Note creates a `notes` row and opens `/notes/[id]`; a `note_created` event row is written; opening writes `note_opened`
- [ ] Typing a heading and a list, then waiting ≤30s, shows "Auto-saved" in the status bar and the content is in Supabase as Tiptap JSON with `word_count` and `updated_at` set
- [ ] After sign-out and sign-in, the note appears in the landing list and reopens with content intact
- [ ] A second account sees neither the note (list, direct URL → 404/empty) nor the first user's events — verified live against the real project
- [ ] `events` rows contain metadata only — no note content
- [ ] Existing two-mode editor behavior and all 11 existing tests unchanged and green; new code TDD-covered
- [ ] Migrations committed under `supabase/migrations/`; `npm run lint`, `typecheck`, `build`, `test` all pass
- [ ] No secrets in client bundles or commits; `.env.local` stays untracked

---

## 7. Risks and Open Questions

| Risk / question                                                                 | Impact                                          | Mitigation                                                                                                  |
| :------------------------------------------------------------------------------ | :---------------------------------------------- | :----------------------------------------------------------------------------------------------------------- |
| Supabase CLI link/push may need an access token or network the sandbox blocks    | Blocks step 3 and the live demo                 | Fall back to applying the committed SQL via the dashboard SQL editor (user-assisted); migrations stay in repo |
| `@supabase/ssr` cookie API drifts across versions (0.10.x)                       | Subtle session bugs                             | Read current docs via the supabase skill / context7 before writing clients and middleware                     |
| VS-002 will touch the same store/types/tests (edit mode, label rename)           | Merge collisions if VS-001 refactors `NoteMode` | VS-001 adds state alongside `mode` and never edits `NoteMode` or mode labels/tests                             |
| `.env.local` holds live credentials in the working tree                          | Secret leakage if ever committed                | Verify it is gitignored; never echo values; consider rotating keys before public beta                          |
| Autosave writing full Tiptap JSON every 30s for large notes                      | Minor write amplification                       | Acceptable for MVP (spec'd design); skip save when content unchanged since last save                          |
| ToS copy is one checkbox line — no legal text exists yet                         | Beta-blocking only if legal review is required  | Ship the spec's one-liner (didactic only, no PHI); flag for the user before the 50-user beta                   |

