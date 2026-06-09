# [Product / Feature Name] — PRD

*Sections, IDs, and format conventions mirror `project/specs/mvp/prd.md`: narrative sections stay prose; requirements, success criteria, and risks are tables. Cross-link with IDs (`US-`, `FR-`, `NFR-`, `SC-`).*

## 1. TL;DR

> Three sentences max. What are we building, who is it for, and why does it matter _now_?

---

## 2. Problem

**Who has the problem?**
The specific user or segment — avoid "all users."

**What is the problem?**
The pain in the user's own language, plus how they cope today (current alternatives). Show evidence, don't assert.

**Why now?**
What changed (market, platform, capability) that makes this the moment? If nothing changed, reconsider priority.

---

## 3. Goals & non-goals

**Goals** — outcome-oriented, not feature lists. Link each to the criterion that proves it.

- [ ] [outcome] (→ SC-01)

**Non-goals** — explicitly out of scope; point to later-phase docs where the work lands.

- [what you are deliberately not building]

---

## 4. User stories

The 2–5 core scenarios, as narrative (not a table). Code them `US-01..` and tag the criterion/requirement each exercises.

**US-01 — [short title]** · *validates SC-0x, FR-0x*

- **Who:** [persona]
- **Today:** [how they cope now and why it's bad]
- **With this:** [what changes]

---

## 5. Requirements

### Functional

Grouped by `Area`; IDs `FR-01..`; priority Must (P0) / Should (P1) / Nice (P2). Keep acceptance terse — detail lives in the tech spec.

| ID | Area | Requirement | Pri | Acceptance |
| --- | --- | --- | --- | --- |
| FR-01 | [area] | [what the system shall do] | Must | [testable check] |

### Non-Functional

Quality attributes; IDs `NFR-01..`; testable acceptance. Other docs reference these IDs — keep them stable.

| ID | Requirement | Acceptance |
| --- | --- | --- |
| NFR-01 | [latency / reliability / security / delivery] | [measurable threshold] |

**Dependencies:** [services, vendors, stack] — context, not a requirement.

---

## 6. Success criteria

Pass/fail gate; IDs `SC-01..`. Each criterion bundles one or more metrics (repeat the SC code across rows). Green/yellow/red, numbers not adjectives. This set IS the release gate.

| SC | Success criterion | Metric | Green | Yellow | Red (pivot) |
| --- | --- | --- | --- | --- | --- |
| SC-01 | [criterion] (Goal n) | [the measure] | [target] | [warn] | [pivot] |

- *Lagging metrics (track, don't optimize): …*
- *Pivot signals: …*

---

## 7. Risks & mitigations

The bets to watch — especially to the core differentiator — and how each is contained.

| Risk | Mitigation |
| --- | --- |
| [the risk] | [what reduces it] |

---

## 8. Open questions

Unknowns and pending decisions — feed `/specs-research` and `/decision`.

- [ ] [question] ([owner], [by when])
