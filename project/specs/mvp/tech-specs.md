# NEXLY RN – Technical Specifications

## 1. System Overview

- **Architecture:** Installable desktop/web Progressive Web App (PWA), online-only; no native runtime and no offline editing in MVP
- **Primary Stack:** Next.js 16.2.6 + React 19.2.6 + TypeScript 6 + Tailwind 4.3 + Tiptap 3.23
- **Backend:** Supabase (Auth, Postgres, Edge Functions, Storage)
- **Product Core:** Three-mode note workflow — Create (capture) and Edit (revision) are both editable and behave identically for now, plus read-only Study (key-term spotting)
- **Important! Core principle:** assistive AI, not substitutive — AI accelerates the student's own work, never does it for them
- **Reference:** Aligns with `prd.md` (4-Week MVP). Post-MVP scope is tracked in `phase-2/prd.md` / `phase-3/prd.md`

## 2. Frontend Architecture

**Core Framework**

- Next.js 16.2.6 (App Router)
- React 19.2.6 + React DOM 19.2.6
- TypeScript 6 strict mode
- Installable PWA: manifest, icons, static-shell service worker (*offline note editing/sync deferred post-beta*)

**UI Layer**

- Custom component library styled with Tailwind CSS 4.3
- `Inter` typeface; `Lucide` icon set
- Single blue brand accent shared across all modes; modes differentiated by layout, badges, and status bar, not accent color
- Dark mode via CSS variables

**Rich Text Editor (Tiptap 3.23)**

- Starter Kit (FR-011 core set): headings, bold/italic/underline/strikethrough, code, lists, blockquote, dividers, links
- Extended content set (FR-011 Should-tier, net-new beyond Starter Kit): Highlight, TextAlign, TaskList/TaskItem (checklists), Image (URL insert), Table (resizable)
- Placeholder extension for empty-state hints
- Slash command menu (`@tiptap/suggestion`): formatting primitives only (H1–H3, lists, divider, code, quote) — *nursing templates deferred to Phase 2*
- Read-only enforced in Study Mode (editable in Create & Edit)
- Autocomplete decoration extension (Create & Edit only); ghost-text is visually distinct, Tab-accepts, typing dismisses

**State Management**

- Zustand 5.0 store: active mode (create / edit / study), note metadata, AI request queue, user preferences (Default Mode persists per account in `users.default_mode`)
- Immer 11.1 for immutable updates

**Inline Diff**

- *Deferred to Phase 2 (`diff-match-patch`); not in MVP. The MVP's Edit mode is a plain editable surface (identical to Create) — the inline-diff/comparison view and version snapshots are the Phase 2 additions.*

## 3. Backend Architecture

**Supabase Auth**

- Email/password signup; JWT sessions with auto-refresh
- Sign-up requires beta ToS acceptance — didactic notes only, no patient-identifying information (FR-009)
- Gates all application access (NFR-003)

**Postgres Database**

- Tables: `users` (profile + `default_mode` preference), `notes`, `nursing_terms`, `events` (metadata-only beta usage events, FR-012)
- No `note_mode` column — mode is a runtime view, not persisted
- Row-Level Security for per-user isolation (`events`: insert-own; team reads aggregates via service role)
- *No `note_versions` or `usage_quotas` tables in MVP — deferred to Phase 2*

**Edge Functions (Deno)**

- AI orchestration for autocomplete and key-term spotting
- Per-user runaway backstop (high daily ceiling circuit breaker) — cost insurance, not a product quota
- Context capping + prompt caching for cost control

**Storage**

- Note attachments (*PDF/DOCX export deferred — MVP copies key terms to clipboard*)

## 4. AI Integration

**Autocomplete (Create & Edit) — local-first**

- Local 5,000+ nursing-terms DB is the **primary**, instant path for word completion (<100ms, no API)
- OpenAI GPT-4.1 nano provides phrase-prediction ghost-text when available (<500ms or suppressed)
- Triggered after a 150ms typing pause; assistive and dismissable; fires in Create & Edit, never in Study Mode
- **Fidelity guard:** completions must not diverge from the student's content into generic textbook text that pollutes Study Mode signal

**Key Term Spotting (Study)**

- OpenAI GPT-4o-mini with Structured Outputs (typed JSON term list; emphasis-cue enum: `exam_mention`, `noted_repetition`, `emphatic_phrasing`, `formatting`)
- Spotting input serializes the Tiptap document preserving bold/highlight marks — the `formatting` cue is undetectable from plain text
- Surfaces exam-relevant terms + student-recorded emphasis cues; per-term helpful/not-helpful feedback logs a `term_feedback` event (FR-012)
- Target <5s per 3,000 words; longer notes split into ~3,000-word chunks (requested in parallel where possible), merged + deduped, streamed progressively into the sidebar; cap = first ~12,000 words with a truncation notice

**Term Definition Hover (Study)**

- Local nursing-terms DB lookup only — no model call, no quota
- Hover tooltip (term + short snippet) on spotted terms

**Cost Control**

- No token accounting and no quotas in MVP (unlimited for beta); FR-012's metadata usage events are not token tracking
- Controlled by capping context per request (current paragraph / ~500 tokens), prompt caching, and a per-user runaway backstop (NFR-004)

## 5. Data Architecture

**Notes**

```
notes {
  id: uuid
  user_id: uuid
  title: text
  content: jsonb          -- Tiptap document
  word_count: int
  created_at: timestamptz
  updated_at: timestamptz
}
-- auto-save overwrites latest content every 30s (retry with backoff); no server-side version history in MVP
-- client keeps a rolling localStorage recovery copy (per-user, cleared on sign-out) for crash recovery — not version history
```

