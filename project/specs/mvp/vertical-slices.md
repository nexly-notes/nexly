# NEXLY RN - MVP Vertical Slices

## Metadata

- **Source PRD:** `project/specs/mvp/prd.md`
- **Other inputs:** `project/specs/mvp/tech-specs.md`, `project/specs/mvp/design.md`
- **Slices:** 10

## Slice Map

| Slice  | Name                        | Requirements                                  | Depends on     | Demo proves                                            |
| ------ | --------------------------- | --------------------------------------------- | -------------- | ------------------------------------------------------ |
| VS-001 | Walking skeleton            | FR-009, FR-007, FR-011, FR-003, FR-012 (all partial) | -        | a signed-in user types a note and it persists per-user |
| VS-002 | Three-mode cycle            | FR-001 (full)                                 | VS-001         | `Ctrl+M` cycles Create→Edit→Study; Study blocks edits  |
| VS-003 | Save reliability            | FR-003 (complete)                             | VS-001         | no work lost beyond 30s through outage or crash        |
| VS-004 | Note library                | FR-007 (complete)                             | VS-001         | find, sort, open, and delete notes from the library    |
| VS-005 | Local autocomplete          | FR-002 (partial)                              | VS-002         | instant local term completion, Tab accepts             |
| VS-006 | AI ghost-text               | FR-002 (complete)                             | VS-005         | AI phrase suggestion <500ms or never shown             |
| VS-007 | Study tools                 | FR-005 (full), FR-006 (full)                  | VS-002, VS-005 | key terms spotted with cues, jump, hover, copy         |
| VS-008 | Runaway backstop            | FR-009 (complete)                             | VS-006, VS-007 | tripped ceiling pauses AI; local features continue     |
| VS-009 | Formatting power            | FR-004 (full), FR-011 (complete)              | VS-001         | slash menu + extended content tools in the editor      |
| VS-010 | Install & first-use         | FR-008 (full), FR-010 (full), FR-012 (complete) | VS-002, VS-004 | installable PWA, non-blocking onboarding, Default Mode |

## Slices

### VS-001 - Walking skeleton

- **Goal:** a student signs up, creates a note, types rich text, and it persists to their account.
- **Requirements:** FR-009 (partial - runaway backstop, to VS-008); FR-007 (partial - create + open only; delete/search/sort, to VS-004); FR-011 (partial - core Starter Kit set; extended set, to VS-009); FR-003 (partial - plain 30s save; retry/recovery/warning, to VS-003); FR-012 (partial - `events` table + `note_created`/`note_opened`; later events ride their slices)
- **End-to-end path:** sign-up (ToS gate) + classic editor shell -> session + note save logic -> Supabase Auth + `notes`/`events` under RLS
- **In:** email/password sign-up with beta ToS acceptance; blank-note create; classic editor (core content set); 30s save; reopen
- **Out:** all other FRs; save resilience (VS-003); library management (VS-004)
- **Demo:** 1. Sign up, accept the ToS, create a note, type a heading and list, wait for "Auto-saved". 2. Sign out and back in, reopen the note - content intact. 3. A second account cannot see it.
- **Depends on:** -

### VS-002 - Three-mode cycle

- **Goal:** one note viewed through Create, Edit, and Study, cycled with `Ctrl+M`.
- **Requirements:** FR-001 (full)
- **End-to-end path:** mode cycle control + status bar/badges -> Zustand mode state + Tiptap editable toggle -> `mode_toggled` event
- **In:** `edit` mode value + Create/Edit/Study labels; `Ctrl+M` cycle <50ms; Study read-only article shell; differentiation by layout/badge/status bar only
- **Out:** Study Tools panel content (VS-007); Default Mode preference (VS-010)
- **Demo:** 1. Open a note, press `Ctrl+M` twice - status bar reads Create, then Edit, then Study. 2. Typing in Study is blocked; one more `Ctrl+M` returns to Create and typing works.
- **Depends on:** VS-001

### VS-003 - Save reliability

