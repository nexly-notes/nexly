# NEXLY RN – Product Requirements Document (4-Week MVP)

## 1. Product Overview

- **Name:** NEXLY RN – AI-Powered Nursing Education Platform
- **Elevator Pitch:** NEXLY RN helps nursing students keep pace with lectures and turn their own notes into study material through two AI modes: **Write** (fast, AI-assisted capture and revision) and **Study** (AI key-term spotting).
- **Problem:** Lecture note-taking is core to nursing school, but students can't always keep up with the professor's pace while writing — and later they can't tell which of their notes are exam-relevant. Generalist tools fix neither.
- **Solution:** Two modes, one principle:
  1. **Write Mode:** fast capture and revision with local-first AI autocomplete that helps students keep up.
  2. **Study Mode:** AI key-term spotting that surfaces exam-relevant content from the student's own notes.
- **Important! Core principle — assistive AI, not substitutive AI.** Every AI feature accelerates the student's own work (catching up, spotting terms) and never does the thinking or note-taking for them. This principle is the differentiator, not any single model call.

## 2. Goals & Success Criteria

### Primary Goals (4-Week MVP)

1. **Validate the two-mode hypothesis**: ≥60% of users use both Write and Study in Week 1
2. **Prove Write Mode catch-up value**: users report they can keep pace with lecture / "faster than [current method]"
3. **Validate Study Mode value**: ≥50% use Key Term Spotting at least once
4. **Measure autocomplete effectiveness**: ≥40% acceptance rate

### Deferred to Phase 2 (Nothing Lost — see `phase-2/prd.md`)

_Specced for the MVP, then deferred to keep the 4-week build focused on the two-mode differentiator._

- **Edit Mode as a distinct mode + on-demand inline diff** (Phase 2, Week 7-8)
- **AI Smart Summary / "Key Takeaways"** (Phase 2)
- **Paid tiers + quota enforcement** — MVP runs unlimited for beta (Phase 2, with billing)
- **Backend version-snapshot table + last-5 retention + restore infra** (Phase 2, Week 7-8)
- **SOAP / SBAR / Care Plan slash templates** (Phase 2, Week 5-6)
- **PDF/DOCX export** — MVP ships clipboard copy of key terms (Phase 2)
- **Offline note editing / sync** — MVP is an installable PWA but online-only (post-beta)
- **Edit-or-Study open dialog** — removed; notes open in Write Mode with a Study toggle

### Out of Scope (Fast-Follow / Later Phases)

- Shorthand expansion, definition-on-demand AI popup, cloze generator
- Full version-history UI, side-by-side diff viewer
- Audio recording/transcription, time-based lecture tracking
- Flashcards/quizzes, clinical documentation for patient care
- Real-time collaboration, mobile native app, LMS integrations
- Spaced repetition/scheduling, full visual concept maps

### Success Criteria (Definition of Done)

After 2 weeks with 50 beta users:

- ≥60% use both modes (Write/Study) in Week 1
- Autocomplete acceptance rate ≥40%
- ≥50% use Key Term Spotting at least once
- Users report keeping pace with lecture / "faster than [current method]"
- <5% critical bugs or crashes

## 3. Target Users

### Primary Persona

Pre-licensure Nursing Students (ADN/BSN)

### Secondary Persona

Advanced Practice Nursing Students (MSN/DNP)

### Tertiary Persona

Nursing Educators (as validators and institutional adopters - post-MVP)

### Pain Points

- Can't keep pace with the professor while taking notes during lecture
- Difficulty identifying exam-relevant content in their own notes
- Missing key concepts emphasized by professors
- Unclear what to focus on when studying

## 4. User Workflow

### Flow

**New Note:** Sign Up → Contextual intro → Create New Note → Write Mode (autocomplete, fast capture, minimal UI, auto-saves every 30s) → Save note

**Existing Note:** Open Note → opens in Write Mode → toggle to Study Mode anytime (AI spots key terms, term hover tooltips, sidebar shows term list) → copy key terms to clipboard

### Key Screens

1. Note Editor (Tiptap-based Write surface)
2. Mode Toggle (Write / Study)
3. Key Terms Sidebar (Study Mode - spotted terms with context)
4. Note Library (list view with search)
5. Contextual onboarding tooltips (first use)

## 5. Core Features

_All features are in scope for the 4-Week MVP._

