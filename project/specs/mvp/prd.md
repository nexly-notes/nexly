# NEXLY RN (4-Week MVP) — PRD

## 1. TL;DR

> NEXLY RN is an installable PWA that helps pre-licensure nursing students keep pace with lectures and turn their own notes into study material, through two modes — Write (AI-assisted capture) and Study (AI key-term spotting). It matters now because note-taking is core to nursing school, yet students can't keep up with the professor's pace and later can't tell which of their notes are exam-relevant — and generalist AI tools either don't help or take over the writing. NEXLY's bet is assistive AI: it accelerates the student's own work, never does it for them.

---

## 2. Problem

**Who has the problem?**

- Pre-licensure nursing students (ADN/BSN) in didactic lecture courses. Secondary: advanced-practice students (MSN/DNP).

**What is the problem?**

- During lecture, students fall behind the professor's pace while writing and miss content; afterward they can't tell which of their own notes are exam-relevant or which concepts the professor emphasized.
- Today they cope with generic note apps (Notion, OneNote, Google Docs), typing faster, or copying a classmate's notes — none of which help them keep pace *or* surface exam-relevant terms from their own writing.

**Why now?**

- Fast, cheap LLMs (GPT-4.1 nano; GPT-4o-mini Structured Outputs) make sub-500ms assistive autocomplete and reliable key-term extraction economical at beta scale — capability that wasn't affordable before.
- Generalist AI tools lean substitutive (they write for you); the assistive, nursing-specific niche is open.

---

## 3. Goals & non-goals

**Goals** — *outcome-oriented; validated by the success criteria (`SC-01..04`) over a 50-user, 2-week beta.*

- [ ] The two-mode workflow is worth the context switch — students actually use both (→ SC-01, the primary hypothesis)
- [ ] Students keep pace with lecture using Write Mode — self-report "faster than my current method" (→ SC-02)
- [ ] Students turn their own notes into exam-relevant study material via Study Mode key-term spotting (→ SC-03)
- [ ] Assistive-AI integrity holds — the student stays editor-of-record; AI accelerates, never authors (design invariant, no SC)

**Non-goals** — *out of scope for the MVP; full phasing in `phase-2/prd.md` and `phase-3/prd.md`.*

- Edit Mode + inline diff, version snapshots/history (Phase 2)
- AI smart summary; paid tiers + quotas with billing (Phase 2)
- SOAP/SBAR/Care-Plan templates, PDF/DOCX export, shorthand expansion, definition-on-demand, cloze (Phase 2 Fast-Follow)
- Offline note editing/sync — the installable shell ships, offline does not (post-beta)
- Audio/transcription, flashcards/quizzes, real-time collaboration, native mobile, LMS, spaced repetition, concept maps (later phases)
- **Important!** No feature that writes notes *for* the student — that violates the assistive-AI principle.

---

## 4. User stories

*Narrative, not tabular — coherence comes from the `US-` codes and the traceability tag, not a grid.*

**US-01 — Falling behind in lecture** · *validates SC-02, FR-02*

- **Who:** ADN student typing notes during a fast cardiology lecture
- **Today:** types as fast as she can, misses sentences, or stops writing to listen and loses the content
- **With this:** local-first autocomplete completes nursing terms instantly and AI ghost-text predicts phrase endings (<500ms or suppressed); Tab accepts, typing dismisses — she keeps pace without the AI writing for her

**US-02 — Studying from her own notes** · *validates SC-03, FR-05*

- **Who:** BSN student prepping for a pharmacology exam from two weeks of notes
- **Today:** rereads everything, unsure which terms matter or what the professor stressed
- **With this:** toggles a note to Study Mode; AI spots exam-relevant terms and emphasis cues into a sidebar with click-to-jump; hovering a term shows a local-dictionary definition; she copies the term list to study

**US-03 — Cleaning up after class** · *validates SC-01, FR-03, FR-04*

- **Who:** any student revisiting a note later
- **Today:** notes are messy; reformatting in a generic app is slow
- **With this:** reopens in Write Mode (capture and revision in one surface), uses the `/` menu for structure, auto-save every 30s — no separate edit mode to learn

---

## 5. Requirements

### Functional

*Grouped by `Area`; priorities Must (P0) / Should (P1) / Nice (P2). Acceptance is terse — full detail in `tech-specs.md`.*

| ID | Area | Requirement | Pri | Acceptance |
| --- | --- | --- | --- | --- |
| FR-01 | Modes | Write/Study modes with read-only Study and a Write↔Study toggle | Must | single blue accent, differentiated by layout/badges; editing blocked in Study; `Ctrl+M`; transition <50ms |
| FR-02 | Write | Local-first autocomplete | Must | local <100ms after a 150ms pause; AI ghost-text <500ms or suppressed; visually distinct; Tab accepts, typing dismisses; none in Study |
| FR-03 | Write | Auto-save every 30s | Must | saved every 30s to `notes`; recovery = last successful save; no version table/UI |
| FR-04 | Write | `/` formatting menu | Should | fuzzy, keyboard-navigable; H1–H3, lists, divider, code, quote; disabled in Study |
| FR-05 | Study | Key-term spotting + sidebar | Must | terms + emphasis cues with context; click-to-jump; "Copy terms"; <5s for a 3,000-word note |
| FR-06 | Study | Term-definition hover | Should | tooltip (term + snippet) after 200ms; local dictionary, no AI; Study only |
| FR-07 | Library | Note library search + sort | Must | searchable by title; sort by last-edited / created / title; opens in Write |
| FR-08 | Onboarding | Non-blocking contextual onboarding | Should | first-use tooltips for the two modes; dismissable; never blocks first use |
| FR-09 | Auth | Auth + per-user runaway backstop | Must | Supabase Auth gates all access; high per-user daily ceiling; unlimited for beta; not a product quota |
| FR-10 | Modes | Remember last-used mode per session | Nice | defaults to Write |