- **Goal:** no saved work lost beyond a 30s window, through network loss or a crash.
- **Requirements:** FR-003 (complete)
- **End-to-end path:** amber unsaved badge + restore prompt -> save retry/backoff + rolling localStorage recovery copy -> `notes` writes
- **In:** retry with backoff; "Unsaved changes" badge; `beforeunload` warning; per-user recovery copy (cleared on sign-out) with restore prompt
- **Out:** version history/snapshots (Phase 2, excluded)
- **Demo:** 1. Cut the network and type - amber badge appears; closing the tab warns. 2. Kill the tab, reopen the note - the restore prompt offers the newer recovery copy.
- **Depends on:** VS-001

### VS-004 - Note library

- **Goal:** students manage all their notes from one searchable, sortable library.
- **Requirements:** FR-007 (complete)
- **End-to-end path:** sidebar + note grid/list (search, sort, overflow menu) -> list/query/delete logic -> `notes` table
- **In:** title search; sort by last-edited/created/title; delete with confirmation; empty state; open in Create by default
- **Out:** Default Mode open behavior (VS-010); favorites/tags/folders/archive (stretch, excluded)
- **Demo:** 1. With several notes, search by title - the grid narrows. 2. Switch sort to Title A-Z. 3. Delete a note via its overflow menu - confirm, and it is gone after reload.
- **Depends on:** VS-001

### VS-005 - Local autocomplete

- **Goal:** instant nursing-term word completion while typing, no network involved.
- **Requirements:** FR-002 (partial - AI phrase ghost-text, to VS-006)
- **End-to-end path:** ghost-text decoration in editor -> 150ms debounce + local term match (<100ms) -> seeded `nursing_terms` local cache; `suggestion_shown`/`suggestion_accepted` events
- **In:** licensed 5,000+ term dataset seeded; local word completion; Tab accepts (+ trailing space), typing/Esc dismisses; Create & Edit only
- **Out:** AI phrase prediction (VS-006)
- **Demo:** 1. In Create, type "card" and pause - a completion appears instantly; Tab accepts it. 2. Type through a suggestion - it dismisses. 3. Cycle to Study - no suggestions fire.
- **Depends on:** VS-002

### VS-006 - AI ghost-text

- **Goal:** AI phrase prediction layered on the local path - fast or invisible.
- **Requirements:** FR-002 (complete)
- **End-to-end path:** same ghost-text decoration -> Edge Function (Zod-validated, context capped to current paragraph, prompt cached) -> GPT-4.1 nano
- **In:** phrase ghost-text <500ms or suppressed; no AI payload logging; visually distinct styling
- **Out:** runaway backstop (VS-008)
- **Demo:** 1. Type a partial sentence and pause - an AI phrase suggestion appears within 500ms. 2. Throttle the network - late suggestions never render.
- **Depends on:** VS-005

### VS-007 - Study tools

- **Goal:** Study Mode turns the student's own note into an exam-relevant term list.
- **Requirements:** FR-005 (full); FR-006 (full)
- **End-to-end path:** Study Tools panel + inline term annotations -> Edge Function chunking (~3,000 words, progressive, ~12,000-word cap + notice) -> GPT-4o-mini Structured Outputs; hover via local dictionary
- **In:** terms + emphasis cues with context; click-to-jump; "Copy terms"; per-term helpful/not-helpful (`term_feedback` event); `keyterm_spotting_run` event; 200ms hover tooltip from local dictionary
- **Out:** smart summary, definition-on-demand popup (Phase 2, excluded)
- **Demo:** 1. Open a ~3,000-word note in Study - terms and cues populate the panel in under 5s. 2. Click a term to jump; hover it for the local-dictionary tooltip. 3. Copy the term list; mark one not-helpful - an `events` row appears, content-free.
- **Depends on:** VS-002, VS-005

### VS-008 - Runaway backstop

- **Goal:** a tripped per-user daily ceiling pauses AI gracefully; everything local keeps working.
- **Requirements:** FR-009 (complete)
- **End-to-end path:** non-blocking "AI assist is paused until tomorrow" notice -> Edge Function daily ceiling check -> per-user counter in Postgres
- **In:** high daily ceiling across both AI features; non-blocking notice; local autocomplete, hover, and editing unaffected
- **Out:** product quotas, token accounting, billing (Phase 2, excluded)
- **Demo:** 1. With a test ceiling, exceed it - the paused notice appears and ghost-text/spotting stop calling out. 2. Local completion, hover, and editing still work.
- **Depends on:** VS-006, VS-007