1. **Two-Mode Architecture** — Write and Study modes, each optimized for a different stage of the capture-and-learning workflow
2. **Local-First AI Autocompletion** — instant local nursing-term completion plus AI ghost-text phrase prediction when it arrives; assistive and dismissable (Write Mode)
3. **Auto-Save** — automatic saving every 30s (no version history UI in MVP)
4. **AI Key Term Spotting** — automatically surfaces exam-relevant terms and professor emphasis cues in Study (core differentiator); sidebar with click-to-jump and clipboard export
5. **Note Library** — find, search, sort, and open notes
6. **Slash Menu** — fast formatting primitives via a `/` menu (Write Mode)
7. **Term Definition Hover** — hovering a spotted term in Study Mode shows a tooltip with the term and a short definition from the local nursing-terms dictionary (no AI call)
8. **Contextual Onboarding** — inline tooltips introduce the two modes on first use; no blocking screen flow

## 6. Requirements (Functional and Non-Functional)

**Functional Requirements**

| ID    | Requirement                                                                                                                                                                    | Priority | Acceptance Criteria                                                                                                                                              |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | The system shall provide Write and Study modes with distinct visual indicators, shall enforce read-only behavior in Study Mode, and shall toggle Write↔Study                   | Must     | Both modes share a single blue accent and are differentiated by layout and badges, not accent color; editing blocked in Study; toggle works; transition <50ms    |
| FR-02 | The system shall provide local-first AI autocomplete in Write Mode: the local dictionary completes immediately, and AI ghost-text predicts phrase continuations when available | Must     | Local suggestion <100ms after a 150ms pause; AI ghost-text <500ms or suppressed; visually distinct from typed text; Tab accepts, typing dismisses; none in Study |
| FR-03 | The system shall auto-save note content every 30s to `notes`                                                                                                                   | Must     | Content saved every 30s; recovery falls back to the last successful save; no version-history table or UI in MVP (deferred to Phase 2)                            |
| FR-04 | The system shall detect exam-relevant terms in Study Mode and shall present them in a sidebar with click-to-jump and clipboard export                                          | Must     | Terms + emphasis cues listed with context; click scrolls to location; "Copy terms" copies the list; <5s for a 3,000-word note                                    |
| FR-05 | The system shall provide a note library with title search and sorting                                                                                                          | Must     | List view searchable by title; sortable by last-edited / created / title; click opens the note in Write Mode                                                     |
| FR-06 | The system shall provide a `/` command menu for formatting primitives in Write Mode                                                                                            | Should   | `/` opens a fuzzy-filtered, keyboard-navigable menu; inserts H1–H3, lists, divider, code, quote; disabled in Study                                               |
| FR-07 | The system shall show a hover tooltip with the term and a short definition for spotted terms in Study Mode, sourced from the local nursing-terms dictionary                    | Should   | Hovering a flagged term opens a tooltip (term + snippet) after a 200ms delay; local dictionary, no AI call or quota; Study Mode only                             |
| FR-08 | The system shall present contextual onboarding introducing the two modes on first use                                                                                          | Should   | First-session tooltips explain Write and Study; dismissable; no blocking screen flow                                                                             |
| FR-09 | The system shall authenticate users via Supabase Auth and shall protect AI endpoints with a per-user runaway backstop                                                          | Must     | Auth gates all access; AI unlimited for beta users; a high per-user daily ceiling (circuit breaker) prevents cost runaway; not a product quota                   |

**Non-Functional Requirements**

| ID     | Requirement                                                                                        | Priority | Acceptance Criteria                                                                                                                                      |
| ------ | -------------------------------------------------------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | The system shall meet defined latency budgets across core interactions                             | Must     | Local autocomplete <100ms; AI ghost-text <500ms (else suppressed); mode toggle <50ms; key-term spotting <5s/3,000 words; slash menu <50ms                |
| NFR-02 | The system shall be reliable and shall not lose data beyond a 30s window                           | Must     | <5% critical bugs or crashes during beta; no data loss beyond a 30s window                                                                               |
| NFR-03 | The system shall gate all access via Supabase Auth and shall not use user notes to train AI models | Must     | Supabase Auth gates all access; user notes are never used to train AI models                                                                             |
| NFR-04 | The system shall support the 50-user beta and shall control AI cost without quotas                 | Should   | Beta runs unlimited AI; cost controlled by capping context sent per request, prompt caching, and a per-user runaway backstop (no token tracking)         |
| NFR-05 | The system shall provide a minimal, distraction-free Write Mode and non-blocking onboarding        | Must     | Write Mode UI minimal and distraction-free; contextual onboarding does not block first use                                                               |
| NFR-06 | The system shall be delivered as an installable desktop/web PWA, online-only                       | Must     | Installable PWA — manifest, icons, static-shell service worker (Next.js 16.2.6, Tiptap 3.23, Tailwind 4.3); offline note editing/sync deferred post-beta |

_Post-MVP scope (Phase 2, Phase 3, Stretch) is tracked in separate PRDs: `phase-2/prd.md` and `phase-3/prd.md`._

