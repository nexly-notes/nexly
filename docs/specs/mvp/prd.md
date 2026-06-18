# NEXLY RN (4-Week MVP) — PRD

## 1. TL;DR

> NEXLY RN is an installable PWA that helps pre-licensure nursing students keep pace with lectures and turn their own notes into study material, through three modes — Create and Edit (AI-assisted capture and revision) and Study (AI key-term spotting). It matters now because note-taking is core to nursing school, yet students can't keep up with the professor's pace and later can't tell which of their notes are exam-relevant — and generalist AI tools either don't help or take over the writing. NEXLY's bet is assistive AI: it accelerates the student's own work, never does it for them.

---

## 2. Problem

**Who has the problem?**

- Pre-licensure nursing students (ADN/BSN) in didactic lecture courses. Secondary: advanced-practice students (MSN/DNP).

**What is the problem?**

- During lecture, students fall behind the professor's pace while writing and miss content; afterward they can't tell which of their own notes are exam-relevant or which concepts the professor emphasized.
- Today they cope with generic note apps (Notion, OneNote, Google Docs), typing faster, or copying a classmate's notes — none of which help them keep pace _or_ surface exam-relevant terms from their own writing.

**Why now?**

- Fast, cheap LLMs (GPT-4.1 nano; GPT-4o-mini Structured Outputs) make sub-500ms assistive autocomplete and reliable key-term extraction economical at beta scale — capability that wasn't affordable before.
- Generalist AI tools lean substitutive (they write for you); the assistive, nursing-specific niche is open.

---

## 3. Goals & non-goals

**Goals** — _outcome-oriented; validated by the success criteria (`SC-001..004`) over a 50-user, 2-week beta._

- [ ] The multi-mode workflow is worth the context switch — students actually use the editing modes (Create/Edit) and Study (→ SC-001, the primary hypothesis)
- [ ] Students keep pace with lecture using Create Mode — self-report "faster than my current method" (→ SC-002)
- [ ] Students turn their own notes into exam-relevant study material via Study Mode key-term spotting (→ SC-003)
- [ ] Assistive-AI integrity holds — the student stays editor-of-record; AI accelerates, never authors (design invariant, no SC)

**Non-goals** — _out of scope for the MVP; full phasing in `phase-2/prd.md` and `phase-3/prd.md`._

- Edit Mode revision tooling — inline diff, version snapshots/history (Phase 2). _The MVP ships Edit as a named editable mode that mirrors Create; only its diff/comparison and versioning are deferred._
- AI smart summary; paid tiers + quotas with billing (Phase 2)
- SOAP/SBAR/Care-Plan templates, PDF/DOCX export, shorthand expansion, definition-on-demand, cloze (Phase 2 Fast-Follow)
- Offline note editing/sync — the installable shell ships, offline does not (post-beta)
- Audio/transcription, flashcards/quizzes, real-time collaboration, native mobile, LMS, spaced repetition, concept maps (later phases)
- **Important!** No feature that writes notes _for_ the student — that violates the assistive-AI principle.

---

## 4. User personas

_Personas, not stories — each persona carries the scenarios it drives; traceability comes from the `PER-` codes and the validates tag._

**PER-001 — Maya, second-year ADN student** · _primary · validates SC-002 via FR-002, FR-003_

- **Profile:** 24, community-college ADN program; works part-time as a CNA; three didactic lecture courses a term
- **Context:** types notes on a laptop during fast lectures (cardiology, pharm); no time to reformat in class
- **Pain points:** falls behind the professor's pace, misses sentences, or stops writing to listen and loses the content
- **Goals:** capture everything live without the AI writing for her; trust that nothing she typed is lost
- **Behaviors:** accepts a completion only when it matches what she meant to type (Tab); keeps typing otherwise, which dismisses the ghost text; relies on auto-save mid-lecture

**PER-002 — Jasmine, third-year BSN student** · _primary · validates SC-001, SC-003 via FR-001, FR-004, FR-005, FR-006, FR-007_

- **Profile:** 21, university BSN program; organized, anchors her study group
- **Context:** preps for a pharmacology exam from two weeks of her own notes; revisits and cleans notes after class
- **Pain points:** rereads everything, unsure which terms matter or what the professor stressed; reformatting in a generic app is slow
- **Goals:** turn her own notes into exam-relevant study material; jump from a term to its context fast
- **Behaviors:** reopens notes from the library, revises them in Edit Mode, structures them with the `/` menu, cycles to Study Mode (`Ctrl+M`), hovers terms for definitions, copies the term list to study

**PER-003 — Dana, MSN (APRN) student** · _secondary · supported, not beta-recruited_

- **Profile:** 33, working RN in an MSN program; denser, more clinical coursework; studies in short bursts
- **Pain points:** generalist AI tools take over the writing; she wants speed without losing her own voice
- **Goals:** the same multi-mode workflow at higher content density
- **Behaviors:** stress-tests term coverage beyond the pre-licensure vocabulary (a term-DB risk watchpoint); as a working clinician, the sign-up no-PHI rule matters for her notes

