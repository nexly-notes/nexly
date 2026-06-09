# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

> **Current Phase:** MVP

- **What:** NEXLY RN — an AI-powered, installable PWA that helps nursing students keep pace with lectures and turn their own notes into study material.
- **Why:** Students can't keep up with the professor's pace while writing, and later can't tell which notes are exam-relevant; generalist AI tools either don't help or take over the writing.
- **Who:** Pre-licensure nursing students (ADN/BSN) primary; APRN students (MSN/DNP) secondary.
- **Scope:** 4-week MVP, validated by a 50-user, 2-week beta. Online-only, desktop-first PWA — no offline editing, audio, collaboration, or native mobile.
- **Core bet:** the two-mode workflow (Write + Study); Study Mode's AI key-term spotting is the key differentiator.
- **Important! Core principle:** assistive AI, not substitutive — AI accelerates the student's own work (catching up, spotting terms), never authors notes for them. No MVP feature writes notes _for_ the student.

## Specs (source of truth for scope)

- **`project/specs/mvp/prd.md`** — product requirements; `FR-`/`NFR-`/`SC-` IDs are referenced throughout.
- **`project/specs/mvp/tech-specs.md`** — architecture, data model, performance budgets, scope boundaries.
- **`project/specs/mvp/design.md`** — UX/UI spec (drives the "Lecture" label, brand accent, classic/modern shells).
- **`project/roadmap.md`** — milestone sequencing (M-codes).
- **Out of MVP scope:** `project/specs/phase-2/` and `project/specs/phase-3/`.
- _`project/specs/deprecated/` is superseded (older three-mode + an earlier two-mode scope) — ignore it in favor of `mvp/`._

## Commands

- `npm run dev` — dev server
- `npm run build` — production build (main CI gate)
- `npm run lint` / `npm run lint:fix` — ESLint (flat config)
- `npm run typecheck` — `tsc --noEmit` (TS 6 strict)
- `npm test` — Vitest run (unit; jsdom + React Testing Library)
- `npm run test:watch` / `npm run test:coverage` — watch / v8 coverage
- **Single test:** `npx vitest run src/test/stores/app-store.test.ts`, or filter by name with `-t "<pattern>"`
- `npm run e2e` — Playwright E2E (run `npm run e2e:install` once first to fetch Chromium)
- `npm ci` — clean install (after dependency changes)
- **CI** (`.github/workflows/ci.yml`): `npm ci → lint → typecheck → test → build` on push/PR to `main` (Node 22); all must pass.
- **Important!** In this sandbox `npm` fails with `EROFS` unless you pass `--cache "$TMPDIR/npm-cache"`.

## Architecture

### Tech stack

Per `tech-specs.md`: Next.js 16 App Router + React 19 + TS 6 strict · Tiptap 3.23 editor · Zustand 5 + Immer state · Tailwind 4 · Zod 4 validation · Supabase backend · Vitest + Playwright tests.

### Repo layout

- **`src/app/(auth)/`** — unauthenticated routes: `login`, `signup`, `auth/callback`.
- **`src/app/(app)/`** — authenticated shell: `library`, `notes/[noteId]`, `notes/new`, `onboarding`.
- **`src/middleware.ts`** + `src/lib/supabase/middleware.ts` gate auth on every route; `src/app/api/health/` is the health route.
- **`src/components/`** — by domain: `editor/`, `modes/`, `study/`, `library/`, `onboarding/`, `layout/`, `providers/`, `ui/` (Radix-based primitives).
- **`src/lib/`** — `supabase/` (client/server/middleware), `ai/` (per-feature clients), `dictionary/` (local nursing-term lookup), `env.ts`, `constants.ts`.
- **`src/stores/app-store.ts`** — the single Zustand store. **`src/hooks/`** — `use-mode`, `use-autosave`, `use-debounce`. **`src/types/`** — domain (`note.ts`) + DB (`database.ts`) types.
- **`supabase/`** — `migrations/` (schema + RLS), `functions/` (Deno Edge Functions; `_shared/cors.ts` handles preflight), `seed.sql`.

### Two-mode workflow (the central concept)

1. **Write Mode** (labeled **"Lecture"** in the UI) — fast capture _and_ revision; minimal UI, local-first autocomplete, auto-save every 30s.
2. **Study Mode** — read-only lens; AI key-term spotting in a right-side Study Tools panel, term-hover tooltips.