## 7. Technical Requirements

### Frontend

- Next.js 16.2.6 (React 19.2.6)
- Tiptap 3.23 editor
- Tailwind 4.3
- Installable PWA (manifest, icons, static-shell service worker); online-only — offline editing/sync deferred post-beta

### Backend

- Supabase (Auth, Postgres, Edge Functions, Storage)
- Postgres tables: `users`, `notes`, `nursing_terms` (no `note_versions` or `usage_quotas` in MVP)
- Mode is a runtime view (Write/Study), not persisted — no `note_mode` column
- Auto-save writes latest content to `notes`; recovery uses the last successful save
- Row-Level Security on every table

### AI

- **GPT-4.1 nano** for autocomplete (Write Mode) — local-first: the local 5,000+ nursing-terms DB is the primary path for word completion; AI handles phrase prediction
- **GPT-4o-mini with Structured Outputs** for key term spotting (Study Mode)
- Cost control: cap context sent per request (current paragraph / ~500 tokens), prompt caching, per-user runaway backstop

### Performance

- Local autocomplete: <100ms
- AI ghost-text: <500ms (else suppressed)
- Mode toggle: <50ms
- Key term spotting: <5s for a 3,000-word note
- Slash menu open + filter: <50ms

## 8. Monetization Strategy (Deferred to Phase 2)

- **Important!** The MVP runs **unlimited AI for all 50 beta users** — no tiers, no quotas. Free-to-paid conversion is explicitly a lagging metric not optimized for in MVP (see §9).
- The freemium model (Free/Pro/Team tiers, request caps, billing) is fully specced in `phase-2/prd.md` and activates after beta validation.

## 9. Success Metrics

### MVP Validation Metrics (2 weeks after beta launch)

- **Mode Adoption Rate:** % of users using both modes (Write/Study) in Week 1
  - **Green light**: ≥60%
  - **Yellow light**: 40-59%
  - **Red light**: <40% (pivot strategy)
- **Write Mode Catch-up / Speed:** avg time from note creation to first save; qualitative "keep up with lecture"
  - **Green light**: users say "faster than [current method]" / "I can keep up"
  - **Yellow light**: mixed feedback
  - **Red light**: "Too slow" or "No different"
- **Study Mode Engagement:** % of users using Key Term Spotting at least once
  - **Green light**: ≥50%
  - **Yellow light**: 30-49%
  - **Red light**: <30% (users ignore Study Mode)
- **Autocomplete Acceptance:** % of suggestions accepted
  - **Green light**: ≥40%
  - **Yellow light**: 25-39%
  - **Red light**: <25% (accuracy too low)
- **Onboarding Completion:** % of users finishing contextual onboarding
  - **Green light**: ≥80%
  - **Yellow light**: 60-79%
  - **Red light**: <60%

### Decision Matrix

**Green Light (Keep Building)**

- ≥60% use both modes
- ≥50% use Study Mode feature
- ≥40% autocomplete acceptance
- Users say "this is faster" / "I can keep up with lecture"

**Yellow Light (Iterate)**

- Users understand modes but don't use one of them
- Autocomplete accuracy is poor
- Users confused by workflow

**Red Light (Pivot)**

- Users ignore Study Mode entirely
- "Why do I need two modes?"
- "Can I just have one mode with everything?"

### Lagging Metrics (Track but don't optimize for in MVP)

- DAU
- Retention
- Free-to-paid conversion
- Churn

## 10. Challenges & Risks

### Technical

- Autocomplete acceptance/accuracy in Write Mode
- **Autocomplete fidelity** — AI completing with generic textbook content that diverges from what the professor actually said, polluting the notes Study Mode relies on
- AI ghost-text latency vs typing speed (late suggestions must be suppressed, never shown late)
- AI accuracy for key term detection (false positives/negatives) — top risk for the differentiator
- Latency at scale

### User Behavior

- Users confused by two modes instead of one
- Students failing to adopt Study Mode
- Over-reliance on AI leading to passive note-taking (mitigated by assistive, dismissable design)
- Resistance to changing workflows

### Business

- Competition from generalist AI note apps
- Dependence on OpenAI API pricing
- User expectations for features not in MVP

### Mitigations

- Assistive AI design: ghost-text is dismissable, visually distinct, Tab-to-accept; the student stays editor-of-record
- Local-first autocomplete removes network latency from the common path
- Context cap + prompt caching + per-user runaway backstop control cost
- Key-term quality grounded in the local term DB, with a user feedback loop
- Contextual onboarding clarifies the two modes
- Clear roadmap communication: deferred features land in Phase 2
- Data privacy: notes not used to train AI