---

## 5. Requirements

### Functional

_Grouped by `Area`; priorities Must (P0) / Should (P1) / Nice (P2). Acceptance is terse — full detail in `tech-specs.md`._

| ID     | Area       | Requirement                                                     | Pri    | Acceptance                                                                                                                            |
| ------ | ---------- | --------------------------------------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------- |
| FR-001 | Modes      | Create/Edit/Study modes — Create & Edit editable (identical behavior for now), Study read-only; `Ctrl+M` cycles Create→Edit→Study | Must   | single blue accent, differentiated by layout/badges/status bar only; editing blocked in Study; `Ctrl+M` cycles Create→Edit→Study; transition <50ms |
| FR-002 | Create     | Local-first autocomplete                                        | Must   | local <100ms after a 150ms pause; AI ghost-text <500ms or suppressed; visually distinct; Tab accepts, typing dismisses; active in Create & Edit, none in Study |
| FR-003 | Create     | Auto-save every 30s                                             | Must   | saved every 30s to `notes` with retry/backoff; recovery = last successful save, or the newer local recovery copy (restore prompt); `beforeunload` warning while unsaved; no version table/UI                                                      |
| FR-004 | Create     | `/` formatting menu                                             | Should | fuzzy, keyboard-navigable; H1–H3, lists, divider, code, quote; active in Create & Edit, disabled in Study                             |
| FR-005 | Study      | Key-term spotting + sidebar                                     | Must   | terms + emphasis cues (student-recorded markers: exam mentions, noted repetition, emphatic phrasing, highlight/bold) with context; click-to-jump; "Copy terms"; per-term helpful/not-helpful feedback (FR-012 event); <5s/3,000 words — longer notes populate progressively at that rate, capped at the first ~12,000 words with a notice                                            |
| FR-006 | Study      | Term-definition hover                                           | Should | tooltip (term + snippet) after 200ms; local dictionary, no AI; Study only                                                             |
| FR-007 | Library    | Note library (create, open, delete, search, sort)               | Must   | create blank note; delete with confirmation; searchable by title; sort by last-edited / created / title; opens in Create by default, honors FR-010 when set |
| FR-008 | Onboarding | Non-blocking contextual onboarding                              | Should | first-use tooltips for the three modes; dismissable; never blocks first use                                                          |
| FR-009 | Auth       | Auth + per-user runaway backstop                                | Must   | Supabase Auth gates all access; sign-up requires beta ToS acceptance (didactic notes only, no patient-identifying information); high per-user daily ceiling — when tripped, AI pauses for the day with a non-blocking notice while local autocomplete, hover, and editing continue; unlimited for beta; not a product quota                                  |
| FR-010 | Modes      | Default Mode preference                                         | Nice   | existing notes open in the user's Default Mode (Create default); new blank notes always open in Create; no per-session last-used memory |
| FR-011 | Create     | Rich-text content support                                       | Must   | core set (Starter Kit): headings, bold/italic/underline/strikethrough, code, lists, blockquote, divider, links; extended set (Should): highlight, alignment, checklists, images (URL insert), resizable tables |
| FR-012 | Beta       | Metadata-only usage instrumentation                             | Must   | events: note_created, note_opened, mode_toggled, suggestion_shown, suggestion_accepted (+ accepted chars), keyterm_spotting_run, term_feedback, app_error, plus NFR-001 perf timings; Supabase `events` under RLS; never note content; powers SC-001..004 |

_Design-only extras in `design.md` (favorites, tags, folders, archive) are non-gating stretch scope — the FR set above is the MVP build contract._

### Non-Functional

_Acceptance criteria are testable; IDs are referenced by `roadmap.md` and `tech-specs.md`._

| ID      | Requirement       | Acceptance                                                                                                                            |
| ------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-001 | Latency budgets   | local autocomplete <100ms; AI ghost-text <500ms or suppressed; mode toggle <50ms; key-term spotting <5s/3,000 words; slash menu <50ms |
| NFR-002 | Reliability       | no loss of saved work beyond a 30s window while connected; on network loss, unsaved changes persist in-tab (amber badge) with save retry/backoff; a rolling local recovery copy (per-user, cleared on sign-out — crash recovery, not version history) restores unsaved content after crash/reload; <5% critical bugs/crashes in beta |
| NFR-003 | Privacy & access  | Supabase Auth on every route; Postgres RLS per-user isolation; notes never used to train AI; AI calls via the OpenAI API under its no-training / limited-retention terms; Edge Functions never log or persist AI payloads; usage events carry no note content; Zod validation; secrets in env only |
| NFR-004 | Beta cost control | unlimited AI; context capping + prompt caching + per-user runaway backstop; no token accounting or quotas — metadata usage events per FR-012 only |
| NFR-005 | Minimal UX        | Create & Edit minimal and distraction-free — FR-011's content tools live in one toolbar, no extra panels; onboarding non-blocking      |
| NFR-006 | Delivery          | installable desktop/web PWA (manifest, icons, static-shell SW); online-only; desktop-first; offline editing/sync post-beta            |