### Non-Functional

*Acceptance criteria are testable; IDs are referenced by `roadmap.md` and `tech-specs.md`.*

| ID | Requirement | Acceptance |
| --- | --- | --- |
| NFR-01 | Latency budgets | local autocomplete <100ms; AI ghost-text <500ms or suppressed; mode toggle <50ms; key-term spotting <5s/3,000 words; slash menu <50ms |
| NFR-02 | Reliability | no data loss beyond a 30s window; <5% critical bugs/crashes in beta |
| NFR-03 | Privacy & access | Supabase Auth on every route; Postgres RLS per-user isolation; notes never used to train AI; Zod validation; secrets in env only |
| NFR-04 | Beta cost control | unlimited AI; context capping + prompt caching + per-user runaway backstop; no token tracking/quotas |
| NFR-05 | Minimal UX | Write Mode minimal and distraction-free; onboarding non-blocking |
| NFR-06 | Delivery | installable desktop/web PWA (manifest, icons, static-shell SW); online-only; desktop-first; offline editing/sync post-beta |

**Dependencies:** Supabase (Auth, Postgres, Edge Functions, Storage); OpenAI GPT-4.1 nano + GPT-4o-mini Structured Outputs; Next.js 16 / React 19 / TS 6 / Tiptap 3.23 / Zustand 5 / Tailwind 4. *Full architecture in `tech-specs.md`.*

---

## 6. Success criteria

*Each SC is a pass/fail gate proven by its bundled metric(s); measured after 2 weeks with 50 beta users. This set IS the roadmap Release Gate.*

| SC | Success criterion | Metric | Green | Yellow | Red (pivot) |
| --- | --- | --- | --- | --- | --- |
| SC-01 | Two-mode workflow validated (Goal 1) | both modes used in Week 1 | ≥60% | 40–59% | <40% |
| SC-02 | Write Mode catch-up value (Goal 2) | autocomplete acceptance (accepted ÷ shown) | ≥40% | 25–39% | <25% |
| SC-02 | ″ | self-report "keep up" / "faster" | majority positive | mixed | "no different" |
| SC-03 | Study Mode value (Goal 3) | Key Term Spotting used ≥ once | ≥50% | 30–49% | <30% |
| SC-04 | Reliability guardrail | critical bugs/crashes | <5% | — | ≥5% |
| SC-04 | ″ | data loss | none beyond 30s | — | any beyond 30s |

- *SC-01 is the primary hypothesis; SC-04 is the must-not-regress guardrail; latency guardrail = `NFR-01` budgets hold.*
- *Pivot if SC-01 or SC-03 goes red, or users ask "why not one mode with everything?"*
- *Lagging metrics (track, don't optimize): DAU, retention, free-to-paid conversion, churn.*

---

## 7. Risks & mitigations

*The product's core uncertainty is AI accuracy — these are the bets to watch during beta.*

| Risk | Mitigation |
| --- | --- |
| Key-term accuracy (false pos/neg) — top risk for the differentiator | Ground in the local term DB; user feedback loop; GPT-4o-mini Structured Outputs |
| Autocomplete acceptance/accuracy too low | Local-first removes network from the common path; assistive, dismissable, Tab-to-accept |
| **Autocomplete fidelity** — AI drifting into generic textbook text that pollutes the Study signal | Cap context to the student's own paragraph; suppress low-confidence completions |
| AI ghost-text latency vs typing speed | Hard <500ms budget; late suggestions suppressed, never shown late |
| Users reject two modes ("why not one?") | Contextual onboarding; toggle is one keystroke; validated by metric 1 |
| Over-reliance → passive note-taking | Assistive-only design; the student stays editor-of-record |
| OpenAI pricing / cost at scale | Context cap + prompt caching + runaway backstop; quotas return with billing in Phase 2 |

---

## 8. Open questions

*Unknowns to resolve during build/beta.*

- [ ] Is "accepted ÷ shown" the right acceptance definition, or should it weight by accepted characters? (eng + PM, before M4)
- [ ] What key-term false-positive rate feels noisy vs helpful? Needs a beta tolerance threshold. (PM, during beta)
- [ ] How do we gauge a *non-blocking* onboarding's effectiveness without a completion gate? (PM, before M6) — *onboarding-completion was dropped as a hard metric; revisit*
- [ ] Does context capped to the current paragraph give enough signal for phrase prediction, or do we need a wider window? (eng, M4)
- [ ] What runaway-backstop daily ceiling catches abuse without hitting genuine heavy users? (eng, before beta)