- Toggle is a one-keystroke runtime switch (`Ctrl+M`, <50ms); Study blocks editing.
- **Mode differentiation:** both modes share one blue accent (`#3ba9ff`); distinguish by **layout, badges, status bar only — never by color**.
- **Canonical mode value is `create`** (typed `NoteMode`); "Lecture" is only the UI label (`MODE_LABELS` in `src/lib/constants.ts`).

### State

- One Zustand 5 + Immer store (`src/stores/app-store.ts`): `activeMode`, `noteMeta`, `aiQueue`, `preferences` (incl. `editorShell` classic/modern), `theme`.
- **Important!** This is a scaffold: feature logic is intentionally stubbed — components/functions carry `TODO(mvp, FR-xx)` markers (~50 of them) where real behavior goes.

### Backend (Supabase only)

- **Auth** gates all access; JWT sessions; Postgres RLS for per-user isolation.
- **Postgres** (`supabase/migrations/`): MVP tables are `users`, `notes`, `nursing_terms`. _(The initial migration also creates `note_versions` + `usage_quotas` — Phase 2; see scope note below.)_
- **Edge Functions** (Deno, `supabase/functions/`): AI orchestration + per-user runaway backstop; CORS restricted.
- **Env** is validated lazily via Zod in `src/lib/env.ts` (parsed _inside_ accessors so `next build` stays green without secrets). Vars (`.env.local`, see `.env.example`): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `OPENAI_API_KEY`, `ALLOWED_ORIGIN`.

### AI

- **Local-first autocomplete (Write):** the local 5,000+ nursing-term DB is the **primary, instant path** (word completion <100ms, no API) — _not a fallback_. GPT-4.1 nano adds phrase-prediction ghost-text when available (<500ms or suppressed). Tab accepts, typing dismisses; never fires in Study.
- **Key-term spotting (Study):** GPT-4o-mini Structured Outputs → typed term list + emphasis cues; <5s / 3,000 words.
- **Term-definition hover (Study):** local dictionary lookup only — no model call.
- **Cost control:** MVP runs **unlimited AI** for beta — no quotas. Controlled by context capping (~current paragraph), prompt caching, and the per-user runaway backstop. Notes never train models.

### Performance budgets (hard requirements)

- local autocomplete <100ms · AI ghost-text <500ms (else suppressed) · mode toggle <50ms · key-term spotting <5s/3,000 words · slash menu <50ms.
- Debounce autocomplete 150ms; offload heavy AI post-processing to a Web Worker.

## Important! The scaffold is wider — and older — than the MVP

`src/` and `supabase/` were scaffolded against an **earlier, broader scope**. The specs (above), not the scaffold, define MVP scope. **Don't build these out for the MVP**, and don't assume their presence means they're in scope:

| Present in code                                                                                                | Status                                                                                   |
| -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `edit` value in `NoteMode`; `components/edit/`; `compute-diff.ts`, `comparison-dialog.tsx`, `diff-match-patch` | Edit Mode + inline diff → **Phase 2**                                                    |
| `note_versions` table, `NoteVersion`, `MAX_NOTE_VERSIONS`                                                      | Version history → **Phase 2**                                                            |
| `usage_quotas` table, `user_tier`/`UserTier`, `QUOTA_CAPS`, `_shared/quota.ts`                                 | Tiers/quotas → **Phase 2** (MVP = unlimited)                                             |
| `study/smart-summary.tsx`, `ai/summary-client.ts`, `functions/smart-summary/`                                  | AI smart summary → **Phase 2**                                                           |
| `functions/export/`                                                                                            | PDF/DOCX export → **Phase 2**                                                            |
| `note_mode` column + enum, `Note.mode`; `is_favorite`, `NoteTag`                                               | MVP mode is a runtime lens (not persisted); tags/favorites are not in the MVP data model |

- **Local DB is primary, not a fallback** — older code comments calling it a "quota-exhausted fallback" reflect the superseded scope.
- The slash menu ships **formatting primitives only** (H1–H3, lists, divider, code, quote); nursing templates (SOAP/SBAR/Care Plan) are Phase 2.
- **`FR-` numbers in `TODO(mvp, ...)` markers track the older PRD numbering** and don't line up with `project/specs/mvp/prd.md` (e.g. auth is `FR-10` in markers but `FR-09` in the current PRD) — cross-check against the spec, not the marker.
