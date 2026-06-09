# NEXLY RN – Technical Specifications

## 1. System Overview

- **Architecture:** Installable desktop/web Progressive Web App (PWA), online-only; no native runtime and no offline editing in MVP
- **Primary Stack:** Next.js 16.2.6 + React 19.2.6 + TypeScript 6 + Tailwind 4.3 + Tiptap 3.23
- **Backend:** Supabase (Auth, Postgres, Edge Functions, Storage)
- **Product Core:** Two-mode note workflow — Write (capture + revision) and Study (key-term spotting)
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
- Single blue brand accent shared across both modes; modes differentiated by layout and badges, not accent color
- Dark mode via CSS variables

**Rich Text Editor (Tiptap 3.23)**

- Starter Kit: headings, lists, code blocks, quotes, dividers
- Placeholder extension for empty-state hints
- Slash command menu (`@tiptap/suggestion`): formatting primitives only (H1–H3, lists, divider, code, quote) — *nursing templates deferred to Phase 2*
- Read-only enforced in Study Mode
- Autocomplete decoration extension (Write Mode only); ghost-text is visually distinct, Tab-accepts, typing dismisses

**State Management**

- Zustand 5.0 store: active mode (write / study), note metadata, AI request queue, user preferences
- Immer 11.1 for immutable updates

**Inline Diff**

- *Deferred to Phase 2 (Edit Mode + `diff-match-patch`); not in MVP*

## 3. Backend Architecture

**Supabase Auth**

- Email/password signup; JWT sessions with auto-refresh
- Gates all application access (NFR-03)

**Postgres Database**

- Tables: `users`, `notes`, `nursing_terms`
- No `note_mode` column — mode is a runtime view, not persisted
- Row-Level Security for per-user isolation
- *No `note_versions` or `usage_quotas` tables in MVP — deferred to Phase 2*

**Edge Functions (Deno)**

- AI orchestration for autocomplete and key-term spotting
- Per-user runaway backstop (high daily ceiling circuit breaker) — cost insurance, not a product quota
- Context capping + prompt caching for cost control

**Storage**

- Note attachments (*PDF/DOCX export deferred — MVP copies key terms to clipboard*)

## 4. AI Integration

**Autocomplete (Write Mode) — local-first**

- Local 5,000+ nursing-terms DB is the **primary**, instant path for word completion (<100ms, no API)
- OpenAI GPT-4.1 nano provides phrase-prediction ghost-text when available (<500ms or suppressed)
- Triggered after a 150ms typing pause; assistive and dismissable; never fires in Study Mode
- **Fidelity guard:** completions must not diverge from the student's content into generic textbook text that pollutes Study Mode signal

**Key Term Spotting (Study)**

- OpenAI GPT-4o-mini with Structured Outputs (typed JSON term list)
- Surfaces exam-relevant terms + professor emphasis cues
- Target <5s for a 3,000-word note

**Term Definition Hover (Study)**

- Local nursing-terms DB lookup only — no model call, no quota
- Hover tooltip (term + short snippet) on spotted terms

**Cost Control**

- No token tracking and no quotas in MVP (unlimited for beta)
- Controlled by capping context per request (current paragraph / ~500 tokens), prompt caching, and a per-user runaway backstop (NFR-04)

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
-- auto-save overwrites latest content every 30s; no version history in MVP
```

**Nursing Terms**

```
nursing_terms {
  id: uuid
  term: text
  definition: text        -- short snippet for hover tooltip
}
-- 5,000+ seeded terms; powers local autocomplete + Study hover tooltip
```

- *Deferred to Phase 2: `note_versions` (snapshots/history) and `usage_quotas` (tiers/caps)*

**Validation**

- Zod 4.4 for API inputs, form validation, and env-var validation

## 6. Performance Budgets

| Interaction | Budget |
| --- | --- |
| Local autocomplete (keystroke → suggestion) | <100ms |
| AI ghost-text (else suppressed) | <500ms |
| Mode toggle (Write/Study) | <50ms |
| Key term spotting (3,000-word note) | <5s |
| Slash menu open + filter | <50ms |

**Optimization**

- Debounce autocomplete (150ms)
- Code-split routes; lazy-load non-critical UI
- Web Worker for heavy AI post-processing
- Local cache of the nursing-terms DB for instant autocomplete

## 7. Feature-to-Tech Mapping

| Feature | Implementation |
| --- | --- |
| Two-Mode Architecture | Zustand mode state (write / study); Tiptap editable toggle; single blue accent, mode differentiated by layout/badges |
| Local-First Autocomplete | Local nursing-terms DB (primary) + Tiptap decoration; Edge Function → GPT-4.1 nano for phrase ghost-text |
| Auto-Save | 30s interval write of latest content to `notes` (no snapshots) |
| AI Key Term Spotting | Edge Function → GPT-4o-mini Structured Outputs; sidebar with click-to-jump + clipboard export |
| Term Definition Hover | Local nursing-terms DB lookup; hover tooltip (Study only); no AI call |
| Note Library | List view; title search; sort by last-edited / created / title |
| Slash Menu | `@tiptap/suggestion`; formatting primitives (Write Mode) |
| Auth & Cost Control | Supabase Auth; per-user runaway backstop in Edge Functions |

## 8. Monetization (Deferred to Phase 2)

- MVP runs unlimited AI for 50 beta users — no tiers, no quotas
- The freemium model (Free/Pro/Team, request caps, billing) is specced in `phase-2/prd.md` and activates after beta validation

## 9. Testing Strategy

**Unit (Vitest 4.1 + React Testing Library 16.3)**

- Mode toggle state machine, autocomplete debounce + local-first behavior, key-term parsing, auto-save
- 80%+ coverage on critical paths

**Integration / E2E (Playwright 1.60)**

- Sign Up → contextual onboarding → Write Mode → auto-save
- Write Mode → local autocomplete + AI ghost-text accept/dismiss
- Open Note → toggle to Study Mode → Key Term Spotting → copy terms to clipboard
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
- User notes never used to train AI models (NFR-03)
- Zod input validation; React default escaping for XSS; parameterized queries via `supabase-js`
- Secrets in environment variables; CORS restricted on Edge Functions

## 11. MVP Scope Boundaries

**In Scope**

- Write and Study modes
- Local-first AI autocomplete (local DB primary + AI ghost-text)
- Auto-save (latest content only)
- AI key-term spotting (Study) + sidebar, click-to-jump, clipboard export
- Term definition hover tooltip (Study, local dictionary)
- Note library, slash menu (formatting primitives), contextual onboarding
- Installable PWA shell (online-only)

**Out of Scope (Phase 2 / later)**

- Edit Mode + inline diff, version snapshots/history (Phase 2)
- AI smart summary (Phase 2)
- Paid tiers + quotas (Phase 2, with billing)
- Nursing slash templates SOAP/SBAR/Care Plan (Phase 2)
- PDF/DOCX export (Phase 2); offline note editing/sync (post-beta)
- Shorthand, definition-on-demand popup, cloze (Fast-Follow)
- Audio transcription, flashcards/quizzes, collaboration, mobile native, LMS, spaced repetition, concept maps

**Debt Allowances**

- English-only for MVP
- Educator features post-MVP