**Nursing Terms**

```
nursing_terms {
  id: uuid
  term: text
  definition: text        -- short snippet for hover tooltip
}
-- 5,000+ seeded terms; powers local autocomplete + Study hover tooltip
-- seeded from public-domain/CC sources (e.g., MeSH, CC-BY Open RN) with in-app attribution; license-cleared before autocomplete integration
```

**Usage Events (FR-012)**

```
events {
  id: uuid
  user_id: uuid
  type: text              -- note_created | note_opened | mode_toggled | suggestion_shown | suggestion_accepted | keyterm_spotting_run | term_feedback | app_error | perf_timing
  value: int              -- optional count (accepted characters, duration ms)
  created_at: timestamptz
}
-- metadata only, never note content; RLS insert-own, team reads aggregates via service role
```

- *Deferred to Phase 2: `note_versions` (snapshots/history) and `usage_quotas` (tiers/caps)*

**Validation**

- Zod 4.4 for API inputs, form validation, and env-var validation

## 6. Performance Budgets

| Interaction | Budget |
| --- | --- |
| Local autocomplete (keystroke → suggestion) | <100ms |
| AI ghost-text (else suppressed) | <500ms |
| Mode cycle (Create/Edit/Study) | <50ms |
| Key term spotting | <5s per 3,000 words (longer notes chunked + progressive, capped at first ~12,000 words) |
| Slash menu open + filter | <50ms |

**Optimization**

- Debounce autocomplete (150ms)
- Code-split routes; lazy-load non-critical UI
- Web Worker for heavy AI post-processing
- Local cache of the nursing-terms DB for instant autocomplete

## 7. Feature-to-Tech Mapping

| Feature | Implementation |
| --- | --- |
| Three-Mode Architecture | Zustand mode state (create / edit / study); `Ctrl+M` cycles modes; Tiptap editable toggle (Create & Edit editable, Study read-only); single blue accent, mode differentiated by layout/badges/status bar |
| Local-First Autocomplete | Local nursing-terms DB (primary) + Tiptap decoration; Edge Function → GPT-4.1 nano for phrase ghost-text |
| Auto-Save | 30s interval write of latest content to `notes` with retry/backoff; rolling localStorage recovery copy (no server snapshots) |
| AI Key Term Spotting | Edge Function → GPT-4o-mini Structured Outputs; sidebar with click-to-jump + clipboard export |
| Term Definition Hover | Local nursing-terms DB lookup; hover tooltip (Study only); no AI call |
| Note Library | List view; title search; sort by last-edited / created / title |
| Slash Menu | `@tiptap/suggestion`; formatting primitives (Create & Edit) |
| Auth & Cost Control | Supabase Auth (+ sign-up ToS gate); per-user runaway backstop in Edge Functions |
| Beta Instrumentation | Metadata-only `events` table (RLS insert-own) + client perf timings for NFR-001 |

## 8. Monetization (Deferred to Phase 2)

- MVP runs unlimited AI for 50 beta users — no tiers, no quotas
- The freemium model (Free/Pro/Team, request caps, billing) is specced in `phase-2/prd.md` and activates after beta validation

## 9. Testing Strategy

**Unit (Vitest 4.1 + React Testing Library 16.3)**

- Mode toggle state machine, autocomplete debounce + local-first behavior, key-term parsing, auto-save (retry + recovery copy), instrumentation event emission
- 80%+ coverage on critical paths

**Integration / E2E (Playwright 1.60)**

- Sign Up → contextual onboarding → Create Mode → auto-save
- Create / Edit → local autocomplete + AI ghost-text accept/dismiss
- Open Note → cycle to Study Mode → Key Term Spotting → copy terms to clipboard
- Study Mode → term hover tooltip (local dictionary)
- Installable PWA: manifest valid, app installs, static shell loads

## 10. Build, Deployment & Security

**Build / Deploy**

- `next build`; deploy to Vercel (PWA static-shell service worker + edge cache)
- Supabase migrations for schema and RLS policies
- Lighthouse target: 90+ performance

**CI/CD**

- ESLint + TypeScript checks; automated test runs on PR; staging previews

**Security**

- All Supabase traffic over HTTPS; Postgres RLS for user isolation
- User notes never used to train AI models (NFR-003); OpenAI API used under its no-training / limited-retention terms
- Edge Functions do not log or persist AI request/response payloads
- Zod input validation; React default escaping for XSS; parameterized queries via `supabase-js`
- Secrets in environment variables; CORS restricted on Edge Functions

## 11. MVP Scope Boundaries

**In Scope**

- Create, Edit, and Study modes (Create & Edit editable and identical for now; Study read-only)
- Local-first AI autocomplete (local DB primary + AI ghost-text)
- Auto-save (latest content only)
- AI key-term spotting (Study) + sidebar, click-to-jump, clipboard export
- Term definition hover tooltip (Study, local dictionary)
- Note library, slash menu (formatting primitives), contextual onboarding
- Installable PWA shell (online-only)

**Out of Scope (Phase 2 / later)**

- Edit Mode inline diff / comparison view + version snapshots/history (Phase 2; the editable Edit mode itself ships in the MVP)
- AI smart summary (Phase 2)
- Paid tiers + quotas (Phase 2, with billing)
- Nursing slash templates SOAP/SBAR/Care Plan (Phase 2)
- PDF/DOCX export (Phase 2); offline note editing/sync (post-beta)
- Shorthand, definition-on-demand popup, cloze (Fast-Follow)
- Audio transcription, flashcards/quizzes, collaboration, mobile native, LMS, spaced repetition, concept maps

**Debt Allowances**

- English-only for MVP
- Educator features post-MVP
