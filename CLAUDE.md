# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

> **Current Phase:** MVP

- **What:** NEXLY RN — an AI-powered, installable PWA that helps nursing students keep pace with lectures and turn their own notes into study material.
- **Why:** Students can't keep up with the professor's pace while writing, and later can't tell which notes are exam-relevant; generalist AI tools either don't help or take over the writing.
- **Who:** Pre-licensure nursing students (ADN/BSN) primary; APRN students (MSN/DNP) secondary.
- **Scope:** 4-week MVP, validated by a 50-user, 2-week beta. Online-only, desktop-first PWA — no offline editing, audio, collaboration, or native mobile.
- **Core bet:** the three-mode workflow (Create + Edit + Study); Study Mode's AI key-term spotting is the key differentiator.
- **Important! Core principle:** assistive AI, not substitutive — AI accelerates the student's own work (catching up, spotting terms), never authors notes for them. No MVP feature writes notes _for_ the student.

**Important! Current repo state:** The specs now define **three modes (Create, Edit, Study)**, but the implemented editor still wires only **two** — `create` + `study` (`NoteMode` in `src/types/note.ts`, with the legacy "Lecture" UI label) — rendering the classic editable/Study shell (`src/components/editor/`, `src/stores/note-store.ts`) with Tiptap 3, Zustand 5 + Immer, Tailwind 4, and Vitest installed. **Edit mode is specced but not yet in code** — the `edit` value, the Create/Edit/Study label rename, and the three-way `Ctrl+M` cycle are documented in the specs but no code change has landed. Everything else in the specs (Supabase wiring, autocomplete, key-term spotting, library, auth, PWA shell) is still _target_, not present — don't assume a file, dependency, or command exists because the specs mention it.

## Specs (source of truth for scope)

- **`project/specs/mvp/prd.md`** — product requirements; `FR-`/`NFR-`/`SC-` IDs are referenced throughout.
- **`project/specs/mvp/tech-specs.md`** — architecture, data model, performance budgets, scope boundaries.
- **`project/specs/mvp/design.md`** — UX/UI spec (drives the Create/Edit/Study mode labels, brand accent, classic/modern shells).

- **`project/ui-images/<current-phase>/`** — directory of ui images of prototype. Note, some images might contain features beyond the phase scope. Always follow the phase scope no matter what.

- **Out of MVP scope:** `project/specs/phase-2/` and `project/specs/phase-3/`.
- _`project/specs/deprecated/` is superseded (older three-mode + an earlier two-mode scope) — ignore it in favor of `mvp/`._

## Commands

### App (npm)

- `npm run dev` — dev server (http://localhost:3000)
- `npm run build` — production build (main CI gate)
- `npm run lint` / `npm run lint:fix` — ESLint 9 (flat config)
- `npm run typecheck` — `tsc --noEmit` (strict)
- `npm ci` — clean install (after dependency changes)
- `npm test` — Vitest (jsdom + RTL; ProseMirror DOM shims live in `vitest.setup.ts`); `npm run test:watch` for watch mode. Playwright is still planned, not installed.
- **CI** (`.github/workflows/ci.yml`): `npm ci → lint → typecheck → build` on push/PR to `main` (Node 22); all must pass.
- **Important!** In this sandbox `npm` fails with `EROFS` unless you pass `--cache "$TMPDIR/npm-cache"`.

## Architecture

### Current code

- Next.js 16 App Router + React 19 + TypeScript strict; `@/*` → `src/*` path alias.
- FR-01 editor (currently only two of the three specced modes are wired — `create` + `study`): Tiptap 3 (`@tiptap/react` composable API, `setEditable` runtime toggle), Zustand 5 + Immer store (`src/stores/note-store.ts`), Tailwind 4 tokens in `src/app/globals.css`, Lucide icons, Vitest + RTL tests.
- Supabase JS deps (`@supabase/ssr`, `@supabase/supabase-js`) are installed but not wired up yet; env placeholders live in `.env.example`.

### Target stack (per tech-specs.md — not yet installed)

Zod validation · Supabase backend wiring (Auth + Postgres/RLS + Edge Functions) · Playwright tests.

### Three-mode workflow (the central concept)

1. **Create Mode** — fast capture; minimal UI, local-first autocomplete, auto-save every 30s.
2. **Edit Mode** — revision; the same editable shell as Create and behaves identically for now. Its revision-specific tooling (inline diff, version history) is Phase 2.
3. **Study Mode** — read-only lens; AI key-term spotting in a right-side Study Tools panel, term-hover tooltips.

- `Ctrl+M` cycles Create → Edit → Study in one keystroke (<50ms); Study blocks editing.
- **Mode differentiation:** all modes share one blue accent (`#3ba9ff`); distinguish by **layout, badges, status bar only — never by color**.
- **Canonical mode values are `create`, `edit`, `study`** (typed `NoteMode`); UI labels match 1:1 (Create / Edit / Study) — the old "Lecture" label is retired. ⚠️ The shipped code still defines only `create` | `study` (with the "Lecture" label); the `edit` value and label rename are specced but not yet implemented.

### AI (per specs)

- **Local-first autocomplete (Create & Edit):** the local 5,000+ nursing-term DB is the **primary, instant path** (word completion <100ms, no API) — _not a fallback_. GPT-4.1 nano adds phrase-prediction ghost-text when available (<500ms or suppressed). Tab accepts, typing dismisses; never fires in Study.
- **Key-term spotting (Study):** GPT-4o-mini Structured Outputs → typed term list + emphasis cues; <5s / 3,000 words.
- **Term-definition hover (Study):** local dictionary lookup only — no model call.
- **Cost control:** MVP runs **unlimited AI** for beta — no quotas. Controlled by context capping (~current paragraph), prompt caching, and a per-user runaway backstop. Notes never train models.

### Performance budgets (hard requirements)

- local autocomplete <100ms · AI ghost-text <500ms (else suppressed) · mode toggle <50ms · key-term spotting <5s/3,000 words · slash menu <50ms.
- Debounce autocomplete 150ms; offload heavy AI post-processing to a Web Worker.

## Coding Style

- Treat all external input as hostile: validate at the boundary, constrain aggressively, and never let unvalidated values reach logic or queries.
- Avoid `null`/`undefined` returns: prefer empty collections (`[]`) and option-style types.
- Follow existing project conventions even when better alternatives exist; if a standard seems wrong and the reason isn't clear, flag it and ask rather than silently working around it.
- Keep changes incremental: never mix refactoring and new features in one PR; keep cleanup commits separate from behavior-changing commits.

## Other Rules

- Prefer TDD for testing
- Workflows must include an adversarial verification stage
- Keep workflow scripts tight: less is more, and never exceed 10 agents
- Always consult the user first for any out of scope decisions, tasks, and changes.
- **Important!** Do not test Claude configuration (skills, agents, commands, workflows, output styles) — no eval runs, test agents, or baseline comparisons. Write it, review it by reading, validate through real use. Exception: hooks are code and should be tested.

## Other Relevant Context

@AGENTS.md