### VS-009 - Formatting power

- **Goal:** fast structuring with the `/` menu plus the extended content set.
- **Requirements:** FR-004 (full); FR-011 (complete - extended Should set)
- **End-to-end path:** slash menu + extended toolbar items -> `@tiptap/suggestion` + Highlight/TextAlign/TaskList/Image/Table extensions -> same `notes` persistence
- **In:** fuzzy keyboard-navigable `/` menu (<50ms; H1-H3, lists, divider, code, quote), Create & Edit only; highlight, alignment, checklists, image by URL, resizable tables
- **Out:** nursing templates SOAP/SBAR/Care-Plan (Phase 2, excluded)
- **Demo:** 1. Type `/`, fuzzy-match a heading, insert it by keyboard - the menu opens instantly. 2. Insert a checklist and a 3x3 table from the toolbar; in Study the `/` menu is disabled.
- **Depends on:** VS-001

### VS-010 - Install & first-use

- **Goal:** the beta shell - installable app, non-blocking onboarding, Default Mode preference.
- **Requirements:** FR-008 (full); FR-010 (full); FR-012 (complete - `app_error` + NFR-001 perf timings audited across all events)
- **End-to-end path:** install prompt + first-use tooltips + Preferences drawer -> manifest/icons/static-shell SW + first-use flags + open-mode logic -> `users.default_mode`
- **In:** PWA manifest, icons, static-shell service worker (NFR-006); dismissable mode tooltips that never block; Default Mode picker (existing notes honor it, new notes always open in Create)
- **Out:** offline editing/sync (post-beta, excluded); Modern shell + selection bubble (post-beta fast-follow, excluded)
- **Demo:** 1. Install the app from the browser - it launches standalone. 2. First note open shows dismissable mode tooltips while typing stays possible. 3. Set Default Mode to Study - existing notes open in Study; a new blank note still opens in Create.
- **Depends on:** VS-002, VS-004

## Coverage

| Requirement | Slices |
| ----------- | ------ |
| FR-001      | VS-002 |
| FR-002      | VS-005 (local path), VS-006 (AI ghost-text) |
| FR-003      | VS-001 (partial), VS-003 (complete) |
| FR-004      | VS-009 |
| FR-005      | VS-007 |
| FR-006      | VS-007 |
| FR-007      | VS-001 (partial), VS-004 (complete) |
| FR-008      | VS-010 |
| FR-009      | VS-001 (partial), VS-008 (complete) |
| FR-010      | VS-010 |
| FR-011      | VS-001 (core), VS-009 (extended) |
| FR-012      | VS-001 (schema + note events); each slice emits its own events; VS-010 (complete) |

- **Cross-cutting NFRs:** NFR-001 first testable at VS-002 (mode toggle <50ms), then each budget lands with its feature (VS-005, VS-006, VS-007, VS-009); NFR-002 at VS-003; NFR-003 at VS-001 (Auth + RLS), extended at VS-006/VS-007 (Zod, no AI payload logging); NFR-004 at VS-006 (context cap + caching), complete at VS-008; NFR-005 global - every editor slice keeps one toolbar, no extra panels; NFR-006 at VS-010.
- **Exclusions (non-goals):** Edit revision tooling (inline diff, version snapshots/history); AI smart summary; paid tiers/quotas/billing; SOAP/SBAR/Care-Plan templates; PDF/DOCX export; shorthand expansion, definition-on-demand, cloze; offline editing/sync; audio/transcription, flashcards/quizzes, collaboration, native mobile, LMS, spaced repetition, concept maps; anything that writes notes for the student. Design-only stretch (favorites, tags, folders, archive; Modern shell + selection bubble) is non-gating and not sliced.

## Open Questions

- Term-DB source + licensing (PRD open question) must be resolved before VS-005 starts - it is FR-002's primary path and also feeds VS-007 hover.
- Runaway-backstop ceiling value (PRD open question) is needed before VS-008 ships to beta.
- The repo already implements part of VS-001/VS-002 (two-mode editor shell, no persistence); VS-002 includes the `edit` value and the Lecture-to-Create label rename.
