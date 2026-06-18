# NEXLY RN – Product Requirements Document (Phase 2: Fast-Follow)

## 1. Overview

- **Scope:** Post-MVP work that (a) restores features deliberately deferred from the lean 4-Week MVP, (b) adds study accelerators on top of the two-mode workflow, and (c) activates monetization
- **Goal:** Deepen the Write/Study workflow and turn on paid tiers, prioritized by beta feedback
- **Dependency:** Ships only after MVP success criteria are green or yellow

## 2. Deferred from MVP (Re-Scoped In)

*These were specced for the MVP, then deferred to keep the 4-week build focused on the two-mode differentiator (assistive autocomplete + key-term spotting). Nothing from this deferred set was dropped — it lands here.*

**Editing & Versioning (Week 7-8)**

- **Edit Mode:** a distinct revision surface with on-demand, color-coded **inline diff** vs the last save (`diff-match-patch` 1.0.5, debounced 500ms, Web Worker, computed <200ms)
- **Version snapshots:** `note_versions` table; one snapshot per 30s auto-save; Free retains last 5/note; restore infrastructure
- **Full Version History UI** + **Side-by-Side Diff Viewer** read the restored snapshots — now unblocked by the snapshot table above
- *In MVP, "what changed" is out of scope and auto-save keeps only the last successful save; this section restores full revision tooling*

**Study Accelerators**

- **AI Smart Summary:** on-demand "Key Takeaways" bullet summary in Study Mode + Regenerate (GPT-4o-mini Structured Outputs, <5s/3,000 words)

**Capture (Week 5-6)**

- **Nursing slash templates:** prebuilt SOAP / SBAR / Care Plan blocks in the `/` menu (the user-authored custom template designer follows in Month 2+, §5)

**Export & Delivery**

- **PDF/DOCX export** of notes and key-term lists (*MVP ships clipboard copy of key terms only*)
- **Offline editing & sync:** offline note persistence (IndexedDB), pending-writes queue, conflict resolution on reconnect (*MVP ships an installable PWA shell but is online-only*)

## 3. Monetization Activation

*MVP ran unlimited AI for 50 beta users with no tiers. Phase 2 turns on the freemium model once beta validates demand.*

- **Tiers:**

| Tier          | Price                | Autocomplete           | Key Term Spotting | Smart Summary | Snapshots   |
| ------------- | -------------------- | ---------------------- | ----------------- | ------------- | ----------- |
| Free          | $0                   | 100/mo, then local DB  | 10/mo             | 10/mo         | Last 5/note |
| Pro           | $8.99/mo or $79/yr   | Unlimited              | Unlimited         | Unlimited     | Unlimited   |
| Team/Educator | $19.99/mo per seat   | Unlimited              | Unlimited         | Unlimited     | Unlimited   |

- **Enforcement:** `usage_quotas` table + Edge Function quota checks + monthly reset
- **Billing:** payment integration; Pro unlocks all Fast-Follow features; Free keeps the caps above
- *The MVP's per-user runaway backstop becomes the floor under the Free tier's request caps*

## 4. Fast-Follow Features (New)

**Week 5-6 (After Beta Launch)**

- **Shorthand Expansion:** AI converts nursing abbreviations to full text inline
- **Definition-on-Demand:** highlight text → AI returns a concise definition, shown in a click-to-pin popup (*the local-dictionary term hover tooltip ships in the MVP*)

**Week 7-8 (Based on User Feedback)**

- **Cloze Deletion Generator:** AI suggests fill-in-the-blank questions from notes

## 5. Month 2+ (Phase 2 Core)

- Custom template designer (user-authored Tiptap templates)
- Advanced diff features (three-way diff, annotations)
- Spaced repetition for cloze cards
- Audio sync
- Flashcards generated from spotted key terms
- Quiz generation
- Visual concept mapping
- Mobile companion app
- Real-time collaboration (shared notes, co-editing)

## 6. Requirements (High-Level)

**Functional**

1. Edit Mode + inline diff reuse `diff-match-patch`; the diff renders off the main thread; available outside Study Mode only
2. Version History and Side-by-Side Diff read `note_versions` snapshots — written from Phase 2 onward; no MVP snapshot history exists to migrate
3. Shorthand, definition-on-demand, smart summary, cloze, and flashcards reuse the AI model paths and respect tier quotas
4. Tiers gate features and AI request caps via `usage_quotas`; billing controls tier assignment
5. Custom template designer persists user templates and exposes them in the `/` slash menu

**Non-Functional**

1. Reuse MVP performance budgets; new AI calls target <5s
2. No regression to MVP Write Mode speed or minimal UI
3. Pro tier unlocks all Fast-Follow features; Free tier keeps the caps in §3
4. PWA delivery must not regress the desktop/web experience

*Phase 3 and Stretch scope is tracked in `phase-3/prd.md`.*