**Dependencies:** Supabase (Auth, Postgres, Edge Functions, Storage); OpenAI GPT-4.1 nano + GPT-4o-mini Structured Outputs; Next.js 16 / React 19 / TS 6 / Tiptap 3.23 / Zustand 5 / Tailwind 4; curated nursing-terms dataset (5,000+ terms + snippet definitions — source selected before M3, seeded and license-cleared before autocomplete integration begins, as it is FR-002's primary path). _Full architecture in `tech-specs.md`._

---

## 6. Success criteria

_Each SC is a pass/fail gate proven by its bundled metric(s); measured after 2 weeks with 50 beta users. This set IS the roadmap Release Gate._

| SC     | Success criterion                    | Metric                                     | Green             | Yellow | Red (pivot)    |
| ------ | ------------------------------------ | ------------------------------------------ | ----------------- | ------ | -------------- |
| SC-001 | Multi-mode workflow validated (Goal 1) | an editing mode (Create/Edit) and Study both used in Week 1 | ≥60%       | 40–59% | <40%           |
| SC-002 | Create Mode catch-up value (Goal 2)  | autocomplete acceptance (accepted ÷ shown) | ≥40%              | 25–39% | <25%           |
| SC-002 | ″                                    | self-report "keep up" / "faster"           | majority positive | mixed  | "no different" |
| SC-003 | Study Mode value (Goal 3)            | Key Term Spotting used ≥ once              | ≥50%              | 30–49% | <30%           |
| SC-004 | Reliability guardrail                | critical bugs/crashes                      | <5%               | —      | ≥5%            |
| SC-004 | ″                                    | data loss beyond a 30s window of work (after save retry + local recovery) | none | — | any |

- _SC-001 is the primary hypothesis; SC-004 is the must-not-regress guardrail; latency guardrail = `NFR-001` budgets hold (verified via FR-012 perf timings)._
- _Denominators: SC-001/SC-003 over activated users (signed in + created ≥1 note in Week 1; activation rate reported as context); SC-002 acceptance pooled over activated users' suggestion events; SC-002 self-report over exit-survey respondents; SC-004 crashes over activated users; data loss is pass/fail._
- _Measurement: FR-012 events + perf timings in-product; beta exit survey + bug-report channel outside it._
- _Pivot if SC-001 or SC-003 goes red, or users ask "why not one mode with everything?"_
- _Lagging metrics (track, don't optimize): DAU, retention, library usage, free-to-paid conversion, churn._

---

## 7. Risks & mitigations

_The product's core uncertainty is AI accuracy — these are the bets to watch during beta._

| Risk                                                                                              | Mitigation                                                                              |
| ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Key-term accuracy (false pos/neg) — top risk for the differentiator                               | Ground in the local term DB; per-term feedback control (FR-005 → FR-012 event); GPT-4o-mini Structured Outputs |
| Autocomplete acceptance/accuracy too low                                                          | Local-first removes network from the common path; assistive, dismissable, Tab-to-accept |
| **Autocomplete fidelity** — AI drifting into generic textbook text that pollutes the Study signal | Cap context to the student's own paragraph; suppress low-confidence completions         |
| AI ghost-text latency vs typing speed                                                             | Hard <500ms budget; late suggestions suppressed, never shown late                       |
| Users reject multiple modes ("why not one?")                                                      | Contextual onboarding; mode cycle is one keystroke; validated by metric 1               |
| Over-reliance → passive note-taking                                                               | Assistive-only design; the student stays editor-of-record                               |
| OpenAI pricing / cost at scale                                                                    | Context cap + prompt caching + runaway backstop; quotas return with billing in Phase 2  |
| Term DB quality/licensing — inaccurate or unlicensed definitions shown to students                | Public-domain/CC sources (e.g., MeSH, CC-BY Open RN) with in-app attribution; SME spot-review of most-frequent terms; positioned as educational reference, not clinical guidance |
| Students paste clinical/patient data, which reaches OpenAI                                        | Sign-up ToS no-PHI clause (FR-009); didactic-only positioning; client-side PHI warning is a post-MVP candidate |

---

## 8. Open questions

_Unknowns to resolve during build/beta._

- [ ] Is "accepted ÷ shown" the right acceptance definition, or should it weight by accepted characters? (eng + PM, before M4)
- [ ] What key-term false-positive rate feels noisy vs helpful? Needs a beta tolerance threshold. (PM, during beta)
- [ ] How do we gauge a _non-blocking_ onboarding's effectiveness without a completion gate? (PM, before M6) — _onboarding-completion was dropped as a hard metric; revisit_
- [ ] Does context capped to the current paragraph give enough signal for phrase prediction, or do we need a wider window? (eng, M4)
- [ ] What runaway-backstop daily ceiling catches abuse without hitting genuine heavy users? (eng, before beta)
- [ ] What is the source + review process for the 5,000+ nursing-term DB? (eng + PM, before M3)
